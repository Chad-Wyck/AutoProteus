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
from test_providers import FakeModelServer

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


class HostApiTests(unittest.TestCase):
    def test_practical_model_check_is_authenticated_and_blocks_conflicting_operations(self):
        from unittest.mock import Mock
        with self.request('/api/model-check') as response:
            self.assertEqual(json.load(response)['status'],'idle')
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/model-check',{},token=False)
        with patch.object(self.app.practical,'start',return_value={'status':'running'}) as start:
            with self.request('/api/model-check',{}) as response:
                self.assertEqual(json.load(response)['status'],'running')
            start.assert_called_once()
        self.app.practical.thread=Mock()
        self.app.practical.thread.is_alive.return_value=True
        try:
            for path,data in (('/api/settings',{'temperature':.4}),('/api/start',{'task':'blocked'}),('/api/seed-check',{})):
                with self.assertRaises(urllib.error.HTTPError): self.request(path,data)
            with patch.object(self.app.practical,'stop') as stop:
                with self.request('/api/model-check/stop',{}) as response: self.assertTrue(json.load(response)['ok'])
                stop.assert_called_once()
        finally: self.app.practical.thread=None

    def test_action_allowance_defaults_off_and_can_be_enabled_without_inference(self):
        self.assertFalse(self.app.settings.values['action_limit'])
        with patch('controller.server.check_protocol') as qualify:
            with self.request('/api/settings', {'action_limit':True,'max_steps':4}) as response:
                value = json.load(response)
                self.assertTrue(value['action_limit']); self.assertEqual(value['max_steps'], 4)
            with self.request('/api/settings', {'action_limit':False}) as response:
                self.assertFalse(json.load(response)['action_limit'])
            qualify.assert_not_called()

    def test_browser_stream_disconnect_closes_its_lease_without_a_close_post(self):
        import time
        with self.request('/api/browser', {'id':'c'*32,'sequence':1}) as response:
            token = json.load(response)['watch']
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/browser/watch?id='+'c'*32+'&watch=wrong', token=False)
        stream = self.request('/api/browser/watch?id='+'c'*32+'&watch='+token, token=False)
        self.assertEqual(stream.headers['Content-Type'], 'text/event-stream')
        self.assertEqual(stream.readline(), b': connected\n')
        self.assertEqual(self.app.presence.public()['tabs'], 1)
        stream.close()
        deadline = time.monotonic()+8
        while self.app.presence.public()['tabs'] and time.monotonic() < deadline:
            time.sleep(.05)
        self.assertEqual(self.app.presence.public()['tabs'], 0)

    def test_browser_heartbeat_tracks_tabs_and_last_close_releases_resources(self):
        now = [0]
        self.app.presence.clock = lambda:now[0]
        def pulse(identifier, sequence, closing=False):
            with self.request('/api/browser', {'id':identifier, 'sequence':sequence, 'closing':closing}) as response:
                self.assertTrue(json.load(response)['ok'])
        with patch.object(self.app.evaluations, 'close') as checks, patch.object(self.app.agent, 'close') as stop, patch.object(self.app.local, 'unload_models') as unload:
            pulse('a'*32, 1); pulse('b'*32, 1)
            pulse('a'*32, 2, True)
            self.app.presence.tick()
            stop.assert_not_called(); unload.assert_not_called()
            pulse('b'*32, 2, True)
            self.app.presence.tick()
            now[0] += 5
            self.app.presence.tick()
            checks.assert_called_once(); stop.assert_called_once(); unload.assert_called_once()
            with self.request('/api/state') as response:
                self.assertTrue(json.load(response)['resources']['browser']['released'])

    def test_browser_heartbeat_requires_authentication_and_valid_identity(self):
        for data, token in (({'id':'x'*32,'sequence':1},False), ({'id':'bad','sequence':1},True)):
            with self.subTest(data=data), self.assertRaises(urllib.error.HTTPError):
                self.request('/api/browser', data, token=token)

    def test_local_file_setup_delegates_to_managed_runtime_and_blocks_active_tasks(self):
        with patch.object(self.app.local, 'prepare_file') as prepare:
            with self.request('/api/setup/local-file', {'path':'.data/models/gguf/model.gguf',
                    'base_url':'http://localhost:11435','internet':False}) as response:
                self.assertEqual(response.status,200)
            prepare.assert_called_once_with('.data/models/gguf/model.gguf','http://localhost:11435',False)
            with patch.object(self.app,'active',return_value={'id':'active'}):
                with self.assertRaises(urllib.error.HTTPError):
                    self.request('/api/setup/local-file',{'path':'.data/models/gguf/model.gguf'})
            self.assertEqual(prepare.call_count,1)

    def test_local_inventory_uses_selected_address_and_keeps_unavailable_models_out_of_ready_list(self):
        inventory = {'available': True, 'models':[{'name':'valid:latest'}],
                     'unavailable':[{'name':'missing:9b','reason':'Model files unavailable'}], 'downloaded':[]}
        with patch.object(self.app.local, 'inventory', return_value=inventory) as inspect:
            with self.request('/api/local?base_url=http%3A%2F%2Flocalhost%3A11434') as response:
                self.assertEqual(json.load(response), inventory)
            inspect.assert_called_once_with('http://localhost:11434')
            with self.assertRaises(urllib.error.HTTPError):
                self.request('/api/local?base_url=http%3A%2F%2Fremote.example')
            self.assertEqual(inspect.call_count, 1)

    def test_unavailable_model_is_rejected_before_inference_or_settings_changes(self):
        original = dict(self.app.settings.values)
        inventory = {'available':True, 'models':[], 'unavailable':[{'name':'missing:9b'}], 'downloaded':[]}
        with patch.object(self.app.local, 'inventory', return_value=inventory), patch('controller.server.check_protocol') as infer:
            with self.assertRaises(urllib.error.HTTPError) as failure:
                self.request('/api/connect', {'provider':'ollama','base_url':'http://localhost:11435','model':'missing:9b'})
            body = json.load(failure.exception)
            self.assertIn('files could not be verified', body['error'])
            infer.assert_not_called()
            self.assertEqual(self.app.settings.values, original)

    def test_evidence_api_observes_the_active_owner_and_rejects_writes(self):
        from controller.inference_history import InferenceHistory
        session = self.app.store.create('Observe active work', 'demo', 'fixture')
        session['status'] = 'running'; self.app.store.save(session)
        key = InferenceHistory(self.app.store, session, {}).blob({'instructions': ['fixture'], 'tools': []})
        revision = self.app.store.revision
        with self.request('/api/evidence?id=' + session['id']) as response:
            value = json.load(response)
        self.assertTrue(value['read_only']); self.assertIn('verification', value)
        with self.request('/api/evidence/blob?id=' + session['id'] + '&key=' + key) as response:
            self.assertEqual(json.load(response)['value']['instructions'], ['fixture'])
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/evidence', {'id': session['id'], 'status': 'completed'})
        self.assertEqual(session['status'], 'running')
        self.assertEqual(self.app.store.revision, revision)

    def test_live_input_api_persists_pending_cancellation_and_refuses_inactive_tasks(self):
        from unittest.mock import Mock
        session = self.app.store.create('Input fixture', 'demo', 'fixture')
        payload = {'id': session['id'], 'message': 'Keep café unchanged', 'mode': 'steer', 'request_id': 'a' * 32}
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/input', payload)
        worker = Mock(); worker.is_alive.return_value = True
        self.app.agent.workers[session['id']] = (threading.Event(), worker)
        try:
            with self.request('/api/input', payload) as response:
                self.assertEqual(json.load(response)['status'], 'pending')
            with self.request('/api/input', payload):
                pass
            self.assertEqual(len(session['input_queue']), 1)
            with self.request('/api/session?id=' + session['id']) as response:
                self.assertEqual(json.load(response)['input_queue'][0]['message'], payload['message'])
            with self.request('/api/input/cancel', {'id': session['id'], 'request_id': payload['request_id']}):
                pass
            self.assertEqual(session['input_queue'][0]['status'], 'cancelled')
        finally:
            self.app.agent.workers.clear()

    def test_journal_export_contains_verifiable_inference_blobs(self):
        from controller.inference_history import InferenceHistory, digest
        session = self.app.store.create('Evidence export', 'demo', 'fixture')
        value = {'tools': [], 'instructions': [{'role': 'system', 'content': 'You are AutoProteus'}]}
        key = InferenceHistory(self.app.store, session, self.app.settings.values).blob(value)
        with self.request('/api/export?id=' + session['id']) as response:
            with zipfile.ZipFile(io.BytesIO(response.read())) as archive:
                saved = json.loads(archive.read('inference/' + key + '.json'))
                self.assertEqual(digest(saved), key)
                self.assertEqual(saved, value)
                self.assertIn('events.jsonl', archive.namelist())

    def test_offered_input_cancellation_uses_worker_liveness_not_guest_status_or_request_flags(self):
        from controller.interactions import Inputs
        from unittest.mock import Mock
        session = self.app.store.create('Interrupted offer', 'demo', 'fixture')
        inputs = Inputs(self.app.store, session)
        inputs.enqueue('Cancel after stopping.', 'steer', 'b' * 32)
        inputs.offer('steer')
        session['status'] = 'paused'
        self.app.store.save(session)
        worker = Mock(); worker.is_alive.return_value = True
        self.app.agent.workers[session['id']] = (threading.Event(), worker)
        payload = {'id': session['id'], 'request_id': 'b' * 32, 'worker_stopped': True}
        try:
            with self.assertRaises(urllib.error.HTTPError):
                self.request('/api/input/cancel', payload)
            self.assertEqual(session['input_queue'][0]['status'], 'offered')
            worker.is_alive.return_value = False
            with self.request('/api/input/cancel', payload) as response:
                self.assertTrue(json.load(response)['cancelled'])
            self.assertEqual(session['input_queue'][0]['status'], 'cancelled')
            self.assertEqual(inputs.offer('steer'), [])
        finally:
            self.app.agent.workers.clear()

    def test_offered_input_can_be_cancelled_without_a_surviving_worker(self):
        from controller.interactions import Inputs
        session = self.app.store.create('Recovered offer', 'demo', 'fixture')
        inputs = Inputs(self.app.store, session)
        inputs.enqueue('Obsolete follow-up.', 'followup', 'c' * 32)
        inputs.offer('finish')
        with self.request('/api/input/cancel', {'id': session['id'], 'request_id': 'c' * 32}) as response:
            self.assertTrue(json.load(response)['cancelled'])
        self.assertEqual(inputs.offer('finish'), [])

    def test_public_submission_review_returns_source_bound_evidence_without_running_code(self):
        from controller.evaluation import freeze_source, source_identity
        from controller.isolation import seed_files
        from controller.storage import atomic_json
        source = seed_files(ROOT)
        session = freeze_source(self.app.store, source, 'Review')
        atomic_json(self.app.store.directory(session['id']) / 'candidate.json', source)
        files = Artifacts(self.app.store, session)
        files.put('harness/arguments.json', base64.b64encode(b'{}').decode())
        files.checkpoint([*session['artifacts'], 'harness/arguments.json'])
        with patch.object(self.app, 'start_run') as start:
            with self.request('/api/submission-review', {'id': session['id']}) as response:
                result = json.load(response)
        start.assert_not_called()
        self.assertFalse(result['ticket']['ready_for_independent_checks'])
        self.assertIn('arguments.json', result['ticket']['policy']['unexpected_files'])
        self.assertNotEqual(result['ticket']['source_sha256'], source_identity(source))
    def test_restart_uses_the_same_task_and_checkpoint_without_creating_a_session(self):
        session = self.app.store.create('Continue this exact task.', 'demo', 'fixture')
        session['messages'] = [{'role': 'user', 'content': 'Preserve my correction.', 'origin': 'human'}]
        files = Artifacts(self.app.store, session)
        files.put('note.txt', base64.b64encode(b'checkpoint').decode())
        files.checkpoint(['note.txt'])
        with patch.object(self.app.agent, 'restart_seed') as restart:
            with self.request('/api/restart-seed', {'id': session['id']}) as response:
                self.assertEqual(json.load(response)['id'], session['id'])
            restart.assert_called_once_with(session)
        self.assertEqual(len(self.app.store.public()), 1)
        self.assertEqual(session['task'], 'Continue this exact task.')
        self.assertEqual(files.read('note.txt'), b'checkpoint')
        self.assertEqual(session['messages'][0]['origin'], 'human')

    def test_restart_is_rejected_while_a_task_or_comparison_is_active(self):
        from unittest.mock import Mock
        session = self.app.store.create('Waiting task.', 'demo', 'fixture')
        thread = Mock(); thread.is_alive.return_value = True
        with patch.object(self.app.agent, 'restart_seed') as restart:
            self.app.agent.workers[session['id']] = (threading.Event(), thread)
            try:
                with self.assertRaises(urllib.error.HTTPError):
                    self.request('/api/restart-seed', {'id': session['id']})
            finally:
                self.app.agent.workers.clear()
            self.app.evaluations.thread = thread
            try:
                with self.assertRaises(urllib.error.HTTPError):
                    self.request('/api/restart-seed', {'id': session['id']})
            finally:
                self.app.evaluations.thread = None
            restart.assert_not_called()

    def test_active_worker_prevents_creating_a_conflicting_saved_session(self):
        from unittest.mock import Mock
        session = self.app.store.create('Active', 'demo', 'none')
        thread = Mock(); thread.is_alive.return_value = True
        self.app.agent.workers[session['id']] = (threading.Event(), thread)
        try:
            with self.assertRaises(urllib.error.HTTPError): self.request('/api/start', {'task': 'conflicting'})
            self.assertEqual(len(self.app.store.public()), 1)
            with self.request('/api/state') as response:
                self.assertEqual(json.load(response)['active']['id'], session['id'])
        finally:
            self.app.agent.workers.clear()

    def test_session_controls_are_recoverable_and_incremental_views_exclude_context(self):
        session = self.app.store.create('Original', 'demo', 'none')
        session['messages'] = [{'role': 'user', 'content': 'private context'}]; self.app.store.save(session)
        identifier = session['id']
        self.request('/api/session/manage', {'id': identifier, 'action': 'rename', 'title': 'Renamed'}).close()
        with self.request('/api/session?id=' + identifier) as response:
            first = json.load(response); self.assertEqual(first['title'], 'Renamed'); self.assertNotIn('messages', first)
        with self.request('/api/session?id=' + identifier + '&revision=' + str(first['revision'])) as response:
            self.assertTrue(json.load(response)['unchanged'])
        self.request('/api/session/manage', {'id': identifier, 'action': 'delete'}).close()
        with self.request('/api/trash') as response: self.assertEqual(json.load(response)[0]['id'], identifier)
        self.request('/api/session/manage', {'id': identifier, 'action': 'restore'}).close()
        self.assertEqual(self.app.store.get(identifier)['title'], 'Renamed')
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

    def test_provider_diagnostic_errors_are_categorized_without_raw_details(self):
        from controller.providers import ProviderError
        with patch('controller.server.check_protocol', side_effect=ProviderError('secret-provider-body fake-key', category='timeout')):
            with self.assertRaises(urllib.error.HTTPError) as error:
                self.request('/api/connect', {'provider': 'hosted', 'base_url': 'https://example.test/v1', 'model': 'test'})
            response = json.load(error.exception)
            self.assertEqual(response['category'], 'timeout')
            self.assertNotIn('secret-provider-body', response['error'])
            self.assertNotIn('fake-key', response['error'])
            self.assertFalse(self.app.settings.values['configured'])

    def test_unavailable_isolation_prevents_session_and_native_launch(self):
        self.app.settings.update({'provider': 'demo', 'model': 'scripted-demo', 'configured': True})
        with patch.object(self.app.agent.appliance, 'verify', side_effect=IsolationError('Missing VM')), \
                patch('controller.isolation.VM') as vm:
            with self.assertRaises(urllib.error.HTTPError):
                self.request('/api/start', {'task': 'test'})
            self.assertEqual(self.app.store.public(), [])
            vm.assert_not_called()

    def test_checks_block_task_creation_and_candidate_reset(self):
        from unittest.mock import Mock
        self.app.evaluations.thread = Mock()
        self.app.evaluations.thread.is_alive.return_value = True
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/start', {'task':'must not create a session'})
        self.assertEqual(self.app.store.public(), [])
        session = self.app.store.create('trial', 'demo', 'test')
        session['candidate_from'] = 'f' * 32
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/reset', {'id':session['id']})
        self.assertEqual(session['candidate_from'], 'f' * 32)
        self.app.evaluations.thread = None

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

    def test_failed_connection_keeps_working_settings_and_key(self):
        self.app.settings.update({'provider':'demo', 'model':'scripted-demo', 'configured':True})
        previous = self.app.settings.public()
        with self.assertRaises(urllib.error.HTTPError):
            self.request('/api/connect', {'provider':'hosted', 'base_url':'https://bad.example', 'model':'', 'api_key':'do-not-save'})
        self.assertEqual(self.app.settings.public(), previous)
        self.assertFalse((self.app.data / 'credential.bin').exists())
    def test_hosted_connection_checks_selected_protocol_and_consumes_result(self):
        provider = FakeModelServer(hosted=True, native=True, diagnostic=True)
        try:
            with self.request('/api/connect', {'provider': 'hosted', 'base_url': provider.url,
                                               'model': 'fake-model', 'protocol': 'native', 'json_mode': True}) as response:
                self.assertTrue(json.load(response)['configured'])
            self.assertEqual(self.app.settings.values['protocol'], 'native')
            self.assertIn('tools', provider.payloads[0])
            self.assertNotIn('response_format', provider.payloads[0])
            self.assertEqual(len(provider.payloads), 8)
            self.assertEqual(provider.payloads[1]['messages'][-1]['role'], 'tool')
            self.assertTrue(self.app.settings.values['compatibility']['passed'])
            self.assertTrue(self.app.settings.values['compatibility']['rejected_call_recovery'])
        finally:
            provider.close()


if __name__ == '__main__':
    unittest.main()
