"""Regression checks for saved work, complete budgets and managed runtimes."""
import base64
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import Mock, patch

from controller.compatibility import check_protocol
from controller.config import DEFAULTS
from controller.integrity import record_runtime, verify_runtime
from controller.isolation import Artifacts
from controller.providers import ModelClient, ProviderError
from controller.server import Application
from controller.storage import Store
from test_providers import FakeModelServer
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]


class ReliabilityTests(unittest.TestCase):
    def test_summary_recovers_a_snapshot_saved_before_its_summary(self):
        from controller.storage import atomic_json
        import os
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('Old title', 'demo', 'none')
            path = store.directory(session['id']) / 'session.json'
            session['title'] = 'Recovered title'
            atomic_json(path, session)
            summary_path = path.with_name('summary.json')
            os.utime(summary_path, ns=(1, 1))
            reopened = Store(store.root)
            self.assertEqual(reopened.page()['items'][0]['title'], 'Recovered title')
            self.assertEqual(reopened.sessions, {})

    def test_python_launcher_pin_matches_the_shared_runtime_lock(self):
        pins = json.loads((ROOT / 'controller/managed-runtime-lock.json').read_text(encoding='utf-8'))
        linux = (ROOT / 'launch.sh').read_text(encoding='utf-8')
        self.assertIn(pins['python_linux']['sha256'], linux)
        self.assertIn(pins['python_linux']['url'], linux)

    def test_sessions_load_summaries_then_restore_full_history_only_when_opened(self):
        with temporary_directory() as directory:
            root = Path(directory) / 'sessions'
            store = Store(root)
            sessions = [store.create('Session ' + str(i), 'demo', 'none') for i in range(35)]
            sessions[0]['messages'] = [{'role': 'user', 'content': 'saved history'}]; store.save(sessions[0])
            reopened = Store(root)
            self.assertEqual(reopened.sessions, {})
            page = reopened.page(limit=10)
            self.assertEqual((len(page['items']), page['total']), (10, 35))
            self.assertEqual(reopened.get(sessions[0]['id'])['messages'][0]['content'], 'saved history')
            self.assertEqual(len(reopened.sessions), 1)

    def test_rename_archive_search_delete_and_restore_preserve_files_and_identity(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('Original', 'demo', 'none')
            files = Artifacts(store, session)
            files.put('file.txt', base64.b64encode(b'keep').decode()); files.checkpoint(['file.txt'])
            identifier = session['id']
            store.rename(identifier, 'Reading plan'); store.archive(identifier)
            self.assertEqual(store.page()['total'], 0)
            self.assertEqual(store.page('reading', archived=True)['total'], 1)
            store.delete(identifier)
            self.assertEqual(len(store.trash()), 1)
            with self.assertRaises(ValueError): store.get(identifier)
            store.restore(identifier)
            self.assertEqual(Artifacts(store, store.get(identifier)).read('file.txt'), b'keep')
            self.assertTrue(store.get(identifier)['archived'])
            self.assertEqual(store.trash(), [])
            with self.assertRaises(ValueError): store.restore('../outside')

    def test_incremental_session_view_omits_model_context_and_sends_only_new_feed(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('Task', 'demo', 'none')
            session['messages'] = [{'role': 'user', 'content': 'large private context'}]
            store.feed(session, 'notice', 'first')
            first = store.view(session['id'])
            self.assertNotIn('messages', first)
            self.assertTrue(store.view(session['id'], revision=first['revision'])['unchanged'])
            store.feed(session, 'notice', 'second')
            update = store.view(session['id'], after=first['feed_count'])
            self.assertEqual([item['text'] for item in update['feed']], ['second'])
            self.assertEqual(update['feed_start'], 1)

    def test_managed_runtime_detects_changed_added_and_missing_dependencies(self):
        pin = {'version': 'test', 'sha256': 'a' * 64}
        with temporary_directory() as directory:
            root = Path(directory); (root / 'engine').write_bytes(b'engine'); (root / 'library').write_bytes(b'library')
            record_runtime(root, pin); verify_runtime(root, pin)
            (root / 'library').write_bytes(b'changed')
            with self.assertRaises(ValueError): verify_runtime(root, pin)
            (root / 'library').write_bytes(b'library'); (root / 'added').write_bytes(b'extra')
            with self.assertRaises(ValueError): verify_runtime(root, pin)
            (root / 'added').unlink(); (root / 'library').unlink()
            with self.assertRaises(ValueError): verify_runtime(root, pin)

    def test_provider_checks_the_complete_estimate_before_network_access(self):
        config = {**DEFAULTS, 'provider': 'hosted', 'protocol': 'native', 'context_tokens': 2048, 'response_tokens': 512}
        with patch('controller.providers.urllib.request.urlopen') as network:
            with self.assertRaises(ProviderError) as error:
                ModelClient(config)._complete([{'role': 'user', 'content': 'short'}], threading.Event(), None,
                    tools=[{'type': 'function', 'function': {'name': 'large', 'description': 'é' * 10000}}])
            self.assertEqual(error.exception.category, 'context')
            network.assert_not_called()

    def test_both_protocols_require_a_tool_result_receipt_and_explicit_finish(self):
        for protocol in ('native', 'json'):
            server = FakeModelServer(hosted=True, native=protocol == 'native', diagnostic=True)
            try:
                result = check_protocol({**DEFAULTS, 'provider': 'hosted', 'base_url': server.url, 'protocol': protocol})
                self.assertTrue(result['passed']); self.assertEqual(len(server.payloads), 2)
            finally:
                server.close()
        server = FakeModelServer(hosted=True)
        try:
            with self.assertRaises(ProviderError) as error:
                check_protocol({**DEFAULTS, 'provider': 'hosted', 'base_url': server.url, 'protocol': 'json'})
            self.assertEqual(error.exception.category, 'protocol')
        finally:
            server.close()

    def test_import_is_inert_bounded_and_rejects_an_invalid_batch_before_writing(self):
        with temporary_directory() as directory:
            app = Application(ROOT, data=Path(directory))
            try:
                session = app.store.create('Imports', 'demo', 'none')
                with self.assertRaises(ValueError):
                    app.import_files(session, [{'path': 'valid.txt', 'data': 'eA=='}, {'path': '../outside', 'data': 'eA=='}])
                self.assertNotIn('artifacts', session)
                app.import_files(session, [{'path': 'notes.txt', 'data': base64.b64encode(b'copied bytes').decode()}])
                self.assertEqual(Artifacts(app.store, session).read('notes.txt'), b'copied bytes')
                self.assertFalse((Path(session['workspace']) / 'notes.txt').exists())
                with self.assertRaises(ValueError): app.import_files(session, [{'path': 'harness/seed.py', 'data': 'eA=='}])
            finally:
                app.close()

    def test_admission_uses_actual_worker_liveness_not_the_guest_status(self):
        with temporary_directory() as directory:
            app = Application(ROOT, data=Path(directory))
            try:
                session = app.store.create('Still shutting down', 'demo', 'none')
                session['status'] = 'completed'; app.store.save(session)
                thread = Mock(); thread.is_alive.return_value = True
                app.agent.workers[session['id']] = (threading.Event(), thread)
                self.assertEqual(app.active()['id'], session['id'])
                with self.assertRaises(ValueError): app.ensure_idle()
                self.assertEqual(len(app.store.public()), 1)
            finally:
                app.agent.workers.clear(); app.close()
