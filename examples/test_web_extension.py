"""Offline template: copy to harness/tests/test_YOUR_TOOL.py and adapt assertions.

Run from the task workspace: python3 harness/examples/test_web_extension.py
This tests fixture handling only; it does not verify connectivity or host policy.
"""
import base64
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autoproteus.tools import Workspace


class WebExtensionExample(unittest.TestCase):
    def test_fixture_response(self):
        expected = b'{"title":"Research example"}\n'
        calls = []

        def request(arguments):
            calls.append(arguments)
            self.assertEqual(arguments['url'], 'https://example.invalid/page')
            return {'url': arguments['url'], 'status': 200,
                    'headers': {'content-type': 'application/json'},
                    'bytes': len(expected), 'data': base64.b64encode(expected).decode()}

        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            workspace = Workspace(Path(directory))
            with patch.dict(sys.modules, {'autoproteus_web': SimpleNamespace(request=request)}):
                # Replace tool/arguments/assertions with the extension's contract.
                result = workspace.execute('web_request', {
                    'url': 'https://example.invalid/page', 'path': 'saved.json'})
            self.assertEqual((workspace.root / 'saved.json').read_bytes(), expected)
            self.assertEqual(result['status'], 200)
            self.assertEqual(len(calls), 1)


if __name__ == '__main__':
    unittest.main()
