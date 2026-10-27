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
from repeatability import repeat_config, freeze_cases


class RepeatabilityTests(unittest.TestCase):
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
