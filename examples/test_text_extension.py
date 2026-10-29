"""Runnable test patterns to adapt to a new text tool; run from harness/.

    python3 -m unittest discover -s examples -p test_text_extension.py

Replace the existing tool calls with your registered tool and its public contract.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from autoproteus.tools import Workspace


class TextExtensionPatterns(unittest.TestCase):
    def test_success_checks_return_value_and_exact_saved_bytes(self):
        with TemporaryDirectory() as directory:
            workspace = Workspace(Path(directory))
            text = 'café, 猫\r\n'
            result = workspace.execute('write_file', {'path': 'example.txt', 'content': text})
            self.assertEqual(result['path'], 'example.txt')
            self.assertEqual(result['bytes'], len(text.encode('utf-8')))
            self.assertEqual((Path(directory) / 'example.txt').read_bytes(), text.encode('utf-8'))
            self.assertEqual(workspace.execute('read_file', {'path': 'example.txt'})['content'], text)

    def test_rejection_raises_and_does_not_return_an_error_dictionary(self):
        with TemporaryDirectory() as directory:
            workspace = Workspace(Path(directory))
            # Accept either error unless the new tool's contract specifies one.
            with self.assertRaises((ValueError, OSError)):
                workspace.execute('read_file', {'path': 'missing.txt'})

    def test_processing_and_inspection_have_different_limits(self):
        with TemporaryDirectory() as directory:
            workspace = Workspace(Path(directory))
            path = Path(directory) / 'large.txt'
            text = '猫' * 100000
            self.assertEqual(len(text), 100000)
            self.assertEqual(len(text.encode('utf-8')), 300000)
            # Construct large/invalid fixtures directly in this disposable guest
            # directory, so the fixture writer's limit cannot mask the test.
            path.write_bytes(text.encode('utf-8'))
            self.assertEqual(workspace.read_text('large.txt'), text)
            with self.assertRaises(ValueError):
                workspace.execute('read_file', {'path': 'large.txt'})
            path.write_bytes((text + 'x').encode('utf-8'))
            with self.assertRaises(ValueError):
                workspace.read_text('large.txt')


if __name__ == '__main__':
    unittest.main()
