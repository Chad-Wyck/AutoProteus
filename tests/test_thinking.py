import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from controller.storage import Store
from controller.thinking import Thinking
from test_seed import temporary_directory


class ThinkingTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name)/'sessions')
        self.session = self.store.create('Preview reasoning', 'ollama', 'fixture')
        self.store.feed(self.session, 'user', 'Preview reasoning')
        self.cancel = threading.Event()

    def test_preview_is_separate_from_history_and_streams_before_completion(self):
        with patch('controller.thinking.time.monotonic', side_effect=[0, 1, 1, 1, 2, 2]):
            thinking = Thinking(self.store, self.session, self.cancel)
            thinking.thinking('Inspect the input.')
            view = self.store.view(self.session['id'])
            self.assertEqual(view['thinking_spans'][-1]['state'], 'running')
            self.assertEqual(view['thinking_spans'][-1]['text'], 'Inspect the input.')
            thinking.finish('completed')
        self.assertEqual(self.session['thinking_spans'][-1]['after'], self.session['feed'][0]['id'])
        self.assertEqual(self.session['messages'], [])
        self.assertEqual(len(self.session['feed']), 1)
        self.assertEqual(self.session['thinking_spans'][-1]['state'], 'completed')

    def test_cancel_and_late_transport_callbacks_cannot_change_a_finished_preview(self):
        thinking = Thinking(self.store, self.session, self.cancel, key='private-key')
        thinking.thinking('Use private-key safely.')
        thinking.finish('interrupted')
        before = dict(self.session['thinking_spans'][-1])
        thinking.thinking('Late content must be ignored.')
        self.assertEqual(self.session['thinking_spans'][-1], before)
        self.assertNotIn('private-key', before['text'])
        self.assertIn('[REDACTED]', before['text'])

    def test_large_reasoning_previews_remain_bounded(self):
        for _ in range(6):
            thinking = Thinking(self.store, self.session, self.cancel)
            thinking.thinking('x'*70000)
            thinking.finish('completed')
        rows = self.session['thinking_spans']
        self.assertLessEqual(sum(len(row['text']) for row in rows), 256000)
        self.assertTrue(all(len(row['text']) <= 64000 for row in rows))
        self.assertTrue(rows[-1]['shortened'])

    def test_recovery_stops_a_stale_thinking_spinner(self):
        Thinking(self.store, self.session, self.cancel)
        self.session['status'] = 'running'; self.store.save(self.session)
        recovered = Store(self.store.root).get(self.session['id'])
        self.assertEqual(recovered['thinking_spans'][-1]['state'], 'interrupted')
