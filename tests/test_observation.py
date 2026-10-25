import json
from pathlib import Path
import threading
import unittest

from controller.inference_history import InferenceHistory
from controller.observation import Observer
from controller.storage import Store
from test_seed import temporary_directory


class ObserverTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / 'sessions')
        self.session = self.store.create('Active owner', 'demo', 'fixture')
        self.session['status'] = 'running'; self.store.save(self.session)
        self.observer = Observer(self.store)

    def test_observation_cannot_recover_mutate_or_schedule_active_work(self):
        root = self.store.directory(self.session['id'])
        before = {p.name: p.read_bytes() for p in root.glob('*') if p.is_file()}
        revision = self.store.revision
        view = self.observer.session(self.session['id'])
        view['status'] = 'completed'; view['feed'].append({'text': 'foreign'})
        self.observer.timeline(self.session['id'])
        self.assertEqual(self.session['status'], 'running')
        self.assertEqual(self.session['feed'], [])
        self.assertEqual(self.store.revision, revision)
        self.assertEqual(before, {p.name: p.read_bytes() for p in root.glob('*') if p.is_file()})
        for name in ('save', 'create', 'start', 'resume', 'stop', 'cancel', 'enqueue', 'event'):
            self.assertFalse(hasattr(self.observer, name))

    def test_active_owner_can_save_while_observer_reads_without_replace_interference(self):
        failures = []
        def write():
            try:
                for i in range(25):
                    with self.store.lock:
                        self.session['steps'] = i; self.store.save(self.session)
            except BaseException as error: failures.append(error)
        worker = threading.Thread(target=write); worker.start()
        for _ in range(25):
            self.observer.session(self.session['id']); self.observer.timeline(self.session['id'])
        worker.join(10)
        self.assertFalse(worker.is_alive()); self.assertEqual(failures, [])
        self.assertEqual(self.session['status'], 'running')

    def test_evidence_pages_validate_offsets_and_never_invent_missing_records(self):
        for i in range(4): self.store.event(self.session, 'fixture', {'index': i})
        first = self.observer.timeline(self.session['id'], limit=2)
        second = self.observer.timeline(self.session['id'], first['next_offset'], limit=100)
        self.assertEqual(len(first['events']) + len(second['events']), 5)
        with self.assertRaises(ValueError): self.observer.timeline(self.session['id'], 1)
        path = self.store.directory(self.session['id']) / 'events.jsonl'
        with path.open('ab') as stream: stream.write(b'{"unfinished":')
        tail = self.observer.timeline(self.session['id'], second['next_offset'])
        self.assertTrue(tail['incomplete_tail']); self.assertEqual(tail['events'], [])

    def test_blobs_are_inert_identity_checked_and_path_bounded(self):
        value = {'instructions': [{'role': 'system', 'content': '<script>bad()</script>'}], 'tools': []}
        key = InferenceHistory(self.store, self.session, {}).blob(value)
        self.assertEqual(self.observer.blob(self.session['id'], key)['value'], value)
        for bad in ('../session', 'A' * 64, ''):
            with self.assertRaises(ValueError): self.observer.blob(self.session['id'], bad)
        path = self.store.directory(self.session['id']) / 'inference' / (key + '.json')
        path.write_text(json.dumps({'changed': True}))
        with self.assertRaisesRegex(ValueError, 'identity'): self.observer.blob(self.session['id'], key)


if __name__ == '__main__': unittest.main()
