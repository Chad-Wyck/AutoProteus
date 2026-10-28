"""Small owned-process/HTTP fixtures only. No models, accelerators or VMs."""
from contextlib import contextmanager
import json
from pathlib import Path
import socket
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from controller.config import DEFAULTS
from controller.storage import atomic_json
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'evaluations'))
from owned_runtime import AssetPins, GIB, OwnedRuntime, validate
from study_support import file_identity, identity
import model_study as ms

FIXTURE = '''import json,sys,socket,subprocess,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
port,seed,context=map(int,sys.argv[1:4])
if len(sys.argv)>4 and sys.argv[4]=='child':
 childport=int(sys.argv[5])
 code='import socket,time; s=socket.socket(); s.bind(("127.0.0.1",'+str(childport)+')); s.listen(); time.sleep(60)'
 subprocess.Popen([sys.executable,'-c',code])
 for _ in range(100):
  with socket.socket() as s:
   if s.connect_ex(('127.0.0.1',childport))==0: break
  time.sleep(.02)
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):
  value={'status':'ok'} if self.path=='/health' else {'seed':seed+(1 if 'wrong' in sys.argv else 0),'context':context}
  self.send_response(200);self.end_headers();self.wfile.write(json.dumps(value).encode())
ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
'''


def port():
    with socket.socket() as stream:
        stream.bind(('127.0.0.1', 0))
        return stream.getsockname()[1]


def listening(number):
    with socket.socket() as stream:
        stream.settimeout(.2)
        return stream.connect_ex(('127.0.0.1', number)) == 0


class OwnedRuntimeTests(unittest.TestCase):
    def fixture(self, folder, extra=()):
        number = port()
        config = {**DEFAULTS, 'provider':'hosted', 'base_url':f'http://127.0.0.1:{number}/v1',
                  'context_tokens':16384, 'server_initial_seed':104729}
        spec = {'command':[sys.executable, '-u', '-c', FIXTURE, '{port}', '{seed}', '{context_tokens}', *extra],
                'startup_seconds':5, 'reported_seed_path':'seed', 'reported_context_path':'context'}
        pins = AssetPins({sys.executable:file_identity(sys.executable)})
        runtime = OwnedRuntime(folder, spec, config, pins, 10,
            memory_reader=lambda: {'available_physical':16*GIB, 'available_commit':16*GIB})
        self.addCleanup(runtime.close)
        return runtime

    def test_fresh_service_and_descendant_close_without_touching_unrelated_listener(self):
        with temporary_directory() as directory, socket.socket() as unrelated:
            unrelated.bind(('127.0.0.1',0));unrelated.listen()
            other = unrelated.getsockname()[1]
            child = port()
            runtime = self.fixture(Path(directory)/'runtime', ('child', str(child)))
            runtime.start()
            self.assertTrue(runtime.record['fresh_server'])
            self.assertTrue(runtime.record['reported_seed_matches'])
            self.assertTrue(runtime.record['reported_context_matches'])
            self.assertTrue(listening(child))
            runtime.close()
            self.assertFalse(listening(runtime.port))
            self.assertFalse(listening(child))
            self.assertTrue(listening(other))
            cleanup=json.loads((runtime.folder/'cleanup.json').read_text())
            self.assertTrue(cleanup['owned_process_stopped'])
            self.assertIsNone(cleanup['reason'])

    def test_occupied_port_never_starts_or_stops_an_external_service(self):
        with temporary_directory() as directory, socket.socket() as existing:
            existing.bind(('127.0.0.1',0));existing.listen()
            runtime = self.fixture(Path(directory)/'runtime')
            runtime.port = existing.getsockname()[1]
            with patch('owned_runtime.subprocess.Popen', side_effect=AssertionError('Must not launch')):
                with self.assertRaisesRegex(RuntimeError, 'already occupied'):runtime.start()
            self.assertTrue(listening(runtime.port))
            self.assertFalse(runtime.record['fresh_server'])

    def test_reported_seed_mismatch_fails_and_cleans_up(self):
        with temporary_directory() as directory:
            runtime = self.fixture(Path(directory)/'runtime', ('wrong',))
            with self.assertRaisesRegex(RuntimeError, 'requested seed'):runtime.start()
            self.assertFalse(listening(runtime.port))
            receipt=json.loads((runtime.folder/'cleanup.json').read_text())
            self.assertIn('requested seed', receipt['reason'])

    def test_memory_guard_stops_only_owned_fixture_and_preserves_the_reason(self):
        with temporary_directory() as directory:
            runtime = self.fixture(Path(directory)/'runtime')
            runtime.start()
            runtime.read_memory=lambda: {'available_physical':GIB, 'available_commit':16*GIB}
            runtime.monitor.join(timeout=3)
            self.assertFalse(runtime.monitor.is_alive())
            with self.assertRaisesRegex(RuntimeError, 'Memory floor'):runtime.guard()
            runtime.close()
            self.assertIn('Memory floor', json.loads((runtime.folder/'cleanup.json').read_text())['reason'])

    def test_lifetime_guard_stops_a_healthy_but_over_budget_service(self):
        with temporary_directory() as directory:
            runtime = self.fixture(Path(directory)/'runtime')
            runtime.start()
            runtime.began = time.monotonic()-runtime.lifetime-1
            runtime.monitor.join(timeout=3)
            with self.assertRaisesRegex(RuntimeError, 'lifetime expired'):runtime.guard()
            runtime.close()
            self.assertFalse(listening(runtime.port))

    def test_existing_evidence_and_changed_assets_cannot_be_reused(self):
        with temporary_directory() as directory:
            root = Path(directory)
            runtime = self.fixture(root/'runtime')
            runtime.folder.mkdir();(runtime.folder/'keep.txt').write_text('original')
            with self.assertRaises(FileExistsError):runtime.start()
            runtime.close()
            self.assertEqual([p.name for p in runtime.folder.iterdir()], ['keep.txt'])
            asset = root/'asset';asset.write_bytes(b'one')
            pins = AssetPins({str(asset):file_identity(asset)})
            asset.write_bytes(b'different')
            with self.assertRaisesRegex(RuntimeError, 'asset changed'):pins.guard()

    def test_manifest_rejects_unpinned_programs_remote_hosts_and_unbounded_limits(self):
        config={**DEFAULTS,'base_url':'http://127.0.0.1:8123/v1'}
        spec={'command':[sys.executable,'{port}','{seed}']}
        assets={sys.executable:'unused'}
        for bad, settings, pins in ((spec, config, {}), (spec, {**config,'base_url':'http://example.com:8123'}, assets),
                ({**spec,'startup_seconds':float('inf')},config,assets), ({**spec,'command':[sys.executable,'no placeholders']},config,assets)):
            with self.assertRaises(ValueError):validate(bad, settings, pins)

    def test_completed_queue_resume_does_not_launch_a_runtime_or_probe_a_dead_service(self):
        with temporary_directory() as directory:
            root=Path(directory);folder=root/'.data/study';folder.mkdir(parents=True)
            plan={'mode':'benchmark','repeats':2,'source_sha256':'test','source':[], 'scope':'mock lifecycle',
                  'profiles':[{'id':'fixture','runtime':{},'config':dict(DEFAULTS)}], 'upgrade_tasks':[],
                  'repeatability':{'sampling_seeds':[11,22]}}
            atomic_json(folder/'plan.json',plan);(folder/'plan.sha256').write_text(identity(plan))
            launches=[];active=[]
            class Owner:
                def __init__(self, profile):pass
                @contextmanager
                def attempt(self, attempt_folder, config, seconds):
                    launches.append(config['sampling_seed']);active.append(True)
                    try:yield SimpleNamespace(record={'fresh_server':True})
                    finally:active.pop()
            def service(_config):
                if not active:raise AssertionError('No probe before launch or after cleanup')
                return {'model':'fixture'}
            with patch.object(ms,'ROOT',root),patch.object(ms,'check'),patch.object(ms,'calibrate'),\
                    patch.object(ms,'RuntimeOwner',Owner),patch.object(ms,'model_identity',side_effect=service),\
                    patch.object(ms,'benchmark',return_value={'passed':True}),patch('builtins.print'):
                args=SimpleNamespace(input=str(folder),retry=[])
                ms._run(args);ms._run(args)
            self.assertEqual(launches,[11,22])
