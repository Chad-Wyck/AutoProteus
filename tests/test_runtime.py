import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from controller.runtime import LocalRuntime
from test_seed import temporary_directory


class ModelInventoryTests(unittest.TestCase):
    def test_retention_probes_memory_without_loading_weights_and_unloads_only_app_models(self):
        with temporary_directory() as directory:
            runtime = LocalRuntime(Path(directory), None)
            config = {'provider':'ollama', 'base_url':'http://localhost:11435', 'model':'mine:latest'}
            runtime.note_model(config)
            loaded = {'models':[{'name':'mine:latest'}, {'name':'another-app:latest'}]}
            def service(url, data=None, **kwargs):
                if url.endswith('/api/ps'): return loaded
                self.assertTrue(url.endswith('/api/generate'))
                self.assertEqual(data, {'model':'mine:latest','keep_alive':0})
                loaded['models'] = [{'name':'another-app:latest'}]
                return {}
            with patch('controller.runtime.request_json', side_effect=service) as api:
                self.assertTrue(runtime.model_loaded(config))
                self.assertFalse(runtime.model_loaded({**config, 'provider':'hosted'}))
                self.assertFalse(runtime.model_loaded({**config, 'base_url':'https://remote.example'}))
                runtime.unload_models()
                self.assertFalse(runtime.model_loaded(config))
            self.assertFalse(any('/api/chat' in call.args[0] for call in api.call_args_list))

    def test_failed_import_or_qualification_preserves_the_saved_connection(self):
        from controller.config import Settings
        from controller.providers import ProviderError
        for stage in ('import', 'check'):
            with self.subTest(stage=stage), temporary_directory() as directory:
                settings = Settings(Path(directory))
                settings.update({'model':'previous:latest', 'configured':True})
                previous = dict(settings.values)
                runtime = LocalRuntime(Path(directory), settings)
                with patch.object(runtime, 'models', return_value=[]), patch('controller.runtime.import_file') as importer, patch('controller.runtime.check_protocol') as qualify:
                    importer.return_value = 'new:local'
                    if stage == 'import': importer.side_effect = ValueError('Unsupported GGUF')
                    else: qualify.side_effect = ProviderError('Model qualification failed', category='protocol')
                    runtime._prepare_file('fixture.gguf', settings.preview({}))
                self.assertEqual(settings.values, previous)
                self.assertFalse(runtime.public()['busy'])
                self.assertEqual(runtime.public()['phase'], 'error')

    def test_stale_tags_are_rejected_without_inference_and_valid_models_remain(self):
        requests = []
        def service(url, data=None, **kwargs):
            requests.append((url, data))
            if url.endswith('/api/tags'):
                return {'models': [{'name': name, 'size': 100} for name in ('valid:latest', 'missing:9b', 'invalid:4b')]}
            self.assertTrue(url.endswith('/api/show'))
            self.assertLessEqual(kwargs['timeout'], 3)
            if data['model'] == 'missing:9b':
                from controller.providers import ProviderError
                raise ProviderError('read GGUF metadata: The system cannot find the file specified')
            return {'model_info': {'general.architecture': 'fixture'}} if data['model'] == 'valid:latest' else {}
        with temporary_directory() as directory, patch('controller.runtime.request_json', side_effect=service):
            runtime = LocalRuntime(Path(directory), SimpleNamespace(values={'base_url':'http://localhost:11435'}))
            inventory = runtime.inventory()
        self.assertTrue(inventory['available'])
        self.assertEqual([item['name'] for item in inventory['models']], ['valid:latest'])
        self.assertEqual([item['name'] for item in inventory['unavailable']], ['missing:9b', 'invalid:4b'])
        self.assertEqual(len(requests), 4)
        self.assertFalse(any('/api/chat' in url or '/api/generate' in url for url, _ in requests))

    def test_cached_gguf_files_are_reported_separately_even_when_service_is_offline(self):
        from controller.providers import ProviderError
        with temporary_directory() as directory:
            root = Path(directory); cache = root / '.data/models/gguf'; cache.mkdir(parents=True)
            (cache / 'retained-Q6.gguf').write_bytes(b'GGUF\x03\0\0\0\x01' + b'\0' * 55)
            (cache / 'partial.gguf').write_bytes(b'GGUF')
            (cache / 'wrong.gguf').write_bytes(b'not GGUF' * 10)
            outside_cache = root / 'other-files'; outside_cache.mkdir()
            (outside_cache / 'unrelated.gguf').write_bytes(b'GGUF\x03\0\0\0\x01' + b'\0' * 55)
            runtime = LocalRuntime(root, SimpleNamespace(values={'base_url':'http://localhost:11435'}))
            with patch('controller.runtime.request_json', side_effect=ProviderError('private diagnostic detail')):
                inventory = runtime.inventory()
        self.assertFalse(inventory['available']); self.assertEqual(inventory['models'], [])
        self.assertEqual([item['name'] for item in inventory['downloaded']], ['retained-Q6.gguf'])
        self.assertEqual(inventory['downloaded'][0]['status'], 'local_file')
        self.assertNotIn('private diagnostic detail', str(inventory))

    def test_refresh_rechecks_deleted_files_and_uses_the_requested_service_address(self):
        from controller.providers import ProviderError
        missing = False
        def service(url, data=None, **kwargs):
            self.assertTrue(url.startswith('http://localhost:11434/'))
            if url.endswith('/api/tags'): return {'models':[{'name':'model:latest'}]}
            if missing: raise ProviderError('missing model files')
            return {'model_info': {'general.architecture':'fixture'}}
        with temporary_directory() as directory, patch('controller.runtime.request_json', side_effect=service):
            runtime = LocalRuntime(Path(directory), SimpleNamespace(values={'base_url':'http://localhost:11435'}))
            self.assertEqual(len(runtime.inventory('http://localhost:11434/')['models']), 1)
            missing = True
            refreshed = runtime.inventory('http://localhost:11434/')
            self.assertEqual(refreshed['models'], [])
            self.assertEqual(len(refreshed['unavailable']), 1)

    def test_expired_inventory_deadline_does_not_launch_more_checks(self):
        with temporary_directory() as directory, patch('controller.runtime.request_json', return_value={
                'models':[{'name':'fixture'}]}) as service, patch('controller.runtime.time.monotonic', side_effect=[0, 100]):
            runtime = LocalRuntime(Path(directory), SimpleNamespace(values={'base_url':'http://localhost:11435'}))
            inventory = runtime.inventory()
            self.assertEqual(service.call_count, 1)
            self.assertEqual(inventory['models'], [])
            self.assertIn('timed out', inventory['unavailable'][0]['reason'])


@unittest.skipUnless(os.name == 'nt', 'Windows managed model process tree')
class EngineLifecycleTests(unittest.TestCase):
    def test_closing_owned_runtime_ends_runner_children(self):
        from controller.windows_job import Job
        with temporary_directory() as directory:
            path = Path(directory) / 'child.pid'
            runtime = LocalRuntime(Path(directory), None)
            runtime.job = Job(vm_limits=False)
            script = "import pathlib,subprocess,sys,time; child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"
            runtime.process = subprocess.Popen([sys.executable, '-c', script, str(path)],
                                               creationflags=subprocess.CREATE_NO_WINDOW | 0x4)
            handle = None
            dll = ctypes.WinDLL('kernel32', use_last_error=True)
            dll.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            dll.OpenProcess.restype = wintypes.HANDLE
            dll.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            dll.CloseHandle.argtypes = [wintypes.HANDLE]
            try:
                runtime.job.attach_and_resume(runtime.process)
                deadline = time.monotonic() + 5
                while not path.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(path.exists())
                handle = dll.OpenProcess(0x100000, False, int(path.read_text()))
                self.assertTrue(handle)
                self.assertEqual(dll.WaitForSingleObject(handle, 0), 258)
                runtime.close()
                self.assertEqual(dll.WaitForSingleObject(handle, 5000), 0)
                self.assertIsNotNone(runtime.process.poll())
            finally:
                runtime.close()
                if handle:
                    dll.CloseHandle(handle)
