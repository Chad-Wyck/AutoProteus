import base64
import contextlib
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from research_limits import research_config, resource_limits
from submission_preflight import check, structural_issues
import completion_study as completion
import discovery_study as discovery


class ResearchReadinessTests(unittest.TestCase):
    def test_research_limits_do_not_inherit_uncapped_app_preferences(self):
        saved = {'action_limit':False, 'max_steps':24}
        config = research_config(saved)
        self.assertFalse(saved['action_limit'])
        self.assertTrue(config['action_limit'])
        self.assertEqual(resource_limits(config, 3600, 65536)['actions'], 24)
        for values in ({'max_steps':0}, {'max_steps':True}, {'max_steps':201}):
            with self.assertRaises(ValueError): research_config(values)
        with self.assertRaises(ValueError): resource_limits(saved, 3600, 65536)

    def test_public_preflight_parses_schema_without_executing_candidate_code(self):
        with temporary_directory() as directory:
            root = Path(directory)
            providers = root/'harness/autoproteus/providers.py'
            providers.parent.mkdir(parents=True)
            providers.write_text('raise RuntimeError("MUST NEVER RUN")\n'
                'TOOL_SPECS={"combine":("desc", {"sources":{}, "output":{}}, ["sources","output"])}')
            good = {'tool':'combine','arguments':{'sources':['@INPUT_A','@INPUT_B'],'output':'@OUTPUT'}}
            declaration = root/'capability.json'
            declaration.write_text(json.dumps(good))
            self.assertTrue(check(root)['valid'])
            declaration.write_text(json.dumps({**good, 'arguments':{'wrong':['@INPUT_A','@INPUT_B'],'output':'@OUTPUT'}}))
            self.assertIn('Undeclared top-level', ' '.join(check(root)['issues']))
            self.assertTrue(structural_issues({**good,'arguments':{'@INPUT_A':'a','@INPUT_B':'b','@OUTPUT':'out'}}))
            declaration.unlink()
            self.assertFalse(check(root)['valid'])

    def test_discovery_prepares_optional_public_helper_and_explicit_budget(self):
        with temporary_directory() as directory:
            root = Path(directory); profile = root/'profile.json'
            profile.write_text(json.dumps({'config':{'action_limit':False,'max_steps':32}}))
            args = SimpleNamespace(profile=str(profile),output=str(root/'discovery'))
            discovery.prepare(args)
            plan = json.loads((root/'discovery/plan.json').read_text())
            self.assertTrue(plan['config']['action_limit'])
            self.assertEqual(plan['resource_limits']['actions'],32)
            self.assertIn('development/check_submission.py',plan['task']['fixtures'])
            self.assertNotIn('development/check_submission.py',plan['preserve_inputs'])
            self.assertIn('workspace root',plan['task']['task'])

    def test_completion_prepares_separate_balanced_pilots_without_inference(self):
        with temporary_directory() as directory, patch.object(completion,'model_identity') as infer:
            root = Path(directory); profile = root/'profile.json'
            profile.write_text(json.dumps({'config':{'action_limit':False,'max_steps':40}}))
            for treatment in ('final-contract','short-guidance'):
                args = SimpleNamespace(profile=str(profile),source=None,output=str(root/treatment),
                    comparison=treatment,repeats=1,timeout=3600,output_token_budget=65536)
                with contextlib.redirect_stdout(io.StringIO()): plan = completion.prepare(args)
                completion.validate(plan)
                self.assertTrue(plan['config']['action_limit'])
                self.assertEqual(len(plan['schedule']),6)
                self.assertEqual({row['arm'] for row in plan['schedule']},{'baseline',treatment})
                self.assertEqual(plan['resource_limits']['wall_seconds'],3600)
                self.assertTrue((root/treatment/'Run comparison.cmd').exists())
                same = plan['sources']['baseline']==plan['sources'][treatment]
                self.assertEqual(same,treatment=='final-contract')
                for task in plan['tasks']:
                    self.assertNotEqual(task['control'],task['fault'])
            infer.assert_not_called()
