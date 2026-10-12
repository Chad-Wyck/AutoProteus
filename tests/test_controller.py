import base64
import io
import json
import os
from pathlib import Path
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch
import zipfile

from controller.config import Settings
from controller.errors import IsolationError
from controller.isolation import Artifacts
from controller.server import Application, make_server
from test_seed import temporary_directory
import test_seed
import controller.providers as providers

ROOT = Path(__file__).resolve().parents[1]


class StartupTests(unittest.TestCase):
    def test_second_instance_cannot_acquire_the_same_project_lock(self):
        from app import acquire_lock
        with temporary_directory() as directory:
            first = acquire_lock(Path(directory))
            self.assertIsNotNone(first)
            try:
                self.assertIsNone(acquire_lock(Path(directory)))
            finally:
                first.close()
            another = acquire_lock(Path(directory))
            self.assertIsNotNone(another)
            another.close()

    @unittest.skipUnless(os.name == 'nt', 'Windows credential encryption')
    def test_saved_credentials_are_encrypted_and_recoverable(self):
        with temporary_directory() as directory:
            settings = Settings(Path(directory))
            settings.update({'api_key': 'fake-key-for-testing'})
            stored = (Path(directory) / 'credential.bin').read_bytes()
            self.assertNotIn(b'fake-key-for-testing', stored)
            self.assertEqual(Settings(Path(directory)).key(), 'fake-key-for-testing')
            self.assertNotIn('fake-key-for-testing', json.dumps(settings.public()))


class HostProviderTests(test_seed.ProviderTests):
    """Replay the wire-format suite against the separately protected adapters."""
    def setUp(self):
        self.adapter = patch.multiple(test_seed, ModelClient=providers.ModelClient,
                                      ProviderError=providers.ProviderError)
        self.adapter.start()

    def tearDown(self):
        self.adapter.stop()


class HostApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.app = Application(ROOT, data=Path(self.temp.name))
        self.server = make_server(self.app, 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = 'http://127.0.0.1:' + str(self.server.server_port)

    def tearDown(self):
        self.app.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def request(self, path, data=None, token=True, origin=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['X-AutoProteus-Token'] = self.app.token
        if origin:
            headers['Origin'] = origin
        return urllib.request.urlopen(urllib.request.Request(self.base + path,
            data=json.dumps(data).encode() if data is not None else None, headers=headers), timeout=5)

    def test_authentication_and_origin_apply_to_controller(self):
        for kwargs in ({'token': False}, {'origin': 'https://another-site.example'}):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request('/api/state', **kwargs)
            self.assertEqual(error.exception.code, 403)

    def test_unavailable_isolation_prevents_session_and_native_launch(self):
        self.app.settings.update({'provider': 'demo', 'model': 'scripted-demo', 'configured': True})
        with patch.object(self.app.agent.appliance, 'verify', side_effect=IsolationError('Missing VM')), \
                patch('controller.isolation.VM') as vm:
            with self.assertRaises(urllib.error.HTTPError):
                self.request('/api/start', {'task': 'test'})
            self.assertEqual(self.app.store.public(), [])
            vm.assert_not_called()

    def test_edited_ui_is_previewed_and_downloaded_as_data_only(self):
        session = self.app.store.create('data', 'demo', 'scripted-demo')
        a = Artifacts(self.app.store, session)
        evil = b'<script>throw new Error("candidate must not run on host")</script>'
        a.put('harness/web/index.html', base64.b64encode(evil).decode())
        a.checkpoint(['harness/web/index.html'])
        with self.request('/api/file?id=' + session['id'] + '&path=harness/web/index.html') as response:
            self.assertEqual(json.load(response)['content'], evil.decode())
        with self.request('/api/download?id=' + session['id'] + '&path=harness/web/index.html') as response:
            self.assertEqual(response.headers['Content-Type'], 'application/octet-stream')
            self.assertTrue(response.headers['Content-Disposition'].startswith('attachment'))
        with self.request('/api/open-workspace', {'id': session['id']}) as response:
            archive = zipfile.ZipFile(io.BytesIO(response.read()))
            self.assertEqual(archive.read('harness/web/index.html'), evil)
        with self.request('/') as response:
            self.assertNotIn(evil, response.read())


if __name__ == '__main__':
    unittest.main()
