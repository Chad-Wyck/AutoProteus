import unittest
from pathlib import Path
from autoproteus.tools import Cancelled, TEXT_CHARACTER_LIMIT, WRITE_LIMIT, Workspace
from test_seed import temporary_directory

class TextHelperTests(unittest.TestCase):
    def test_character_units_crlf_and_exact_unicode_limit(self):
        self.assertEqual(TEXT_CHARACTER_LIMIT, 100000)
        self.assertEqual(WRITE_LIMIT, TEXT_CHARACTER_LIMIT)
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            text = "猫" * 99998 + "\r\n"
            result = workspace.write_text("nested/sample.txt", text)
            self.assertEqual(result["bytes"], len(text.encode()))
            self.assertEqual(workspace.read_text("nested/sample.txt"), text)
            self.assertEqual(workspace.read_text(Path(directory) / "nested/sample.txt"), text)

    def test_rejected_reads_and_writes_preserve_existing_bytes(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            path = Path(directory) / "sample.txt"
            for raw in (("猫" * 100001).encode(), b"\xff"):
                path.write_bytes(raw)
                with self.assertRaises((ValueError, UnicodeError)):
                    workspace.read_text(path)
                self.assertEqual(path.read_bytes(), raw)
            path.write_bytes(b"keep\r\n")
            for content in ("x" * 100001, None, 7, b"bytes"):
                with self.assertRaises(ValueError):
                    workspace.write_text(path, content)
                self.assertEqual(path.read_bytes(), b"keep\r\n")
            for value in ("../outside.txt", "."):
                with self.assertRaises((ValueError, OSError)):
                    workspace.read_text(value)
                with self.assertRaises((ValueError, OSError)):
                    workspace.write_text(value, "bad")

    def test_missing_files_and_cancellation(self):
        with temporary_directory() as directory:
            workspace = Workspace(Path(directory))
            self.assertEqual(workspace.read_text("new/deep.txt", missing_ok=True), "")
            self.assertFalse((Path(directory) / "new").exists())
            with self.assertRaises(FileNotFoundError):
                workspace.read_text("new/deep.txt")
            workspace.cancel.set()
            with self.assertRaises(Cancelled):
                workspace.read_text("new/deep.txt")
            with self.assertRaises(Cancelled):
                workspace.write_text("new/deep.txt", "bad")
            self.assertFalse((Path(directory) / "new/deep.txt").exists())
