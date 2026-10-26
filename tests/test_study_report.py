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


class StudyReportTests(unittest.TestCase):
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
