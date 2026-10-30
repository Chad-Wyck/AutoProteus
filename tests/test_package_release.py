"""Tests for the release packager (evaluations/package-release.py)."""
import hashlib
import importlib.util
import io
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'package_release', ROOT / 'evaluations/package-release.py')
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)

CHANGELOG = """# Release notes

Versions use `major.minor.patch`.

## 0.14.10

- A different version that must not match 0.14.1.

## 0.14.1

- Yield idle VMs.
- Portable research studies.

## 0.14.0

- Local model UX.
"""


class ChangelogTests(unittest.TestCase):
    def test_extracts_exact_section(self):
        section = packager.changelog_section(CHANGELOG, '0.14.1')
        self.assertIn('Yield idle VMs.', section)
        self.assertNotIn('different version', section)
        self.assertNotIn('Local model UX', section)

    def test_missing_version_refused(self):
        with self.assertRaises(ValueError):
            packager.changelog_section(CHANGELOG, '0.9.9')

    def test_notes_draft(self):
        notes = packager.draft_notes('0.14.1',
                                     packager.changelog_section(CHANGELOG, '0.14.1'))
        self.assertTrue(notes.startswith('# AutoProteus v0.14.1'))
        self.assertIn('Portable research studies.', notes)


def make_repo(directory):
    root = Path(directory)
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', 'config', 'user.email', 'test@example.invalid'], cwd=root, check=True)
    subprocess.run(['git', 'config', 'user.name', 'Test'], cwd=root, check=True)
    (root / 'b.txt').write_text('second\n')
    (root / 'a.txt').write_text('first\n')
    subprocess.run(['git', 'add', '-A'], cwd=root, check=True)
    subprocess.run(['git', 'commit', '-q', '-m', 'fixture'], cwd=root, check=True)
    return root


class ZipTests(unittest.TestCase):
    def test_deterministic_and_sorted(self):
        parent = ROOT / '.data/test-tmp'
        parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=parent) as tmp:
            repo = make_repo(tmp)
            first = packager.build_release_zip(repo, 'HEAD')
            second = packager.build_release_zip(repo, 'HEAD')
            self.assertEqual(hashlib.sha256(first).hexdigest(),
                             hashlib.sha256(second).hexdigest())
            with zipfile.ZipFile(io.BytesIO(first)) as archive:
                self.assertEqual(archive.namelist(), ['a.txt', 'b.txt'])
                self.assertEqual(archive.read('a.txt'), b'first\n')
                for info in archive.infolist():
                    self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))

    def test_tag_refuses_duplicate(self):
        parent = ROOT / '.data/test-tmp'
        parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=parent) as tmp:
            repo = make_repo(tmp)
            self.assertEqual(packager.create_tag(repo, '1.2.3'), 'v1.2.3')
            with self.assertRaises(ValueError):
                packager.create_tag(repo, '1.2.3')

    def test_tag_lands_on_ref_not_head(self):
        # Chad's PR #5 reproduction: --tag --ref <older commit> must tag
        # that commit, not HEAD.
        parent = ROOT / '.data/test-tmp'
        parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=parent) as tmp:
            repo = make_repo(tmp)
            first = packager.resolve_commit(repo, 'HEAD')
            (repo / 'a.txt').write_text('changed\n')
            subprocess.run(['git', 'commit', '-q', '-a', '-m', 'second'],
                           cwd=repo, check=True)
            self.assertNotEqual(first, packager.resolve_commit(repo, 'HEAD'))
            packager.create_tag(repo, '1.2.3', ref=first)
            tagged = subprocess.run(
                ['git', 'rev-list', '-n', '1', 'v1.2.3'], cwd=repo,
                capture_output=True, check=True).stdout.decode().strip()
            self.assertEqual(tagged, first)

    def test_notes_come_from_ref_not_worktree(self):
        # Notes must be read from the packaged commit even when the
        # working-tree CHANGELOG.md has been modified since.
        parent = ROOT / '.data/test-tmp'
        parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=parent) as tmp:
            repo = make_repo(tmp)
            (repo / 'CHANGELOG.md').write_text(CHANGELOG)
            subprocess.run(['git', 'add', '-A'], cwd=repo, check=True)
            subprocess.run(['git', 'commit', '-q', '-m', 'changelog'],
                           cwd=repo, check=True)
            (repo / 'CHANGELOG.md').write_text(
                CHANGELOG.replace('Yield idle VMs.', 'WORKTREE EDIT'))
            section = packager.changelog_section_at_ref(repo, 'HEAD', '0.14.1')
            self.assertIn('Yield idle VMs.', section)
            self.assertNotIn('WORKTREE EDIT', section)


if __name__ == '__main__':
    unittest.main()
