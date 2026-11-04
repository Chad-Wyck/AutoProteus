"""Preparation controls use synthetic arrays and fake backends only."""
import copy,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import Mock,patch
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from neuron_focus_contract import *
from neuron_focus import FocusStudy,_conditions,run,execute
from neuron_focus_worker import probe_condition
from weight_editor_runtime import Deadline,TokenBudget
from lora6k_state import atomic,read,sha


class FocusPreparationControls(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'.data/test-neuron-focus';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.temp.name)
        self.prefixes=[{'id':'prefix-'+str(i)} for i in range(4)]
        atomic(self.root/'prefixes.json',{'prefixes':self.prefixes});self.plan={'publication':str(self.root)}

    def tearDown(self):self.temp.cleanup()

    def test_preparation_cannot_start_runtime_or_load_backend(self):
        atomic(self.root/'manifest.json',{'authority':{'preparation_only':True}});(self.root/'manifest.sha256').write_text('binding')
        with self.assertRaisesRegex(ValueError,'Preparation only'):run(self.root)
        self.assertFalse((self.root/'RUN-STARTED.json').exists());self.assertFalse((self.root/'PROBE-ADMISSION.json').exists())

    def test_execution_review_and_authorization_both_bind_manifest(self):
        atomic(self.root/'manifest.json',{'authority':{'preparation_only':True},'publication':str(self.root)});(self.root/'manifest.sha256').write_text('bound')
        atomic(self.root/'LIVE-AUTHORIZATION.json',{'approved':True,'plan_identity':'bound','scope':'full_frozen_study'})
        with self.assertRaises(ValueError):require_execution(self.root)
        atomic(self.root/'LIVE-REVIEW.json',{'approved':True,'plan_identity':'other','scope':'full_frozen_study'})
        with self.assertRaises(ValueError):require_execution(self.root)
        atomic(self.root/'LIVE-REVIEW.json',{'approved':True,'plan_identity':'bound','scope':'preparation_only'})
        with self.assertRaisesRegex(ValueError,'partial approval'):require_execution(self.root)
        atomic(self.root/'LIVE-REVIEW.json',{'approved':True,'plan_identity':'bound','scope':'full_frozen_study'});require_execution(self.root)
        atomic(self.root/'manifest.json',{'authority':{'preparation_only':True},'publication':str(self.root/'different')})
        with self.assertRaisesRegex(ValueError,'cannot move'):require_execution(self.root)

    def test_exact_saved_prefix_is_authoritative_when_retokenization_differs(self):
        tokenizer=Mock();tokenizer.decode.return_value='observed';tokenizer.encode.return_value=types.SimpleNamespace(ids=[999])
        case={'id':'untouched-failure','input_ids':[1]*638,'rendered_prompt':'full prompt<think>\n'}
        response={'finish_reason':'length','tokens':[7]*8192,'raw_text':'unfinished'}
        p=prefix_record(case,response,3072,tokenizer)
        self.assertEqual(p['prefix_tokens'],3710);self.assertEqual(p['input_ids'],[1]*638+[7]*3072)
        self.assertFalse(p['decoded_prefix_roundtrips']);self.assertEqual(p['original_rendered_prompt'],case['rendered_prompt'])

    def test_prefix_overflow_stops_without_trimming_instructions(self):
        tokenizer=Mock();case={'id':'long','input_ids':[1]*3000,'rendered_prompt':'all original instructions'}
        response={'finish_reason':'length','tokens':[7]*8192,'raw_text':'unfinished'}
        with self.assertRaisesRegex(ValueError,'no silent truncation'):prefix_record(case,response,3072,tokenizer)
        tokenizer.decode.assert_not_called()

    def test_completed_or_edited_regression_trace_is_not_admitted(self):
        tokenizer=Mock();case={'id':'x','input_ids':[1],'rendered_prompt':'x'}
        with self.assertRaises(ValueError):prefix_record(case,{'finish_reason':'eos','tokens':[7]*8192,'raw_text':'done'},1024,tokenizer)
        with self.assertRaises(ValueError):prefix_record(case,{'finish_reason':'length','tokens':[7]*8192,'raw_text':'</think>'},1024,tokenizer)

    def test_family_and_dose_are_not_an_implicit_search(self):
        self.assertEqual(validate_proposal({'layer':26,'columns':[5],'scale':.5})['columns'],[5])
        for p in [{'layer':27,'columns':[5],'scale':.5},{'layer':26,'columns':[5,6],'scale':.5},
            {'layer':26,'columns':[5],'scale':.9},{'layer':26,'columns':[5],'scale':.5,'tensor':'gate'}]:
            with self.assertRaises(ValueError):validate_proposal(p)

    def test_probe_counts_include_baseline_noop_and_static_control(self):
        self.assertEqual(sum(PHASE_COUNTS.values()),32);self.assertEqual(PHASE_COUNTS['baseline'],12)
        request={'phase':'baseline','conditions':_conditions(self.prefixes,'baseline',modes=('no_hook','capture','noop'))}
        validate_probe_request(self.plan,request,0)
        with self.assertRaisesRegex(ValueError,'budget'):validate_probe_request(self.plan,request,21)
        bad=copy.deepcopy(request);bad['conditions'][0]['mode']='channel'
        with self.assertRaises(ValueError):validate_probe_request(self.plan,bad,0)
        bad=copy.deepcopy(request);bad['conditions'][0]['id']='../outside'
        with self.assertRaisesRegex(ValueError,'Unsafe'):validate_probe_request(self.plan,bad,0)

    def test_only_two_shortlisted_units_cover_all_four_prefixes(self):
        atomic(self.root/'SHORTLIST.json',{'channels':[5,9]})
        request={'phase':'channels','conditions':_conditions(self.prefixes,'channels',channels=[5,9])}
        validate_probe_request(self.plan,request,12)
        request['conditions'][0]['channel']=7
        with self.assertRaisesRegex(ValueError,'Unapproved channel'):validate_probe_request(self.plan,request,12)

    def test_worker_uses_original_exact_ids_and_one_final_token_hook(self):
        api=Mock();api.forward.return_value=(np.zeros(3),{})
        prefix={'input_ids':[1,2,3]};deadline=object()
        probe_condition(api,'model',{'mode':'channel','channel':17},prefix,deadline)
        api.forward.assert_called_once_with('model',[1,2,3],deadline,hook=True,capture=True,
            intervention={'kind':'columns','name':'ffn_swiglu-26','columns':[17],'scale':.5})

    def test_noop_and_static_capture_have_distinct_semantics(self):
        api=Mock();api.forward.return_value=(np.zeros(3),{});prefix={'input_ids':[1]}
        probe_condition(api,'base',{'mode':'noop'},prefix,None)
        self.assertEqual(api.forward.call_args.kwargs['intervention']['scale'],1.)
        probe_condition(api,'static-model',{'mode':'capture'},prefix,None)
        self.assertIsNone(api.forward.call_args.kwargs['intervention'])
        probe_condition(api,'base',{'mode':'no_hook'},prefix,None)
        self.assertFalse(api.forward.call_args.kwargs['hook'])

    def test_capture_parity_fails_without_relaxing_tolerance(self):
        a=np.linspace(-1,1,100)
        self.assertTrue(parity_check(a,a.copy())['passed'])
        self.assertFalse(parity_check(a,a+.01)['passed'])
        with self.assertRaises(ValueError):parity_check(a,np.full(100,np.nan))

    def test_known_column_predicts_ffn_delta_and_wrong_coordinate_fails(self):
        base=np.array([1.,2.,3.]);column=np.array([.2,.4,.6]);changed=base-.5*2*column
        self.assertTrue(channel_delta_check(2,base,changed,column)['passed'])
        self.assertFalse(channel_delta_check(2,base,changed,np.array([1.,0.,0.]))['passed'])

    def effects(self,first=.01,second=.02):
        return [{'channel':j,'prefix_id':str(i),'contrast_margin':v,'reference_contrast_margin':0.,'contrast_margin_delta':v,'delta_validation':{'passed':True}} for j,v in [(5,first),(9,second)] for i in range(4)]

    def test_nonfinite_margins_deltas_and_means_cannot_select_patch(self):
        for key,value in [('contrast_margin',float('inf')),('reference_contrast_margin',float('nan')),('contrast_margin_delta',float('inf'))]:
            rows=self.effects();rows[0][key]=value
            with self.assertRaisesRegex(ValueError,'Nonfinite'):choose_channel(rows)
        rows=self.effects(1e308,.02)
        with self.assertRaisesRegex(ValueError,'Nonfinite surrogate mean'):choose_channel(rows)

    def test_both_improved_counterexample_never_claims_specificity(self):
        base=[{'id':'a','correct':False},{'id':'b','correct':False}]
        control=[{'id':'a','correct':False},{'id':'b','correct':True}]
        candidate=[{'id':'a','correct':True},{'id':'b','correct':True}]
        out=final_attribution(base,candidate,control)
        self.assertTrue(out['both_edited_artifacts_improved']);self.assertFalse(out['coordinate_specificity_claimed'])
        self.assertEqual(out['control_vs_untouched']['candidate_correct'],1)
        self.assertEqual(out['candidate_vs_control']['candidate_correct'],2)

    def test_shortlist_projection_alone_cannot_select_candidate(self):
        rows=self.effects(-.01,-.02)
        self.assertFalse(choose_channel(rows)['supported'])
        rows=self.effects();rows[0]['contrast_margin_delta']=-.1
        self.assertEqual(choose_channel(rows)['channel'],9)

    def test_selection_is_frozen_strength_with_lower_id_tie_break(self):
        self.assertEqual(choose_channel(self.effects(.02,.02))['channel'],5)
        rows=self.effects();rows[4]['delta_validation']['passed']=False
        self.assertEqual(choose_channel(rows)['channel'],5)

    def test_norm_control_uses_deployed_delta_and_excludes_shortlist(self):
        match=match_control(1.,[{'channel':5,'deployed_delta_l2':1.},{'channel':8,'deployed_delta_l2':1.02},{'channel':7,'deployed_delta_l2':1.02}],[5,9])
        self.assertTrue(match['matched']);self.assertEqual(match['channel'],7);self.assertFalse(match['promotable'])
        self.assertFalse(match_control(1.,[{'channel':8,'deployed_delta_l2':1.2}],[5,9])['matched'])
        with self.assertRaises(ValueError):match_control(1.,[{'channel':j,'deployed_delta_l2':1.} for j in range(9)],[])

    def test_shorter_failure_or_ceiling_accuracy_is_not_primary_support(self):
        base=[{'id':'a','correct':False},{'id':'b','correct':True}]
        self.assertFalse(behavior_comparison(base,copy.deepcopy(base))['useful_completion_support'])
        improved=[{'id':'a','correct':True},{'id':'b','correct':True}]
        self.assertTrue(behavior_comparison(base,improved)['useful_completion_support'])
        self.assertTrue(behavior_comparison(improved,improved)['ceiling'])
        regression=[{'id':'a','correct':True},{'id':'b','correct':False}]
        self.assertFalse(behavior_comparison(base,regression)['useful_completion_support'])

    def test_thinking_token_partition_accounts_for_closing_token(self):
        self.assertEqual(token_partition({'tokens':[1,2,99,3,4]},99),{'reasoning_tokens':2,'after_thinking_tokens':2,'closing_tokens':1,'total_tokens':5,'thinking_closed':True})
        self.assertEqual(token_partition({'tokens':[1,2,3]},99)['reasoning_tokens'],3)

    def test_baseline_reruns_are_in_eighteen_response_budget(self):
        self.assertEqual(SCHEDULED_TOKENS,18*8192);self.assertEqual(TOKEN_LIMIT,155648)
        self.assertEqual(2*8192*len(('development','preservation','confirmation'))*len(('untouched','candidate','control')),SCHEDULED_TOKENS)

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'.data/apwt-builder-teacher-20261104-003/manifest.json').is_file(), 'Private pinned codec manifest is not distributed; synthetic Q8 codec control not revalidated here')
    def test_synthetic_q8_roundtrip_and_spillover_are_measured(self):
        plan=read(Path(__file__).resolve().parents[1]/'.data/apwt-builder-teacher-20261104-003/manifest.json')
        sys.path.insert(0,plan['cpu_vendor_sources']['path'])
        from gguf import GGMLQuantizationType
        from gguf.quants import quantize,dequantize
        from weight_editor_targeted import q8_column_edit
        original=np.full((2,64),.1,dtype=np.float32);original[:,0]=1.
        changed=q8_column_edit(original,[0],.5)
        a=quantize(original,GGMLQuantizationType.Q8_0);b=quantize(changed,GGMLQuantizationType.Q8_0)
        self.assertTrue(np.array_equal(a.reshape(2,2,34)[:,1],b.reshape(2,2,34)[:,1]))
        stats=weight_delta_statistics(original,changed,dequantize(a,GGMLQuantizationType.Q8_0),dequantize(b,GGMLQuantizationType.Q8_0),0)
        self.assertEqual(stats['canonical_changed_entries'],2);self.assertEqual(stats['selected_changed_values'],2)
        self.assertGreater(stats['neighbor_changed_values'],0)
        reconstructed=a.reshape(2,2,34).copy();reconstructed[:,0]=b.reshape(2,2,34)[:,0]
        self.assertTrue(np.array_equal(reconstructed.reshape(b.shape),b))

    def test_unintended_canonical_neighbor_change_is_rejected(self):
        original=np.ones((2,4));changed=original.copy();changed[:,0]*=.5;changed[0,1]=.9
        with self.assertRaisesRegex(ValueError,'escaped'):weight_delta_statistics(original,changed,original,changed,0)

    def test_shared_screen_helper_cannot_misattribute_generation_budget(self):
        s=object.__new__(FocusStudy);s.root=self.root;s.plan={'models':{'unchanged':{'path':'base','sha256':'basehash'}},
            'interpreters':{'python':{'path':'unused'}},'tokenizers':{'editor_tokenizer':{}}};s.category='screen';s.phase_categories={};s.calls=0
        case={'id':'case1','split':'development','rendered_prompt':'frozen','input_ids':[1],'rng_seed':7}
        s.by_id={'case1':case};s.state={'phase':'teacher_screen'};s.arm='screen-untouched';s.deadline=Deadline(10)
        (self.root/'requests').mkdir();(self.root/'runs').mkdir()
        def fake_launch(root,folder,command,deadline):
            request=read(self.root/'requests/call-001.json');binding={'nonce':'fake','request_sha256':sha(self.root/'requests/call-001.json')}
            budget=TokenBudget(folder,8192,binding);budget.before_sample();budget.record('case1',7);budget.settle()
            atomic(folder/'case1.json',{'tokens':[7],'raw_text':'x','finish_reason':'eos','generated_tokens':1})
            return {'request_sha256':binding['request_sha256']}
        with patch('neuron_focus.require_execution'),patch('neuron_focus.launch',side_effect=fake_launch):
            rows=s.inference('editor',s.plan['models']['unchanged'],[case])
        self.assertEqual(s.category,'development_untouched');self.assertEqual(s.reconcile()['observed_categories']['development_untouched'],1)
        self.assertEqual(rows[0]['generated_tokens'],1)

    def simulated_execution(self,*,ceiling=False,candidate_gain=True,parity=True):
        study=types.SimpleNamespace(root=self.root,plan={'models':{'unchanged':{'path':'base','sha256':'b'}}})
        phases=[];responses=[];w=np.ones((3,12));h=np.ones(12)
        def probes(phase,conditions,model):
            phases.append((phase,len(conditions)));rows=[]
            for number,c in enumerate(conditions):
                path=self.root/(phase+'-'+str(number)+'.npz');out=np.zeros(3);logits=np.ones(3)
                if phase=='baseline' and c['mode']=='capture' and not parity:logits+=.01
                if c['mode']=='channel':out=-.5*h[c['channel']]*w[:,c['channel']]
                np.savez(path,logits=logits,**{'ffn_swiglu-26':h,'ffn_out-26':out})
                rows.append({**c,'capture':str(path),'contrast_margin':.02 if c.get('channel')==9 else .01 if c['mode']=='channel' else 0.})
            return rows
        def behavior(s,split,models,results,arms=('untouched','candidate','control')):
            if split=='confirmation':self.assertTrue((self.root/'MODELS-FROZEN.json').exists())
            for arm in arms:
                values=[True,True] if ceiling or split=='preservation' or arm=='candidate' and candidate_gain else [False,True]
                if arm=='control':values=[True,True] # Better control must never replace a failed candidate.
                rows=[{'id':split+'-'+str(i),'correct':value} for i,value in enumerate(values)]
                responses.extend((split,arm,row['id']) for row in rows);results.setdefault(split,{})[arm]=rows
        def artifacts(s,channel,excluded):
            self.assertEqual(channel,9);self.assertEqual(excluded,[5,9])
            atomic(self.root/'SELECTION.json',{'candidate_channel':9,'control_channel':7})
            models={'candidate':{'model':{'path':'candidate','sha256':'c'}},'control':{'model':{'path':'control','sha256':'x'}}}
            atomic(self.root/'MODELS-FROZEN.json',models);return models
        study.probes=probes
        with patch('neuron_focus.behavioral',side_effect=behavior),patch('neuron_focus.shortlist',return_value=([5,9],w)),patch('neuron_focus.norm_and_artifacts',side_effect=artifacts):
            result=execute(study)
        return result,phases,responses

    def test_scripted_full_controller_caps_32_probes_and_18_responses(self):
        result,phases,responses=self.simulated_execution()
        self.assertEqual(sum(n for _,n in phases),32);self.assertEqual(dict(phases),PHASE_COUNTS)
        self.assertEqual(len(responses),18);self.assertEqual(len(set(responses)),18)
        self.assertTrue(result['positive_narrow_teacher_effect']);self.assertFalse(result['student_inference'])

    def test_scripted_ceiling_does_not_construct_or_probe(self):
        result,phases,responses=self.simulated_execution(ceiling=True)
        self.assertEqual(result['status'],'baseline_ceiling_stop');self.assertEqual(len(responses),2);self.assertEqual(phases,[])
        self.assertFalse((self.root/'MODELS-FROZEN.json').exists())

    def test_scripted_better_control_never_rescues_candidate(self):
        result,phases,responses=self.simulated_execution(candidate_gain=False)
        self.assertEqual(result['status'],'development_support_stop');self.assertEqual(len(responses),6)
        self.assertFalse(any(split=='confirmation' for split,_,_ in responses));self.assertEqual(sum(n for _,n in phases),32)

    def test_scripted_parity_failure_stops_before_channel_intervention(self):
        with self.assertRaisesRegex(ValueError,'parity failed'):self.simulated_execution(parity=False)
        self.assertFalse((self.root/'CHANNEL-CHOICE.json').exists())


if __name__=='__main__':unittest.main()
