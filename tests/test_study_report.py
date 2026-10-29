import json
from pathlib import Path
import sys
import unittest

from controller.storage import atomic_json
from test_seed import temporary_directory

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'evaluations'))
from study_report import attempt_folder, failure_labels, report, markdown
from trace_audit import audit_events
from study_support import task_observations
from activation_use import PROTOCOL


class StudyReportTests(unittest.TestCase):
    def test_correct_artifacts_do_not_hide_missing_completion_or_skipped_extensions(self):
        with temporary_directory() as directory:
            root = Path(directory)
            atomic_json(root / 'plan.json', {'protocol': PROTOCOL, 'profiles': [{'id': 'fixture', 'config': {}}]})
            cells = {f'fixture_basic_{n}': [{'attempt': 1, 'state': 'completed', 'result': {
                'run': {'checks': [{'passed': True}], 'status': 'completed' if n == 0 else 'waiting', 'passed': n == 0}}}]
                for n in range(5)}
            cells['fixture_first_01_csv'] = [{'attempt': 0, 'state': 'not_run', 'reason': 'Basic gate did not qualify'}]
            cells['fixture_growth_01_csv'] = [{'attempt': 0, 'state': 'not_run', 'reason': 'No accepted parent'}]
            atomic_json(root / 'queue.json', {'cells': cells})
            result = report(root)
            group = result['groups']['fixture/baseline']
            self.assertEqual(group['ordinary_artifacts_correct'], 5)
            self.assertEqual(group['ordinary_explicit_completion'], 1)
            self.assertEqual(group['ordinary_passed'], 1)
            self.assertEqual(group['first_attempts'], 0)
            self.assertEqual(group['not_run']['first'], 1)
            self.assertEqual(group['not_run']['second'], 1)
            self.assertIn('explicit_completion_missing', result['rows'][1]['failure_labels'])
            rendered = markdown(result)
            self.assertIn('5/5 | 1/5 | 1/5', rendered)
            self.assertIn('Not run: Basic gate did not qualify', rendered)
            self.assertNotIn('0/0', rendered)

    def test_missing_checks_and_partial_attempts_are_not_artifact_passes(self):
        self.assertIsNone(task_observations({'checks': []})['artifacts_correct'])
        self.assertIsNone(task_observations({'checks': [{'passed': None}]})['artifacts_correct'])
        with temporary_directory() as directory:
            root = Path(directory)
            atomic_json(root / 'plan.json', {'profiles': [{'id': 'fixture', 'config': {}}]})
            atomic_json(root / 'queue.json', {'cells': {'fixture_basic_error': [{'attempt': 1, 'state': 'error', 'result': {
                'run': {'checks': [{'passed': True}], 'status': 'completed', 'passed': True}}}]}})
            group = report(root)['groups']['fixture/baseline']
            self.assertEqual(group['ordinary_attempts'], 1)
            self.assertEqual(group['ordinary_checks'], 0)
            self.assertEqual(group['ordinary_passed'], 0)

    def test_correct_first_use_artifacts_do_not_imply_tool_reuse(self):
        with temporary_directory() as directory:
            root = Path(directory)
            atomic_json(root / 'plan.json', {'protocol': PROTOCOL, 'profiles': [{'id': 'fixture', 'config': {}}]})
            atomic_json(root / 'queue.json', {'cells': {'fixture_first_01_json': [{'attempt': 1, 'state': 'completed', 'result': {
                'added': 'format_json', 'first_package_accepted': True,
                'first_use': {'attempted': True, 'artifacts_correct': True, 'completed': True, 'capability_used': False, 'passed': False}}}]}})
            result = report(root)
            self.assertEqual(result['groups']['fixture/baseline']['first_use_passed'], 0)
            self.assertEqual(result['rows'][0]['outcome'], {'artifacts_correct': True, 'explicit_completion': True, 'capability_used': False})

    def test_activation_reminder_is_labelled_separately_from_the_default_handoff(self):
        with temporary_directory() as directory:
            root=Path(directory)
            atomic_json(root/'plan.json',{'protocol':PROTOCOL,'activation_reminder':True,'profiles':[{'id':'fixture','config':{}}]})
            atomic_json(root/'queue.json',{'cells':{'fixture_first_01_hash':[{'attempt':1,'state':'completed',
                'result':{'added':'sha256_file','first_package_accepted':True,'activation_reminder':{'observed':True}}}]}})
            value=report(root)
            self.assertTrue(value['activation_reminder'])
            self.assertIn('fixture/task-reminder',value['groups'])
            self.assertTrue(value['rows'][0]['activation_reminder']['observed'])

    def test_resource_receipt_overrides_downstream_provider_error_and_is_not_a_model_score(self):
        with temporary_directory() as directory:
            root=Path(directory)
            atomic_json(root/'plan.json', {'protocol':PROTOCOL,'profiles':[{'id':'fixture','config':{}}]})
            cells={}
            for phase in ('basic','first','growth'):
                cell='fixture_'+phase+'_01'
                cells[cell]=[{'attempt':1,'state':'error','detail':'ProviderError: connection reset','result':{
                    'calls':{'error_categories':{'connection':1}},'review':{'new_test_files':[]}}}]
                atomic_json(root/'trials'/cell/'attempt-001/runtime/cleanup.json',
                            {'reason':'Memory floor reached; owned inference stopped','owned_process_stopped':True})
            cells['fixture_basic_cancelled']=[{'attempt':1,'state':'interrupted','detail':'KeyboardInterrupt'}]
            cells['fixture_basic_unclassified']=[{'attempt':1,'state':'error','detail':'Unknown error'}]
            atomic_json(root/'queue.json',{'cells':cells})
            before=(root/'queue.json').read_bytes()
            value=report(root);group=value['groups']['fixture/baseline']
            self.assertEqual(group['resource_stops'],3)
            self.assertEqual(group['interruptions'],1)
            self.assertEqual(group['infrastructure_errors'],1)
            self.assertEqual(group['launched'],5)
            self.assertEqual(group['ordinary_evaluated'],0)
            self.assertEqual(group['first_evaluated'],0)
            self.assertEqual(group['second_evaluated'],0)
            for row in value['rows'][:3]:
                self.assertIn('resource_stop',row['failure_labels'])
                self.assertNotIn('provider_or_format',row['failure_labels'])
                self.assertNotIn('missing_candidate_tests',row['failure_labels'])
            self.assertIn('Execution accounting',markdown(value))
            self.assertNotIn('0/3',markdown(value))
            self.assertEqual((root/'queue.json').read_bytes(),before)

    def test_overlapping_failures_do_not_confuse_scope_with_implementation(self):
        row={'review':{'allowed_files_only':False,'protected_unchanged':True,'new_test_files':['test.py'],
            'feature':{'passed':True,'probe':{'checks':{'exact':True},'suite':{'exit_code':0}}}},'run':{'status':'completed'}}
        labels,_=failure_labels(row)
        self.assertIn('submission_scope',labels);self.assertNotIn('implementation',labels)
        row['review']['feature']['probe']['checks']['unicode_exact']=False
        self.assertIn('implementation',failure_labels(row)[0])
        row['review']['feature']['probe']['suite']['exit_code']=1
        self.assertIn('candidate_tests',failure_labels(row)[0])
        row['stage_order_preserved']=False
        self.assertIn('final_input_changed_before_activation',failure_labels(row)[0])

    def test_legacy_unknown_use_is_unmeasured_report_is_read_only_and_omits_keys(self):
        with temporary_directory() as directory:
            root=Path(directory)
            atomic_json(root/'plan.json',{'profiles':[{'id':'fixture','config':{'model':'test','api_key':'NEVER COPY'}}]})
            queue={'cells':{'fixture_first_01_hash':[{'attempt':1,'state':'completed','result':{
                'added':'hash','review':{'accepted':True},'run':{'status':'completed'}}}]}}
            atomic_json(root/'queue.json',queue);before=(root/'queue.json').read_bytes()
            result=report(root)
            self.assertIsNone(result['groups']['fixture/baseline']['complete_chains'])
            self.assertIn('unmeasured',markdown(result));self.assertNotIn('NEVER COPY',json.dumps(result))
            self.assertEqual((root/'queue.json').read_bytes(),before)
            queue['cells']['fixture_first_01_hash'][0]['state']='error';atomic_json(root/'queue.json',queue)
            failed=report(root)['groups']['fixture/baseline']
            self.assertEqual(failed['first_attempts'],1);self.assertEqual(failed['first_packages'],0)
            queue['cells']['fixture_first_01_hash'][0]['state']='running';atomic_json(root/'queue.json',queue)
            with self.assertRaises(ValueError):report(root)

    def test_report_does_not_follow_exported_absolute_paths_or_traversal(self):
        with temporary_directory() as directory:
            root=Path(directory)
            self.assertTrue(attempt_folder(root,'safe_cell',1).is_relative_to(root))
            for cell in ('../outside','a/b','C:\\outside'):
                with self.assertRaises(ValueError):attempt_folder(root,cell,1)

    def test_timeline_counts_post_full_reads_but_does_not_call_focused_pass_full(self):
        def event(second,tool,args,result):
            return {'time':f'2026-10-25T00:00:{second:02d}+00:00','type':'action_result',
                'data':{'ok':True,'action':{'tool':tool,'arguments':args},'result':result}}
        rows=[{'time':'2026-10-25T00:00:00+00:00','type':'run_started'},
            event(1,'read_section',{'path':'harness/providers.py','length':20},{'content':'abc','start':0}),
            event(2,'run_command',{}, {'exit_code':0,'output':json.dumps({'check':'candidate focused tests','scope':'focused','passed':True,'tests':1})}),
            event(3,'edit_file',{'path':'harness/tools.py'},{}),
            event(4,'run_command',{}, {'exit_code':0,'output':json.dumps({'check':'candidate tests','scope':'full','passed':True,'tests':10})}),
            event(5,'read_section',{'path':'harness/providers.py','length':20},{'content':'abc','start':0})]
        result=audit_events(rows)
        self.assertEqual(result['first_full_check_seconds'],4)
        self.assertEqual(result['same_content_repeat_reads'],1)
        self.assertEqual(result['tiny_reads_after_full_check'],1)
        self.assertEqual(result['phases']['after_first_full_check'],1)

    def test_unchanged_edits_do_not_start_the_source_editing_phase(self):
        def edit(second, old, new):
            return {'time': f'2026-10-25T00:00:{second:02d}+00:00', 'type': 'action_result',
                    'data': {'ok': True, 'action': {'tool': 'edit_file',
                    'arguments': {'path': 'harness/tools.py', 'old_text': old, 'new_text': new}}, 'result': {}}}
        result = audit_events([{'time': '2026-10-25T00:00:00+00:00', 'type': 'run_started'},
                               edit(1, 'same', 'same'), edit(2, 'same', 'changed')])
        self.assertEqual(result['unchanged_edit_actions'], 1)
        self.assertEqual(result['first_source_edit_seconds'], 2)
