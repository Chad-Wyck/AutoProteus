"""Tests for the testing ladder (evaluations/testing_ladder.py)."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'testing_ladder', ROOT / 'evaluations/testing_ladder.py')
ladder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ladder)


class RungShapeTests(unittest.TestCase):
    def test_rungs_ordered_easy_to_hard(self):
        kinds = [rung['kind'] for rung in ladder.RUNGS]
        self.assertEqual(kinds, ['local', 'local', 'local', 'hosted'])

    def test_ids_unique(self):
        ids = [rung['id'] for rung in ladder.RUNGS]
        self.assertEqual(len(ids), len(set(ids)))

    def test_exactly_one_spend_gated_rung_and_it_is_last(self):
        gated = [rung for rung in ladder.RUNGS if rung.get('requires_spend')]
        self.assertEqual(len(gated), 1)
        self.assertIs(gated[0], ladder.RUNGS[-1])

    def test_profiles_carry_no_keys_and_fit_research_rules(self):
        for rung in ladder.RUNGS:
            profile = ladder.profile_for(rung)
            self.assertNotIn('api_key', json.dumps(profile))
            config = profile['config']
            self.assertIn(config['provider'], ('ollama', 'hosted'))
            self.assertLess(config['response_tokens'], config['context_tokens'])
            self.assertFalse(config['internet'])


class GateTests(unittest.TestCase):
    def test_hosted_run_refused_without_spend_approval(self):
        with self.assertRaises(ValueError):
            ladder.ensure_runnable(ladder.RUNGS[-1], 'ready', approve_spend=False)

    def test_local_run_refused_when_not_ready(self):
        with self.assertRaises(ValueError):
            ladder.ensure_runnable(ladder.RUNGS[0], 'endpoint-unreachable')

    def test_ready_local_rung_runnable(self):
        self.assertTrue(ladder.ensure_runnable(ladder.RUNGS[0], 'ready'))


class PreflightTests(unittest.TestCase):
    def test_parse_tags(self):
        payload = json.dumps({'models': [{'name': 'b:1'}, {'name': 'a:2'}, {}]})
        self.assertEqual(ladder.parse_tags(payload), ['a:2', 'b:1'])

    def test_unreachable_endpoint(self):
        rung = ladder.RUNGS[0]
        result = ladder.preflight(rung, probe=lambda url: {
            'reachable': False, 'models': [], 'error': 'connection refused'})
        self.assertEqual(result['status'], 'endpoint-unreachable')

    def test_model_missing(self):
        rung = ladder.RUNGS[0]
        result = ladder.preflight(rung, probe=lambda url: {
            'reachable': True, 'models': ['other:1'], 'error': None})
        self.assertEqual(result['status'], 'model-not-downloaded')

    def test_ready(self):
        rung = ladder.RUNGS[0]
        result = ladder.preflight(rung, probe=lambda url: {
            'reachable': True, 'models': [rung['model']], 'error': None})
        self.assertEqual(result['status'], 'ready')

    def test_hosted_preflight_never_probes(self):
        def forbidden(url):
            raise AssertionError('hosted rung must not be probed')
        result = ladder.preflight(ladder.RUNGS[-1], probe=forbidden)
        self.assertEqual(result['status'], 'spend-gated')


class ReceiptTests(unittest.TestCase):
    def test_receipt_records_phases_verbatim(self):
        phases = {'preflight': {'status': 'endpoint-unreachable', 'detail': 'x'}}
        receipt = ladder.receipt_for(ladder.RUNGS[0], phases)
        self.assertEqual(receipt['kind'], 'testing-ladder-rung')
        self.assertEqual(receipt['phases'], phases)
        self.assertEqual(receipt['model']['model'], ladder.RUNGS[0]['model'])


if __name__ == '__main__':
    unittest.main()
