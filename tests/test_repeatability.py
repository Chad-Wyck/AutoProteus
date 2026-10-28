import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from controller.storage import atomic_json
from test_seed import temporary_directory

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'evaluations'))
import model_plan
from repeatability import repeat_config, freeze_cases, sampling_record


class RepeatabilityTests(unittest.TestCase):
    def test_server_initialization_is_distinct_and_never_claimed_verified(self):
        config = {'sampling_seed': 999}
        plan = {'sampling_seed_mode': 'server-initialized', 'repeatability': {'sampling_seeds': [1, 2]}}
        server = repeat_config(plan, config, 2)
        self.assertNotIn('sampling_seed', server)
        self.assertEqual(server['server_initial_seed'], 2)
        self.assertEqual(repeat_config(plan, server, 1)['server_initial_seed'], 1)
        self.assertEqual(config, {'sampling_seed': 999})
        self.assertFalse(sampling_record(server)['server_initialization_verified'])
        per_request = repeat_config({**plan, 'sampling_seed_mode': 'per-request'}, server, 2)
        self.assertEqual(per_request['sampling_seed'], 2)
        self.assertNotIn('server_initial_seed', per_request)
        for values in ({}, {'sampling_seed': True}, {'server_initial_seed': -1}):
            with self.assertRaises(ValueError):repeat_config({'sampling_seed_mode': 'server-initialized'}, values, 1)
        with self.assertRaises(ValueError):repeat_config({'sampling_seed_mode': 'unknown'}, config, 1)
        self.assertEqual(sampling_record({})['mode'], 'server-default')

    def test_csv_sampling_arms_freeze_matching_tasks_and_distinct_policies_without_inference(self):
        with temporary_directory() as directory:
            root = Path(directory)
            profiles = root / 'profiles.json'
            atomic_json(profiles, [{'id': 'fixture', 'config': {'provider': 'hosted', 'base_url': 'http://127.0.0.1:8080/v1', 'model': 'fixture'}}])
            plans = []
            for mode in ('per-request', 'server-initialized'):
                args = SimpleNamespace(mode='full', output=str(root / mode), profiles=str(profiles), repeats=None,
                    first_only=True, timeout=3600, output_token_budget=65536, sampling_seed_mode=mode,
                    case_pack=str(ROOT / 'evaluations/sampling-csv-cases.json'))
                with patch('builtins.print'):model_plan.prepare(args)
                plans.append(json.loads((root / mode / 'plan.json').read_text()))
            request, server = plans
            for key in ('source_sha256', 'first_use_contracts', 'contracts', 'deadline', 'generated_tokens', 'upgrade_tasks', 'repeats'):
                self.assertEqual(request[key], server[key])
            self.assertEqual(request['upgrade_tasks'], ['csv_preview'])
            self.assertFalse(request['growth_enabled'])
            self.assertNotEqual(request['repeatability']['portable_case_sha256'], server['repeatability']['portable_case_sha256'])
            self.assertNotIn('sampling_seed', server['profiles'][0]['config'])
            self.assertEqual(server['profiles'][0]['sampling']['declared_server_initial_seed'], 104729)

    def test_fixed_cases_are_identical_across_repeats_and_host_preparations(self):
        with temporary_directory() as directory:
            root=Path(directory);profiles=root/'profiles.json'
            atomic_json(profiles,[{'id':'fixture','config':{'provider':'hosted','base_url':'http://127.0.0.1:8080/v1','model':'fixture'}}])
            profiles.write_text(profiles.read_text(),encoding='utf-8-sig')  # Common Windows editor/PowerShell output.
            args=SimpleNamespace(mode='full',output=str(root/'a'),profiles=str(profiles),repeats=None,
                timeout=3600,output_token_budget=65536,case_pack=str(ROOT/'evaluations/repeatability-cases.json'))
            with patch('builtins.print'):
                model_plan.prepare(args);args.output=str(root/'b')
                with patch.object(model_plan,'environment',return_value={'root':'another-host'}):model_plan.prepare(args)
            a=json.loads((root/'a/plan.json').read_text());b=json.loads((root/'b/plan.json').read_text())
            self.assertEqual(a['repeatability'],b['repeatability'])
            self.assertNotEqual(a['environment'],b['environment'])
            self.assertEqual(a['repeats'],3);self.assertEqual(a['upgrade_tasks'],['format_json','csv_preview'])
            for feature in a['upgrade_tasks']:
                self.assertEqual(a['first_use_contracts']['1-'+feature],a['first_use_contracts']['3-'+feature])
            config=a['profiles'][0]['config']
            self.assertEqual(repeat_config(a,config,2)['sampling_seed'],130363)
            self.assertEqual(config['sampling_seed'],104729)
            self.assertEqual(a['source_sha256'],b['source_sha256'])

    def test_invalid_schedule_and_mismatched_repeat_count_are_rejected(self):
        with temporary_directory() as directory:
            path=Path(directory)/'pack.json'
            base={'schema':1,'sampling_seeds':[1,2],'cases':[{'feature':'format_json','input_id':'fixed'}]}
            plan={'contracts':{'format_json':'contract'},'profiles':[],'recipe':'recipe','deadline':10,'generated_tokens':100,'scope':''}
            for change in ({'sampling_seeds':[True]},{'sampling_seeds':[{}]},{'sampling_seeds':[1,1]},
                {'cases':[{'feature':'format_json','input_id':'../escape'}]}):
                atomic_json(path,{**base,**change})
                with self.assertRaises(ValueError):freeze_cases(copy.deepcopy(plan),path)
            atomic_json(path,base)
            with self.assertRaises(ValueError):freeze_cases(copy.deepcopy(plan),path,3)
