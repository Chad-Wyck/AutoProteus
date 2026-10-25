import base64
import json
import os
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from controller.appliance import Appliance
from controller.config import Settings
from controller.errors import Cancelled, IsolationError
from controller.isolation import Artifacts, Broker, IsolatedAgent, VMLease, relative_name, seed_files, vm_command
from controller.storage import Store, atomic_json

ROOT = Path(__file__).resolve().parents[1]


class BoundaryTests(unittest.TestCase):
    def test_optional_request_cap_can_be_off_without_disabling_the_frame_limit(self):
        broker = Broker(self.store, self.session, self.client,
                        {**self.settings.values, 'action_limit':False, 'max_steps':1}, self.cancel)
        self.assertIsNone(broker.request_limit)
        broker.requests = 1000
        self.client.complete.return_value = {'content':'{}'}
        broker.handle({'op':'infer','messages':[{'role':'user','content':'Continue.'}]})
        self.assertEqual(broker.requests, 1001)
        broker.frames = 10000
        with self.assertRaisesRegex(IsolationError, 'message quota'):
            broker.handle({'op':'infer','messages':[{'role':'user','content':'Continue.'}]})

    def test_finished_run_watchdog_cannot_kill_a_retained_vm_at_its_old_deadline(self):
        vm = Mock(); vm.closed = threading.Event()
        finished = threading.Event(); finished.set()
        agent = IsolatedAgent(ROOT, self.store, self.settings)
        agent._watchdog(vm, threading.Event(), 0, finished)
        vm.close.assert_not_called()

    def test_two_stage_history_fits_while_message_byte_and_request_caps_remain(self):
        client = Mock(); client.complete.return_value = {'content': '{}'}
        broker = Broker(self.store, self.session, client, self.settings.values, threading.Event(), 'Activation state')
        messages = [{'role': 'user', 'content': str(i)} for i in range(402)]
        broker.handle({'op': 'infer', 'messages': messages})
        self.assertEqual(len(client.complete.call_args.args[0]), 403)
        with self.assertRaisesRegex(IsolationError, '2048-message'):
            broker.handle({'op': 'infer', 'messages': messages * 6})
        with self.assertRaisesRegex(IsolationError, 'Invalid model request'):
            broker.handle({'op': 'infer', 'messages': [{'role': 'user', 'content': 'x' * 1500001}]})
        self.assertEqual(broker.requests, 1)
        broker.requests = broker.request_limit
        with self.assertRaisesRegex(IsolationError, 'request quota'):
            broker.handle({'op': 'infer', 'messages': messages})

    def test_protocol_repairs_discard_raw_provider_data_and_keep_the_host_request_quota(self):
        from controller.providers import ProviderError
        client = Mock()
        client.complete.side_effect = ProviderError('private-host-key', {
            'protocol_reason':'tool_arguments', 'tool_calls':[{'unsafe':'private-host-key'}]}, category='protocol')
        broker = Broker(self.store, self.session, client, self.settings.values, threading.Event())
        marker = broker.handle({'op':'infer','messages':[{'role':'user','content':'test'}]})
        self.assertEqual(marker['provider_error'], 'protocol')
        self.assertEqual(marker['content'], '')
        self.assertNotIn('private-host-key', json.dumps(marker))
        self.assertNotIn('tool_calls', marker)
        self.assertIn('could not parse the tool arguments', marker['normalization_error'])
        broker.requests = broker.request_limit
        with self.assertRaisesRegex(IsolationError, 'request quota'):
            broker.handle({'op':'infer','messages':[{'role':'user','content':'test'}]})

    def test_host_activation_state_is_early_without_replacing_human_requirements(self):
        client = Mock()
        client.complete.return_value = {'content':'{}'}
        phase = 'CURRENT ACTIVATION STATE\nRunning seed is active.'
        broker = Broker(self.store, self.session, client, self.settings.values, threading.Event(), phase)
        messages = [{'role':'user','content':'Keep the original human constraint.'}]
        broker.handle({'op':'infer','messages':messages})
        forwarded = client.complete.call_args.args[0]
        self.assertEqual(forwarded[-1], messages[0])
        self.assertEqual(forwarded[0]['content'], phase)
        self.assertEqual(messages, [{'role':'user','content':'Keep the original human constraint.'}])
        broker.handle({'op':'infer','messages':forwarded})
        self.assertEqual(client.complete.call_args.args[0], forwarded)
        broker.context_config = {**self.settings.values,'context_tokens':self.settings.values['response_tokens']+128}
        broker.handle({'op':'infer','messages':messages})
        self.assertEqual(client.complete.call_args.args[0], messages)

    def test_failed_restart_preserves_the_previous_candidate_selection(self):
        session = self.store.create('Keep the previous version.', 'demo', 'fixture')
        agent = IsolatedAgent(ROOT, self.store, self.settings)
        try:
            for previous in (None, 'a' * 32):
                if previous is None:
                    session.pop('candidate_from', None)
                else:
                    session['candidate_from'] = previous
                with patch.object(agent, 'start', side_effect=IsolationError('fixture failure')):
                    with self.assertRaises(IsolationError):
                        agent.restart_seed(session)
                self.assertEqual(session.get('candidate_from'), previous)
                self.assertEqual(session['task'], 'Keep the previous version.')
        finally:
            agent.close()

    def setUp(self):
        parent = ROOT / '.data/test-tmp'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.root = Path(self.temp.name)
        self.store = Store(self.root / 'sessions')
        self.settings = Settings(self.root)
        self.settings.values.update(configured=True, provider='demo', model='scripted-demo', action_limit=True)
        self.session = self.store.create('task', 'demo', 'scripted-demo')
        self.client, self.cancel = Mock(), threading.Event()
        self.broker = Broker(self.store, self.session, self.client, self.settings.values, self.cancel)

    def tearDown(self):
        self.temp.cleanup()

    def test_command_line_has_no_host_sharing_network_monitor_or_fallback(self):
        with patch.object(Appliance, 'binary', return_value=ROOT / 'fixture-qemu'):
            args = vm_command(Appliance(ROOT))
        for flag, expected in [('-accel', 'kvm' if sys.platform == 'linux' else 'whpx'), ('-nic', 'none'), ('-monitor', 'none'), ('-display', 'none')]:
            self.assertEqual(args[args.index(flag) + 1], expected)
        self.assertIn('-no-user-config', args)
        self.assertIn('-nodefaults', args)
        self.assertNotIn('tcg', ' '.join(args))
        for forbidden in ('-drive', '-hda', '-fsdev', '-virtfs', '-netdev', '-qmp', '-usb', '-spice'):
            self.assertNotIn(forbidden, args)

    def test_no_native_execution_when_isolation_is_missing(self):
        agent = IsolatedAgent(ROOT, self.store, self.settings)
        with patch.object(agent.appliance, 'verify', side_effect=IsolationError('Unavailable')), \
                patch('controller.isolation.VM') as vm:
            with self.assertRaises(IsolationError):
                agent.start(self.session)
            vm.assert_not_called()
        self.assertEqual(self.session['status'], 'ready')

    def test_seed_does_not_receive_the_controller_or_host_launcher(self):
        names = {item['path'] for item in seed_files(ROOT)}
        self.assertIn('seed.py', names)
        self.assertIn('autoproteus/agent.py', names)
        self.assertIn('tests/test_text_helpers.py', names)
        self.assertNotIn('app.py', names)
        self.assertFalse(any(name.startswith('controller/') for name in names))

    def test_traversal_device_and_windows_special_paths_are_rejected(self):
        for name in ('../x', '/etc/passwd', 'a/../../x', 'D:/secret', 'a\\x', 'a//x', 'x:stream',
                     'NUL.txt', 'COM1', 'LPT2.json', 'COM¹.txt', 'CON .txt', 'x.', 'x ', 'x/./y', 'x\x00y'):
            with self.subTest(name=name), self.assertRaises(IsolationError):
                self.broker.handle({'op': 'file', 'path': name, 'data': 'eA=='})
        self.assertEqual(relative_name('harness/autoproteus/feature.py'), 'harness/autoproteus/feature.py')

    def test_files_are_inert_blobs_and_deletion_is_transactional(self):
        a = self.broker.artifacts
        a.put('harness/seed.py', base64.b64encode(b'raise SystemExit("do not import me")').decode())
        self.assertNotIn('artifacts', self.session)
        a.checkpoint(['harness/seed.py'])
        self.assertTrue(a.read('harness/seed.py').startswith(b'raise'))
        self.assertFalse((Path(self.session['workspace']) / 'harness/seed.py').exists())
        self.assertEqual(len(list(a.root.glob('*.blob'))), 1)
        a.checkpoint([])
        self.assertEqual(list(a.root.glob('*.blob')), [])

    def test_exports_and_requests_are_bound_to_this_session(self):
        other = self.store.create('other', 'demo', 'scripted-demo')
        for frame in ({'op': 'read_host', 'path': str(self.root)},
                      {'op': 'command', 'command': 'powershell'},
                      {'op': 'file', 'path': 'x', 'data': 'eA==', 'session': other['id']},
                      {'op': 'infer', 'messages': [], 'base_url': 'file:///secret'},
                      {'op': 'configure', 'network': True}):
            with self.subTest(frame=frame), self.assertRaises(IsolationError):
                self.broker.handle(frame)
        self.assertFalse(list((self.store.directory(other['id'])).glob('quarantine/*')))
        self.client.complete.assert_not_called()

    def test_credentials_cannot_leak_through_provider_exception(self):
        self.client.complete.side_effect = RuntimeError('Bearer secret-test-key')
        with self.assertRaises(IsolationError) as error:
            self.broker.handle({'op': 'infer', 'messages': [{'role': 'user', 'content': 'test'}]})
        self.assertNotIn('secret-test-key', str(error.exception))

    def test_output_cutoff_discards_partial_calls_and_returns_only_a_fixed_marker(self):
        from controller.providers import ProviderError
        self.client.complete.side_effect = ProviderError('Bearer secret-test-key',
            response={'raw_content': 'secret-test-key', 'tool_calls': [{'unsafe': True}]}, category='cutoff')
        frame = {'op': 'infer', 'messages': [{'role': 'user', 'content': 'test'}]}
        value = self.broker.handle(frame)
        self.assertEqual(value, {'content': '', 'provider_error': 'cutoff'})
        self.assertNotIn('secret-test-key', json.dumps(value))
        self.assertNotIn('error_category', self.session)
        self.assertEqual(self.broker.requests, 1)
        self.broker.request_limit = 1
        with self.assertRaises(IsolationError):
            self.broker.handle(frame)
        self.assertEqual(self.client.complete.call_count, 1)

    def test_request_ceiling_accounts_for_each_response_repair_and_is_host_owned(self):
        broker = Broker(self.store, self.session, self.client,
                        {**self.settings.values, 'max_steps': 3, 'response_retries': 999}, self.cancel)
        self.assertEqual(broker.request_limit, 12)
        broker = Broker(self.store, self.session, self.client,
                        {**self.settings.values, 'max_steps': 999, 'response_retries': 999}, self.cancel)
        self.assertEqual(broker.request_limit, 603)

    def test_host_identity_and_policy_cannot_be_changed_by_guest_state(self):
        original = {key: self.session[key] for key in ('id', 'workspace', 'provider', 'task')}
        state = dict(self.session, workspace='C:/', id='f'*32, provider='hosted', task='changed',
                     terminal=True, base_url='file:///secret')
        self.broker.handle({'op': 'state', 'session': state})
        self.assertEqual({key: self.session[key] for key in original}, original)
        self.assertNotIn('terminal', self.session)
        self.assertNotIn('base_url', self.session)

    def test_history_deltas_reconstruct_validated_state_without_changing_host_policy(self):
        metadata = {'status': 'running', 'activity': 'Checking', 'steps': 1, 'runs': 1,
                    'workspace': 'C:/', 'id': 'f' * 32, 'provider': 'hosted', 'terminal': True}
        initial = {'messages': {'prefix': 0, 'items': [{'role': 'user', 'content': 'Keep this request.'}]},
                   'feed': {'prefix': 0, 'items': [{'id': 'first', 'kind': 'user', 'text': 'Keep this request.'}]}}
        identity = {name: self.session[name] for name in ('id', 'provider', 'workspace', 'task')}
        self.broker.handle({'op': 'state', 'session': metadata, 'changes': initial})
        changes = {'messages': {'prefix': 1, 'items': [{'role': 'assistant', 'content': 'Done'}]},
                   'feed': {'prefix': 1, 'items': [{'id': 'second', 'kind': 'assistant', 'text': 'Done'}]}}
        self.broker.handle({'op': 'state', 'session': metadata, 'changes': changes})
        self.assertEqual([item['content'] for item in self.session['messages']], ['Keep this request.', 'Done'])
        self.assertEqual([item['id'] for item in self.session['feed']], ['first', 'second'])
        self.assertEqual({name: self.session[name] for name in identity}, identity)
        self.assertNotIn('terminal', self.session)
        changes['messages'] = {'prefix': 1, 'items': [{'role': 'assistant', 'content': 'Corrected'}]}
        changes['feed'] = {'prefix': 1, 'items': [{'id': 'second', 'kind': 'assistant', 'text': 'Corrected'}]}
        self.broker.handle({'op': 'state', 'session': metadata, 'changes': changes})
        self.assertEqual(self.session['messages'][-1]['content'], 'Corrected')

    def test_invalid_history_deltas_and_oversized_reconstructed_state_are_rejected_atomically(self):
        metadata = {'status': 'running', 'steps': 0, 'runs': 1}
        valid = {'messages': {'prefix': 0, 'items': []}, 'feed': {'prefix': 0, 'items': []}}
        bad = [None, {}, {**valid, 'extra': {}},
               {**valid, 'messages': {'prefix': True, 'items': []}},
               {**valid, 'messages': {'prefix': -1, 'items': []}},
               {**valid, 'messages': {'prefix': 1, 'items': []}},
               {**valid, 'messages': {'prefix': 0, 'items': {}}},
               {**valid, 'messages': {'prefix': 0, 'items': [{'role': 'invalid', 'content': 'bad'}]}},
               {**valid, 'messages': {'prefix': 0, 'items': [{'role': 'user', 'content': 'x'}] * 2001}},
               {**valid, 'messages': {'prefix': 0, 'items': [{'role': 'user', 'content': 'x' * 1500000}]}}]
        for changes in bad:
            with self.subTest(changes_type=type(changes).__name__), self.assertRaises(IsolationError):
                self.broker.handle({'op': 'state', 'session': metadata, 'changes': changes})
            self.assertEqual(self.session['messages'], [])
            self.assertEqual(self.session['feed'], [])

    def test_bad_display_state_cannot_break_host_stop_controls(self):
        value = {**self.session, 'status': 'completed'}
        self.broker.handle({'op': 'state', 'session': value})
        self.assertEqual(self.session['status'], 'running')
        self.assertEqual(self.broker.last_status, 'completed')
        for name, data in [('feed', [None]), ('messages', [{'role': 'user', 'content': {}}])]:
            with self.assertRaises(IsolationError):
                self.broker.handle({'op': 'state', 'session': {**value, name: data}})
        duplicate = {'id': 'same', 'kind': 'notice', 'text': 'test'}
        with self.assertRaises(IsolationError):
            self.broker.handle({'op': 'state', 'session': {**value, 'feed': [duplicate, duplicate]}})

    def test_oversized_file_invalid_manifest_and_request_quota(self):
        with patch('controller.artifacts.MAX_FILE', 2):
            with self.assertRaises(IsolationError):
                self.broker.handle({'op': 'file', 'path': 'x', 'data': base64.b64encode(b'123').decode()})
        for paths in (['missing'], ['x', 'x'], '../x'):
            with self.assertRaises(IsolationError):
                self.broker.handle({'op': 'checkpoint', 'paths': paths})
        self.broker.request_limit = 1
        self.client.complete.return_value = {'content': '{}'}
        frame = {'op': 'infer', 'messages': [{'role': 'user', 'content': 'test'}]}
        self.broker.handle(frame)
        with self.assertRaises(IsolationError):
            self.broker.handle(frame)
        self.assertEqual(self.client.complete.call_count, 1)

    def test_cancel_prevents_late_model_calls_and_exports(self):
        self.cancel.set()
        for frame in ({'op': 'infer', 'messages': [{'role': 'user', 'content': 'test'}]},
                      {'op': 'file', 'path': 'late.txt', 'data': 'eA=='}):
            with self.assertRaises(Cancelled):
                self.broker.handle(frame)
        self.client.complete.assert_not_called()
        self.assertEqual(list(self.broker.artifacts.root.glob('*.blob')), [])

    def test_native_guest_entry_cannot_run_accidentally_on_host(self):
        from autoproteus.agent import Agent
        with patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            Agent(ROOT, self.store, self.settings).start(self.session)

    def test_persisted_workspace_metadata_cannot_redirect_host_reads(self):
        expected = self.store.directory(self.session['id']) / 'workspace'
        value = {**self.session, 'workspace': str(self.root / 'outside')}
        atomic_json(self.store.directory(self.session['id']) / 'session.json', value)
        restored = Store(self.store.root).get(self.session['id'])
        self.assertEqual(Path(restored['workspace']), expected)

    @unittest.skipUnless(os.name == 'nt', 'Windows cross-process VM lease')
    def test_vm_lease_is_exclusive_cancellable_and_released_on_close(self):
        import time
        first, second = VMLease(self.root), VMLease(self.root)
        cancel = threading.Event()
        first.acquire(cancel, time.monotonic() + 3)
        acquired = threading.Event()
        stopped = threading.Event()
        def wait():
            try:
                second.acquire(cancel, time.monotonic() + 3)
                acquired.set()
            except Cancelled:
                stopped.set()
            finally:
                second.close()
        worker = threading.Thread(target=wait)
        try:
            worker.start()
            self.assertFalse(acquired.wait(.2))
            cancel.set(); worker.join(timeout=2)
            self.assertTrue(stopped.is_set())
        finally:
            first.close(); second.close()
        fresh = VMLease(self.root)
        fresh.acquire(threading.Event(), time.monotonic() + 2)
        fresh.close()


if __name__ == '__main__':
    unittest.main()
