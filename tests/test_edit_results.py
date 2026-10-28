"""Current edit feedback checks, outside the shared starter regression contract."""
from pathlib import Path
import unittest
from unittest.mock import patch

from autoproteus.tools import Workspace
from test_seed import temporary_directory


class EditResultTests(unittest.TestCase):
    def test_identical_edit_does_not_write_and_keeps_match_checks(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            path = Path(directory) / 'text.txt'
            raw = '\ufeff# café\r\n猫 = 1\r\n'.encode('utf-8')
            path.write_bytes(raw)
            modified = path.stat().st_mtime_ns
            with patch.object(Path, 'write_bytes', side_effect=AssertionError('An unchanged edit must not write')):
                for _ in range(3):
                    result = workspace.execute('edit_file', {'path': 'text.txt', 'old_text': '猫 = 1', 'new_text': '猫 = 1'})
                    self.assertFalse(result['changed'])
                    self.assertEqual(result['replacements'], 0)
                    self.assertEqual(result['bytes'], len(raw))
                    self.assertIn('No change made', result['message'])
                with self.assertRaisesRegex(ValueError, 'not found'):
                    workspace.execute('edit_file', {'path': 'text.txt', 'old_text': 'absent', 'new_text': 'absent'})
            self.assertEqual(path.read_bytes(), raw)
            self.assertEqual(path.stat().st_mtime_ns, modified)
            path.write_text('same same', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'ambiguous'):
                workspace.execute('edit_file', {'path': 'text.txt', 'old_text': 'same', 'new_text': 'same'})

    def test_real_edit_reports_a_change(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'text.txt'; path.write_bytes(b'old')
            result = Workspace(Path(directory)).execute('edit_file', {'path': 'text.txt', 'old_text': 'old', 'new_text': 'new'})
            self.assertTrue(result['changed'])
            self.assertEqual(result['replacements'], 1)
            self.assertEqual(path.read_bytes(), b'new')
