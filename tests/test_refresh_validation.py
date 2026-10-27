"""Tests for the validation-refresh bundler (evaluations/refresh-validation.py)."""
import hashlib
import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'refresh_validation', ROOT / 'evaluations/refresh-validation.py')
refresh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refresh)

OK_LOG = """dots and fixture noise
----------------------------------------------------------------------
Ran 323 tests in 42.344s

OK (skipped=46)
"""
FAILED_LOG = """----------------------------------------------------------------------
Ran 10 tests in 1.5s

FAILED (failures=2, errors=1, skipped=3)
"""
PLAIN_OK_LOG = "Ran 5 tests in 0.25s\n\nOK\n"


class SummarizeTests(unittest.TestCase):
    def test_ok_with_skips(self):
        counts = refresh.summarize_unittest_log(OK_LOG)
        self.assertEqual(counts, {'discovered': 323, 'passed': 277, 'failed': 0,
                                  'errors': 0, 'skipped': 46, 'seconds': 42.344})

    def test_plain_ok(self):
        counts = refresh.summarize_unittest_log(PLAIN_OK_LOG)
        self.assertEqual(counts['passed'], 5)
        self.assertEqual(counts['skipped'], 0)

    def test_failed(self):
        counts = refresh.summarize_unittest_log(FAILED_LOG)
        self.assertEqual(counts['passed'], 4)
        self.assertEqual(counts['failed'], 2)
        self.assertEqual(counts['errors'], 1)

    def test_missing_summary_refused(self):
        with self.assertRaises(ValueError):
            refresh.summarize_unittest_log('crashed before running anything')

    def test_truncated_log_refused(self):
        with self.assertRaises(ValueError):
            refresh.summarize_unittest_log('Ran 3 tests in 0.1s\n')


class BundleTests(unittest.TestCase):
    def build(self):
        ordinary = refresh.summarize_unittest_log(OK_LOG)
        log = OK_LOG.encode()
        return refresh.build_results('9.9.9', 'a' * 40, ordinary,
                                     refresh.sha256_bytes(log))

    def test_results_shape(self):
        results = self.build()
        self.assertEqual(results['schema_version'], 1)
        self.assertEqual(results['release'], 'v9.9.9')
        self.assertEqual(results['ordinary']['passed'], 277)
        self.assertIsNone(results['real_vm'])
        self.assertIsNone(results['model_trials']['qualification_passed'])
        self.assertEqual(len(results['starter_source_sha256']), 64)

    def test_write_bundle_and_manifest(self):
        results = self.build()
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'v9.9.9'
            refresh.write_bundle(out, OK_LOG.encode(), results)
            names = sorted(p.name for p in out.iterdir())
            self.assertEqual(names, ['SHA256SUMS', 'ordinary-tests.log', 'results.json'])
            manifest = {}
            for line in (out / 'SHA256SUMS').read_text().splitlines():
                digest, name = line.split('  ')
                manifest[name] = digest
                actual = hashlib.sha256((out / name).read_bytes()).hexdigest()
                self.assertEqual(actual, digest)
            stored = json.loads((out / 'results.json').read_text())
            self.assertEqual(stored['ordinary']['log_sha256'],
                             manifest['ordinary-tests.log'])

    def test_refuses_overwrite(self):
        results = self.build()
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / 'v9.9.9'
            refresh.write_bundle(out, OK_LOG.encode(), results)
            with self.assertRaises(ValueError):
                refresh.write_bundle(out, OK_LOG.encode(), results)

    def test_page_renders_honest_gaps(self):
        results = self.build()
        page = refresh.render_page('9.9.9', 'a' * 40, '1 January 2027',
                                   results, 'docs/validation/v9.9.9')
        self.assertIn('**v9.9.9**', page)
        self.assertIn('not re-run', page)
        self.assertIn('323', page)
        self.assertIn('docs/validation/v9.9.9/results.json', page)


if __name__ == '__main__':
    unittest.main()
