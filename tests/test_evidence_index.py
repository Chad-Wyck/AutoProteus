import importlib.util
import json
from pathlib import Path
import unittest

from test_seed import temporary_directory

spec = importlib.util.spec_from_file_location('evidence_index', Path(__file__).resolve().parents[1] / 'evaluations/evidence_index.py')
index = importlib.util.module_from_spec(spec); spec.loader.exec_module(index)


class EvidenceIndexTests(unittest.TestCase):
    def test_backfill_is_idempotent_searchable_and_preserves_changed_report_history(self):
        with temporary_directory() as directory:
            root = Path(directory); folder = root / 'evaluations'; folder.mkdir()
            path = folder / 'seed-example-findings.md'
            path.write_text('# Saved study\n\nQwen failed its boundary check.\n', encoding='utf-8')
            (folder / 'seed-example-results.json').write_text('{"passed": false}')
            self.assertEqual(len(index.backfill(root)), 1)
            target = folder / 'experiment-index.jsonl'; first = target.read_bytes()
            self.assertEqual(index.backfill(root), []); self.assertEqual(target.read_bytes(), first)
            result = index.search('Qwen boundary', target)
            self.assertEqual(result[0]['status'], 'historical_not_regraded')
            path.write_text('# Saved study\n\nClarified original result.', encoding='utf-8')
            self.assertEqual(len(index.backfill(root)), 1)
            self.assertTrue(target.read_bytes().startswith(first))
            self.assertEqual(len(index.records(target)), 2)

    def test_invalid_old_index_is_never_overwritten(self):
        with temporary_directory() as directory:
            root = Path(directory); folder = root / 'evaluations'; folder.mkdir()
            target = folder / 'experiment-index.jsonl'; target.write_text('partial {')
            (folder / 'x-findings.md').write_text('# Evidence')
            with self.assertRaises(ValueError): index.backfill(root)
            self.assertEqual(target.read_text(), 'partial {')
