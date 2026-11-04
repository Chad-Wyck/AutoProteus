"""Prospective teacher-study contracts; no models or GPUs."""
import copy,json,sys,tempfile,time,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_contract import pilot_brief,resource_feedback,development_gate,qualify_target_outcome
from tensor_workspace_teacher_stage import teacher_cases,screen_support,endpoint_outcomes,screen_fixture,grade_teacher_case,freeze_endpoint,prepare_layout,science_deadline,resume_frozen_intervention,TeacherStudy,PAIR_CATEGORIES,SCREEN,PAIR,RESERVE,TOTAL
from tensor_workspace_study import Study
from tensor_workspace_overnight import fixture
from tensor_workspace_errors import CellAllowanceExceeded,InfrastructureStop
from weight_editor_runtime import Deadline
from lora6k_state import atomic,read,sha


class TeacherStageControls(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace');self.root=Path(self.temp.name)
        self.case=teacher_cases()[0];self.p,_,_,_,_=fixture(self.root/'fixture',self.case,faithful=False)
        self.plan={'numeric_policy':'precise-v2','models':{'original_target':self.p.base,'unchanged':{'sha256':'original'}},
            'limits':{'arm_seconds':60,'editor_calls':8,'editor_tokens':49152,'cell_seconds':60,'forward_calls':4,'development_generated_tokens':32768},
            'design':{'explicit_contract':True,'target_output_tokens':8192,'editor_output_tokens':8192,'editor_seed_sequence':[2026110420+i for i in range(8)]},'image':{},'tokenizers':{'editor_tokenizer':{'path':'unused'}}}

    def tearDown(self):self.temp.cleanup()

    def study(self):
        s=object.__new__(Study);s.root=self.root;s.project=self.root;s.deadline=Deadline(120);s.state={'arms':{}};s.save=Mock();s.settings_sha256='settings'
        s.plan=copy.deepcopy(self.plan);s.records=self.p.records;s.cases=[];s.golds={};s.brief=pilot_brief(self.plan);s.generation_calls=0;s.probe_calls=0
        return s

    def editor_flow(self,outcomes,*,teacher=None):
        s=self.study();s.inference=Mock(return_value=[{'raw_text':'</think>\n```python\nprint(1)\n```','generated_tokens':10,'finish_reason':'eos'}])
        if teacher is not None:s.teacher_models={'unchanged':teacher}
        tokenizer=Mock();tokenizer.encode.return_value=types.SimpleNamespace(ids=[1,2])
        vm=Mock();index=iter(outcomes)
        def execute(code,policy,seconds):
            action,error=next(index)
            if action=='allowance':raise CellAllowanceExceeded('bounded cell')
            if action=='submit':policy.handle({'op':'submit'})
            return {'error':error,'output':'out'}
        vm.execute.side_effect=execute
        with patch.dict(sys.modules,{'tokenizers':types.SimpleNamespace(Tokenizer=types.SimpleNamespace(from_file=Mock(return_value=tokenizer)))}),patch('tensor_workspace_study.TensorVM',return_value=vm):s.editor_arm('unchanged',[])
        vm.close.assert_called_once();return s

    def test_brief_has_one_real_configuration_and_schema(self):
        text=pilot_brief(self.plan)
        self.assertIn('at most 8 responses',text);self.assertIn('sharing 49152',text)
        self.assertIn("result['candidate']['outcomes']",text);self.assertIn('exactly ONE text',text)
        self.assertIn('are NOT supported',text);self.assertNotIn('48 editor turns',text);self.assertNotIn('32K output',text)

    def test_resource_feedback_counts_attempts_and_physical_usage(self):
        s=self.study();s.policy=self.p;s.worker_deadline=Deadline(20);s.generation_calls=1;s.probe_calls=2
        r=resource_feedback(s,{'calls':7,'editor_tokens':40000,'sampled_tokens':12000})
        self.assertEqual((r['responses_remaining'],r['sampled_editor_tokens_remaining']),(1,9152))
        self.assertEqual((r['candidate_generation_requests_remaining'],r['single_text_probes_remaining']),(1,0))
        self.assertEqual(r['candidate_feedback_tokens_remaining'],20768);self.assertEqual(r['candidate'],self.p.candidate_state())

    def test_submission_then_error_fails_clean_terminal(self):
        s=self.editor_flow([('submit','ValueError: after submit')]);st=s.state['arms']['unchanged']
        self.assertTrue(st['submitted']);self.assertFalse(st['clean_terminal']);self.assertEqual(st['status'],'submission_cell_error')
        self.assertEqual(len(st['recoverable_errors']),1)

    def test_recovered_error_then_clean_submission_is_explicit(self):
        s=self.editor_flow([('none','ValueError: earlier'),('submit',None)]);st=s.state['arms']['unchanged']
        self.assertTrue(st['clean_terminal']);self.assertEqual(st['status'],'clean_submitted');self.assertEqual(len(st['recoverable_errors']),1)

    def test_cell_allowance_status_is_not_overwritten(self):
        s=self.editor_flow([('allowance',None)]);st=s.state['arms']['unchanged']
        self.assertEqual(st['status'],'model_cell_allowance');self.assertFalse(st['clean_terminal'])

    def test_eight_clean_cells_without_submit_remain_incomplete(self):
        s=self.editor_flow([('none',None)]*8);st=s.state['arms']['unchanged']
        self.assertEqual(st['calls'],8);self.assertEqual(st['status'],'turn_allowance_exhausted');self.assertFalse(st['clean_terminal'])

    def test_actual_teacher_model_binding_without_manifest_mutation(self):
        s=self.editor_flow([('submit',None)],teacher={'sha256':'manual binding'})
        self.assertEqual(s.inference.call_args.args[1],{'sha256':'manual binding'})
        self.assertEqual(s.inference.call_args.args[2][0]['rng_seed'],2026110420)
        self.assertEqual(s.plan['models']['unchanged'],self.plan['models']['unchanged'])

    def test_latest_resource_feedback_survives_context_trimming(self):
        s=self.study();s.policy=self.p
        tokenizer=Mock();tokenizer.encode.side_effect=lambda t,**kw:types.SimpleNamespace(ids=[1]*len(t))
        messages=[{'role':'user','content':'initial baseline'},{'role':'assistant','content':'x'*25000},
            {'role':'user','content':'y'*25000},{'role':'user','content':'remaining_resources: latest'}]
        rendered,_=s.render(messages,tokenizer)
        self.assertIn('remaining_resources: latest',rendered);self.assertIn('initial baseline',rendered)

    def test_screen_readonly_rejects_checkpoint_and_missing_display(self):
        c=next(x for x in teacher_cases() if x['kind']=='test_saved')
        p,expected,requests,n,attempts=screen_fixture(self.root/'readonly',c,faithful=False)
        with self.assertRaises(ValueError):p.handle({'op':'checkpoint','label':'extra'})
        result=p.handle({'op':'forward','mode':'generate','view':'edited','ids':['dev-0','dev-1'],'texts':None})
        out=grade_teacher_case(p,expected,requests,n,attempts,c,{'error':None,'output':json.dumps(result)})
        self.assertFalse(out['correct']);self.assertEqual(out['forbidden_operation_count'],1)
        p,expected,requests,n,attempts=screen_fixture(self.root/'undisplayed',c,faithful=False)
        p.handle({'op':'forward','mode':'generate','view':'edited','ids':['dev-0','dev-1'],'texts':None})
        self.assertFalse(grade_teacher_case(p,expected,requests,n,attempts,c,{'error':None,'output':''})['correct'])

    def test_invalid_endpoint_is_recorded_without_snapshot_or_exception(self):
        s=self.study();s.policy=self.p;s.state['arms']['unchanged']={'clean_terminal':False,'status':'turn_allowance_exhausted'}
        (self.root/'unchanged').mkdir();self.p.upload={'partial':True};s.snapshot=Mock()
        endpoint=freeze_endpoint(s,'unchanged',[{'id':'dev-0','correct':False},{'id':'dev-1','correct':False}])
        self.assertFalse(endpoint['numerically_valid']);s.snapshot.assert_not_called()
        self.assertEqual(read(self.root/'unchanged/ENDPOINT.json')['secondary_status'],'unmeasured_invalid_endpoint')

    def test_development_gate_requires_clean_completion_and_bound_coverage(self):
        self.p.mark_evaluated('generate',['dev-0','dev-1'],'measured',context={'settings_sha256':'settings','outcomes':[{'id':'dev-0','correct':True},{'id':'dev-1','correct':False}]})
        initial=[{'id':'dev-0','correct':False},{'id':'dev-1','correct':False}];self.p.handle({'op':'submit'})
        bad={'clean_terminal':False,'status':'submission_cell_error','terminal_cell_error':'after submit'}
        self.assertFalse(development_gate(self.p,bad,initial,'settings')['passed'])
        good={'clean_terminal':True,'status':'clean_submitted','terminal_cell_error':None}
        self.assertTrue(development_gate(self.p,good,initial,'settings')['passed'])
        self.assertFalse(development_gate(self.p,good,initial,'other-settings')['passed'])

    def test_screen_ceiling_accuracy_cannot_show_gain(self):
        b=[{'id':'a','split':'development','correct':True}];e=copy.deepcopy(b)
        self.assertEqual(screen_support(b,e,'development')['gains'],[])
        e[0]['correct']=False;self.assertEqual(screen_support(b,e,'development')['losses'],['a'])

    def test_secondary_unsubmitted_endpoint_cannot_earn_primary(self):
        b=[{'id':'confirmation-0','correct':False},{'id':'preservation-0','correct':True}]
        e=[{'id':'confirmation-0','correct':True},{'id':'preservation-0','correct':True}]
        endpoint={'development_gate':{'passed':False},'baseline_equivalent':False,'primary_procedural_completion':False}
        out=endpoint_outcomes(b,e,endpoint);self.assertEqual(out['secondary_correct'],2);self.assertFalse(out['primary_accepted_student_improvement'])

    def test_preservation_is_not_vacuous_and_unchanged_is_not_repair(self):
        b=[{'id':'confirmation-0','correct':False},{'id':'preservation-0','correct':False}];e=[{'id':r['id'],'correct':True} for r in b]
        endpoint={'development_gate':{'passed':True},'baseline_equivalent':False,'primary_procedural_completion':True}
        self.assertFalse(endpoint_outcomes(b,e,endpoint)['primary_accepted_student_improvement'])
        b[1]['correct']=True;endpoint['baseline_equivalent']=True
        self.assertFalse(endpoint_outcomes(b,e,endpoint)['primary_accepted_student_improvement'])

    def test_stage_arithmetic_and_second_arm_budgets_are_separate(self):
        self.assertEqual(sum(PAIR_CATEGORIES.values()),PAIR);self.assertEqual(SCREEN+PAIR+RESERVE,TOTAL)
        s=object.__new__(TeacherStudy);s.root=self.root;s.phase_categories={'call-001':'feedback_unchanged','call-002':'feedback_edited'}
        atomic(self.root/'usage.json',{'charged_tokens':12000,'phases':{'call-001':{'observed_tokens':8000,'uncertain_tokens_upper_bound':0},'call-002':{'observed_tokens':4000,'uncertain_tokens_upper_bound':0}}})
        b=s.reconcile();self.assertEqual(b['observed_categories']['feedback_unchanged'],8000);self.assertEqual(b['observed_categories']['feedback_edited'],4000)

    def test_target_grading_keeps_answer_completion_and_infrastructure_separate(self):
        row={'status':'ok','correct':True,'finish_reason':'eos'};response={'raw_text':'reason</think>answer'}
        self.assertTrue(qualify_target_outcome(row,response)['correct'])
        capped=qualify_target_outcome({**row,'finish_reason':'length'},response)
        self.assertTrue(capped['reference_correct']);self.assertFalse(capped['correct'])
        self.assertFalse(qualify_target_outcome({**row,'correct':False},response)['correct'])
        self.assertFalse(qualify_target_outcome(row,{'raw_text':'unclosed'})['correct'])
        with self.assertRaises(InfrastructureStop):qualify_target_outcome({'status':'grader_error','correct':None},response)

    def test_preparation_creates_artifact_parent_for_disk_admission(self):
        import shutil
        prepared=self.root/'prepared';prepare_layout(prepared)
        self.assertGreater(shutil.disk_usage(prepared/'artifacts').free,0)
        self.assertFalse((prepared/'artifacts/edited-teacher').exists())
        with self.assertRaises(FileExistsError):prepare_layout(prepared)

    def test_continuation_preserves_original_screen_and_global_clock(self):
        began=time.time()-1800
        atomic(self.root/'SCIENTIFIC-START.json',{'began_unix':began,'end_unix':began+28800})
        atomic(self.root/'manifest.json',{'continuation':{'original_screen_end_unix':began+7200}})
        first=sha(self.root/'SCIENTIFIC-START.json');deadline=science_deadline(self.root,'screen')
        self.assertLess(deadline.end-time.monotonic(),5401);self.assertGreater(deadline.end-time.monotonic(),5398)
        self.assertEqual(first,sha(self.root/'SCIENTIFIC-START.json'))
        atomic(self.root/'SCIENTIFIC-START.json',{'began_unix':time.time()-7300,'end_unix':time.time()+20000})
        with self.assertRaises(ValueError):science_deadline(self.root,'screen')

    def test_continuation_cannot_repeat_any_localization_forward(self):
        study=object.__new__(TeacherStudy);study.plan={'continuation':{'localization_conditions_consumed':32}}
        with self.assertRaisesRegex(ValueError,'Localization is disabled'):study.localize([{'unused':True}])

    def test_continuation_builds_only_exact_pinned_recipe_once(self):
        s=self.study();proposal={'layer':26,'columns':list(range(16)),'scale':.5}
        atomic(self.root/'FROZEN-INTERVENTION.json',{'proposal':proposal,'mean_column_margin_change':.04})
        s.plan['continuation']={'intervention_sha256':sha(self.root/'FROZEN-INTERVENTION.json'),'localization_conditions_consumed':32}
        with patch('tensor_workspace_teacher_stage.build_frozen_intervention',return_value={'passed':True}) as build:
            self.assertTrue(resume_frozen_intervention(s)['passed']);build.assert_called_once_with(s,proposal)
        (self.root/'artifacts/edited-teacher').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'duplicate artifact'):resume_frozen_intervention(s)


if __name__=='__main__':unittest.main()
