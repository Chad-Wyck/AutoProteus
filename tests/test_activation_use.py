import copy
import json
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from controller.config import DEFAULTS
from controller.storage import atomic_json
from test_seed import temporary_directory

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'evaluations'))
import activation_use as use
import model_study as study
from study_support import identity


class Files:
    def __init__(self,values): self.values=values
    def read(self,path):
        if path not in self.values: raise ValueError('Missing file')
        return self.values[path]


class ActivationUseTests(unittest.TestCase):
    def fixture(self,feature):
        spec=use.contract(feature,'fixed')
        final,receipt=use.expected(spec)
        files=Files({spec['input']:final,spec['output']:json.dumps(receipt).encode()})
        events=[{'type':'action_result','data':{'ok':True,'action':{'tool':feature,'arguments':{'path':spec['input']}},'result':receipt}}]
        return spec,files,events

    def test_fresh_contracts_and_oracles_detect_missing_calls_wrong_input_and_wrong_receipt(self):
        specs={feature:use.contract(feature,'fresh') for feature in study.study.CONTRACTS}
        self.assertTrue(use.oracle_controls(specs)['passed'])
        for feature in specs:
            spec,files,events=self.fixture(feature)
            self.assertNotEqual(spec['input'],use.contract(feature,'other')['input'])
            self.assertTrue(use.grade(files,spec,events,source_unchanged=True,completed=True)['passed'])
            for field in ('source_unchanged','completed','on_time','within_budget'):
                options={'source_unchanged':True,'completed':True,field:False}
                self.assertFalse(use.grade(files,spec,events,**options)['passed'])
            bad=copy.deepcopy(events);bad[0]['data']['result']={'path':spec['input']}
            self.assertFalse(use.grade(files,spec,bad,source_unchanged=True,completed=True)['passed'])

    def test_cli_invocation_can_prove_fresh_use_without_native_route_preference(self):
        spec,files,events=self.fixture('sha256_file')
        _,receipt=use.expected(spec)
        arguments=json.dumps({'path':spec['input']})
        event={'type':'action_result','data':{'ok':True,'action':{'tool':'run_command','arguments':{
            'command':"python3 harness/seed.py invoke --tool sha256_file --arguments '"+arguments+"'"}},
            'result':{'exit_code':0,'output':json.dumps({'check':'candidate tool invocation','passed':True,'tool':'sha256_file','result':receipt})}}}
        grade=use.grade(files,spec,[event],source_unchanged=True,completed=True)
        self.assertTrue(grade['passed']);self.assertIn('sha256_file',grade['usage']['development'])
        self.assertFalse(grade['inspection_observed'])  # Not an arbitrary extra gate.
        helper=copy.deepcopy(event)
        helper['data']['action']['arguments']['command']="python3 experience/invoke_tool.py sha256_file '"+arguments+"'"
        helper['data']['result']['output']=json.dumps({'check':'development tool invocation','passed':True,'tool':'sha256_file','result':receipt})
        self.assertTrue(use.grade(files,spec,[helper],source_unchanged=True,completed=True)['passed'])
        helper['data']['result']['output']=json.dumps({'check':'development tool invocation','passed':False,'tool':'sha256_file','result':receipt})
        self.assertFalse(use.grade(files,spec,[helper],source_unchanged=True,completed=True)['passed'])

    def test_csv_requires_five_rows_and_format_requires_actual_file_change(self):
        spec,files,events=self.fixture('csv_preview')
        self.assertTrue(use.grade(files,spec,events,source_unchanged=True,completed=True)['default_arguments_omitted'])
        events[0]['data']['action']['arguments']['limit']=5
        explicit=use.grade(files,spec,events,source_unchanged=True,completed=True)
        self.assertTrue(explicit['passed']);self.assertFalse(explicit['default_arguments_omitted'])
        receipt=json.loads(files.values[spec['output']]);self.assertEqual(len(receipt['rows']),5)
        numeric={**receipt,'truncated':1};files.values[spec['output']]=json.dumps(numeric).encode()
        self.assertFalse(use.grade(files,spec,events,source_unchanged=True,completed=True)['passed'])
        receipt['rows']=receipt['rows'][:2];files.values[spec['output']]=json.dumps(receipt).encode()
        self.assertFalse(use.grade(files,spec,events,source_unchanged=True,completed=True)['passed'])
        spec,files,events=self.fixture('format_json')
        files.values[spec['input']]=spec['fixtures'][spec['input']].encode()
        self.assertFalse(use.grade(files,spec,events,source_unchanged=True,completed=True)['passed'])

    def test_python_workspace_variables_and_environment_prefix_are_observed_without_execution(self):
        import shlex
        from controller.evaluation import tool_use
        from controller.tool_evidence import python_invocations
        spec,files,_=self.fixture('sha256_file');_,receipt=use.expected(spec)
        for module,prefix in [('autoproteus.tools','PYTHONPATH=/work/task/harness '),('harness.autoproteus.tools','')]:
            program=('from '+module+' import Workspace\nfrom pathlib import Path\n'
                "workspace = Workspace(Path('.'))\nresult = workspace.execute('sha256_file', "+repr({'path':spec['input']})+")\nprint('Result:', result)\n")
            command=prefix+'python3 -c '+shlex.quote(program)
            event={'type':'action_result','data':{'ok':True,'action':{'tool':'run_command','arguments':{'command':command}},
                'result':{'exit_code':0,'output':'Result: '+repr(receipt)+'\n'}}}
            self.assertIn('sha256_file',tool_use([event])['development'])
            self.assertTrue(use.grade(files,spec,[event],source_unchanged=True,completed=True)['passed'])
            event['data']['result']['exit_code']=1
            self.assertFalse(use.grade(files,spec,[event],source_unchanged=True,completed=True)['passed'])
            event['data']['result']['exit_code']=0
            for bad in [program.replace(spec['input'],'other.txt'),program.replace("print('Result:', result)","print('Result:', {})")]:
                event['data']['action']['arguments']['command']=prefix+'python3 -c '+shlex.quote(bad)
                self.assertFalse(use.grade(files,spec,[event],source_unchanged=True,completed=True)['passed'])
        for program in ["from other import Workspace\nWorkspace('.').execute('x', {})",
            "from autoproteus.tools import Workspace\nif False:\n Workspace('.').execute('x', {})",
            "from autoproteus.tools import Workspace\nw=Workspace('.')\nw=object()\nw.execute('x', {})",
            "from autoproteus.tools import Workspace\nWorkspace=object\nWorkspace().execute('x', {})"]:
            self.assertEqual(python_invocations('python3 -c '+shlex.quote(program)),[])

    def test_first_only_outline_preparation_is_inert_and_keeps_seed_frozen(self):
        import contextlib
        import io
        from controller.isolation import seed_files
        from controller.evaluation import source_identity
        with temporary_directory() as directory:
            root=Path(directory);profiles=root/'profiles.json'
            atomic_json(profiles,[{'id':'fixture','config':{'provider':'hosted','base_url':'http://127.0.0.1:8080/v1','model':'fixture'}}])
            before=source_identity(seed_files(ROOT))
            args=SimpleNamespace(output=str(root/'study'),profiles=str(profiles),mode='full',repeats=1,
                timeout=3600,output_token_budget=65536,first_only=True,experiment='source-outline')
            with patch.object(study,'model_identity') as model,contextlib.redirect_stdout(io.StringIO()):
                study.prepare(args);model.assert_not_called()
            plan=json.loads((root/'study/plan.json').read_text())
            self.assertEqual(plan['protocol'],use.PROTOCOL)
            self.assertFalse(plan['growth_enabled'])
            self.assertEqual(set(plan['variants']),{'baseline','source-outline'})
            self.assertEqual(len(plan['first_use_contracts']),3)
            self.assertEqual(source_identity(seed_files(ROOT)),before)

    def test_first_use_failure_allows_diagnostic_but_never_complete_chain_credit(self):
        first={'first_package_accepted':True,'review':{'accepted':False},'first_use':{'passed':False}}
        self.assertTrue(use.eligible_parent(first,use.PROTOCOL))
        second={'scores':{'functional_growth':True}}
        result=use.chain_result(first,second,use.PROTOCOL)
        self.assertTrue(result['diagnostic_only']);self.assertFalse(result['complete_chain_passed'])
        first['first_use']['passed']=True
        self.assertTrue(use.chain_result(first,second,use.PROTOCOL)['complete_chain_passed'])
        self.assertIsNone(use.chain_result(first,second)['complete_chain_passed'])
        self.assertFalse(use.eligible_parent({'first_package_accepted':False},use.PROTOCOL))

    def test_new_queue_preserves_verified_parent_after_failed_use_and_marks_diagnostic(self):
        with temporary_directory() as directory:
            root=Path(directory);output=root/'.data/study';output.mkdir(parents=True)
            source=[{'path':'seed.py','data':'IyBJbmVydA=='}]
            plan={'protocol':use.PROTOCOL,'growth_enabled':True,'profiles':[{'id':'fixture','config':dict(DEFAULTS)}],
                'mode':'full','repeats':1,'source':[],'source_sha256':'fixture','trusted_sha256':{},'environment':{},'scope':'fixture',
                'ordinary_tasks':['one'],'tasks':[{'name':'one'}],'upgrade_tasks':list(study.study.CONTRACTS),
                'contracts':study.study.CONTRACTS,'recipe':study.study.RECIPE,'invoke_tool':'',
                'first_use_contracts':{'1-'+name:use.contract(name,'fresh') for name in study.study.CONTRACTS}}
            atomic_json(output/'plan.json',plan);(output/'plan.sha256').write_text(identity(plan))
            def calibration(folder,source): atomic_json(folder/'calibration.json',{'passed':True})
            calls=[]
            def attempt(folder,task,starter,config,inputs,feature=None,earlier=None):
                calls.append((feature,earlier))
                if earlier:
                    self.assertEqual(starter,source)
                    return {'verified_extension':True,'scores':{'functional_growth':True},'review':{'verified_upgrade':True}}
                if feature:
                    self.assertIn('finish needs_input',task['task'])
                    self.assertNotIn(task['first_use']['input'],task.get('fixtures',{}))
                    ready=feature=='sha256_file'
                    if ready: atomic_json(folder/'review/candidate-source.json',source)
                    return {'first_package_accepted':ready,'review':{'accepted':False},
                        'first_use':{'attempted':ready,'passed':False}}
                return {'run':{'passed':True}}
            with patch.object(study,'ROOT',root),patch.object(study,'check'),patch.object(study,'Appliance'),\
                patch.object(study,'model_identity',return_value={'model':'fixture'}),\
                patch.object(study.study,'self_check',side_effect=calibration),\
                patch.object(study,'benchmark',return_value={'passed':True}),patch.object(study,'trial',side_effect=attempt):
                args=SimpleNamespace(input=str(output),retry=[])
                study.run(args);count=len(calls);study.run(args);self.assertEqual(len(calls),count)
            summary=json.loads((output/'summary.json').read_text())['profiles']['fixture']
            self.assertEqual(summary['first_accepted'],1)
            self.assertEqual(summary['first_use_passed'],0)
            self.assertEqual(summary['second_use_passed'],1)
            self.assertEqual(summary['diagnostic_second_attempts'],1)
            self.assertEqual(summary['complete_growth'],0)
