"""Durable outcomes and generated checkpoint/recovery sequences; no models."""
import base64
import copy
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from controller.artifacts import Artifacts
from controller.interactions import Operations
from controller.storage import Store, PersistenceError, atomic_json
from test_seed import temporary_directory


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'sessions')
        self.session = self.store.create('Keep committed work', 'demo', 'fixture')

    def snapshot(self):
        return json.loads((self.store.directory(self.session['id']) / 'session.json').read_text(encoding='utf-8'))

    def test_rejected_replace_restores_the_committed_snapshot_and_live_view(self):
        previous = self.snapshot()
        self.session['title'] = 'Unsaved title'
        with patch('controller.storage.os.replace', side_effect=OSError('fixture replace failure')):
            with self.assertRaises(PersistenceError) as raised:
                self.store.save(self.session)
        self.assertIs(raised.exception.committed, False)
        self.assertEqual(self.snapshot(), previous)
        self.assertEqual(self.session, previous)
        self.assertFalse(self.store.view(self.session['id'])['storage_warning']['snapshot_committed'])
        self.assertEqual(list(self.store.directory(self.session['id']).glob('*.tmp-*')), [])

    def test_error_after_replacement_does_not_roll_back_a_committed_snapshot(self):
        original = atomic_json
        def write_then_fail(path, value):
            original(path, value)
            raise OSError('failure after durable replacement')
        self.session['title'] = 'Committed title'
        with patch('controller.storage.atomic_json', side_effect=write_then_fail):
            with self.assertRaises(PersistenceError) as raised:
                self.store.save(self.session)
        self.assertIs(raised.exception.committed, True)
        self.assertEqual(self.snapshot()['title'], 'Committed title')
        self.assertEqual(self.store.public(self.session['id'])['title'], 'Committed title')

    def test_summary_failure_preserves_the_new_checkpoint_and_rebuilds_index(self):
        files = Artifacts(self.store, self.session)
        files.put('result.txt', base64.b64encode(b'new committed bytes').decode())
        original = atomic_json
        def fail_summary(path, value):
            if path.name == 'summary.json':
                raise OSError('fixture summary failure')
            original(path, value)
        with patch('controller.storage.atomic_json', side_effect=fail_summary):
            with self.assertRaises(PersistenceError) as raised:
                files.checkpoint(['result.txt'])
        self.assertIs(raised.exception.committed, True)
        reopened = Store(self.store.root)
        saved = reopened.get(self.session['id'])
        self.assertEqual(Artifacts(reopened, saved).read('result.txt'), b'new committed bytes')
        self.assertEqual(reopened.page()['items'][0]['_revision'], saved['_revision'])

    def test_journal_failure_after_receipt_save_keeps_uncertainty_without_replay(self):
        operations = Operations(self.store, self.session)
        operations.event('action_started', {'tool': 'run_command', 'arguments': {'command': 'effect'}}, 'start')
        with patch.object(self.store, 'event', side_effect=PersistenceError('journal', None)):
            with self.assertRaises(PersistenceError):
                operations.event('action_result', {'action': {'tool': 'run_command', 'arguments': {'command': 'effect'}},
                    'ok': True, 'result': {'done': True}}, 'result')
        restored = Store(self.store.root).get(self.session['id'])
        self.assertEqual(restored['operation_receipts'][-1]['status'], 'result_reported')
        self.assertIn('never automatically replayed', Operations(self.store, restored).notice())
        with patch('controller.storage.os.fsync', side_effect=OSError('fixture journal sync')):
            with self.assertRaises(PersistenceError) as raised:
                self.store.event(self.session, 'fixture', {})
        self.assertIsNone(raised.exception.committed)

    def test_generated_lifecycle_sequences_restore_exact_committed_files(self):
        # Deterministic generated schedules exercise combinations beyond the
        # individual historical bug fixtures. No generated program is executed.
        for seed in range(12):
            rng = random.Random(seed)
            session = self.store.create('Schedule ' + str(seed), 'demo', 'fixture')
            store = self.store; files = Artifacts(store, session)
            staged, committed, receipts = {}, {}, []
            for step in range(28):
                operation = rng.choice(('write', 'delete', 'checkpoint', 'interrupt', 'receipt', 'failed_save'))
                if operation == 'write':
                    name, value = 'file' + str(rng.randrange(3)) + '.txt', ('café-' + str(step)).encode()
                    files.put(name, base64.b64encode(value).decode()); staged[name] = value
                elif operation == 'delete':
                    staged.pop('file' + str(rng.randrange(3)) + '.txt', None)
                elif operation == 'checkpoint':
                    files.checkpoint(sorted(staged)); committed = dict(staged)
                elif operation == 'receipt':
                    operations = Operations(store, session)
                    operations.event('action_started', {'tool': 'fixture', 'arguments': {'step': step}}, str(step))
                    receipts = copy.deepcopy(session['operation_receipts'])
                elif operation == 'failed_save':
                    before = json.loads((store.directory(session['id']) / 'session.json').read_text())
                    session['title'] = 'must not survive rejected save'
                    with patch('controller.storage.os.replace', side_effect=OSError('generated rejection')):
                        with self.assertRaises(PersistenceError): store.save(session)
                    self.assertEqual(session, before)
                else:
                    session['status'] = 'running'; store.save(session)
                    store = Store(store.root); session = store.get(session['id'])
                    self.assertEqual(session['status'], 'interrupted')
                    files = Artifacts(store, session)
                    staged = dict(committed)
                    self.assertEqual(session.get('operation_receipts', []), receipts)
                saved = json.loads((store.directory(session['id']) / 'session.json').read_text())
                self.assertEqual(set(saved.get('artifacts', {})), set(committed))
                for name, value in committed.items():
                    self.assertEqual(files.read(name), value)

    def test_crash_between_file_commit_and_conversation_save_preserves_uncertain_receipt(self):
        operations = Operations(self.store, self.session)
        action = {'tool': 'write_file', 'arguments': {'path': 'result.txt', 'content': 'committed'}}
        operations.event('action_started', action, 'start')
        operations.event('action_result', {'action': action, 'ok': True, 'result': {'bytes': 9}}, 'result')
        files = Artifacts(self.store, self.session)
        files.put('result.txt', base64.b64encode(b'committed').decode()); files.checkpoint(['result.txt'])
        # Process stops before the receipt checkpoint or guest history arrives.
        restored = Store(self.store.root); session = restored.get(self.session['id'])
        self.assertEqual(Artifacts(restored, session).read('result.txt'), b'committed')
        recovered = Operations(restored, session); recovered.checkpoint()
        self.assertEqual(recovered.current()['status'], 'result_reported')
        self.assertEqual(session['messages'], [])
        self.assertIn('Inspect current files', recovered.notice())


if __name__ == '__main__':
    unittest.main()
