import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from controller.config import DEFAULTS
from controller.storage import atomic_json
from test_seed import temporary_directory

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'evaluations'))
import model_plan
import model_study as ms
import outcome_study as study
from outcome_tasks import task_pack, grade_outputs, oracle_controls
from study_support import identity, StudyQueue


class Files:
    def __init__(self,task):
        self.values={r['path']:(r['expected'].encode('utf-8') if r['kind']=='text' else json.dumps(r['expected'],ensure_ascii=False).encode()) for r in task['checks']}
    def read(self,path):return self.values[path]


class OutcomeStudyTests(unittest.TestCase):
    def test_outcomes_are_exact_and_fresh_without_any_required_extension(self):
        cases=task_pack();self.assertTrue(oracle_controls(cases)['passed'])
        for case in cases:
            for stage in ('first','reuse'):
                task=case[stage];files=Files(task)
                self.assertTrue(grade_outputs(files,task)['passed'])
                self.assertNotIn('add a tool',task['task'].lower());self.assertNotIn('edit the seed',task['task'].lower())
                output=task['checks'][0]['path'];files.values[output]=b'wrong output'
                self.assertFalse(grade_outputs(files,task)['passed'])
            self.assertNotEqual(list(case['first']['fixtures'].values()),list(case['reuse']['fixtures'].values()))
        csv_case=next(c for c in cases if c['name']=='csv-index')['first']
        expected=csv_case['checks'][0]['expected'];self.assertEqual(expected['files'][0]['rows'],3)
        self.assertIn('\r\n',expected['files'][0]['preview'][1][0])

    def test_preparation_freezes_goals_checks_and_sampling_without_calling_a_model(self):
        with temporary_directory() as directory:
            root=Path(directory);profiles=root/'profiles.json'
            atomic_json(profiles,[{'id':'fixture','config':{'provider':'hosted','base_url':'http://127.0.0.1:8080/v1','model':'fixture'}}])
            args=SimpleNamespace(mode='outcomes',output=str(root/'study'),profiles=str(profiles),repeats=1,timeout=3600,output_token_budget=65536)
            with patch('builtins.print'),patch.object(ms,'model_identity',side_effect=AssertionError('No model calls while preparing')):
                model_plan.prepare(args)
            plan=json.loads((root/'study/plan.json').read_text())
            self.assertEqual(len(plan['outcome_cases']),4);self.assertEqual(plan['upgrade_tasks'],[])
            self.assertEqual(plan['protocol'],'outcome-choice-v1')
            self.assertTrue(all(c['starter_solvable'] for c in plan['outcome_cases']))
            self.assertEqual(plan['profiles'][0]['config']['sampling_seed'],104729)
            self.assertIn('unmeasured',plan['scope'])

    def test_no_edit_can_complete_both_tasks_and_does_not_earn_extension_credit(self):
        with temporary_directory() as directory:
            root=Path(directory);source=[{'path':'seed.py','data':'IyBpbmVydA=='}]
            plan={'mode':'outcomes','profiles':[{'id':'fixture','config':dict(DEFAULTS)}],'source':source,'base_tool_names':['read_file','write_file'],
                'repeats':1,'scope':'fixture','outcome_cases':task_pack()[:2]}
            ledger=StudyQueue(root,identity(plan))
            def phase(folder,task,starter,*args):
                atomic_json(folder/'continuation-source.json',starter)
                return {'task_outcome_passed':True,'seed_edit_attempted':False,'checked_packages':0,
                    'continuation_source_sha256':study.source_identity(starter),'continuation_tools':plan['base_tool_names'],
                    'usage':{'direct':['read_file','write_file'],'development':[]}}
            with patch.object(ms,'check'),patch.object(ms,'model_identity',return_value={'model':'fixture'}),\
                patch.object(ms,'benchmark',return_value={'passed':True}),patch.object(study,'phase',side_effect=phase),patch('builtins.print'):
                result=study.run_plan(plan,root,ledger,SimpleNamespace(retry=[]))
            self.assertEqual(result['first_task_passes'],2);self.assertEqual(result['later_task_passes'],2)
            self.assertEqual(result['two_task_workflows_passed'],2);self.assertEqual(result['source_extensions_chosen'],0)
            self.assertEqual(result['extension_use_observed'],0)
            self.assertEqual(result['independent_feature_acceptance'],'unmeasured')

    def test_failed_preflight_leaves_tasks_unmeasured_not_failed(self):
        with temporary_directory() as directory:
            root=Path(directory)
            plan={'mode':'outcomes','profiles':[{'id':'fixture','config':dict(DEFAULTS)}],'repeats':1,
                'scope':'fixture','outcome_cases':task_pack()[:2]}
            ledger=StudyQueue(root,identity(plan))
            with patch.object(ms,'check'),patch.object(ms,'model_identity',return_value={'model':'fixture'}),\
                patch.object(ms,'benchmark',return_value={'passed':False}),patch.object(study,'phase') as phase,patch('builtins.print'):
                result=study.run_plan(plan,root,ledger,SimpleNamespace(retry=[]))
            phase.assert_not_called()
            self.assertIsNone(result['first_task_passes']);self.assertIsNone(result['later_task_passes'])
            self.assertEqual(result['first_task_outcomes']['scheduled'],2)
            self.assertEqual(result['first_task_outcomes']['launched'],0)
            self.assertEqual(result['first_task_outcomes']['recorded_outcomes'],0)
