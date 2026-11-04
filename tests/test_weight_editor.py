"""Failure controls for the research harness. No model, GPU, network or API calls."""
import copy
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from lora6k_state import atomic, sha
import weight_editor_runtime as runtime
import weight_editor_owned as owned
import weight_editor_worker as worker
import lora6k_supervisor as supervisor
from weight_editor_drift import analyze
from weight_editor_prepare import select_data
from weight_editor_artifacts import proposal
from weight_editor_study import experiment, Study, check_coordinator_environment
from weight_editor_format import render_feedback, EDITOR_SUFFIX
from weight_repair_protocol import PROTOCOL
from weight_editor_reuse import target_reference, compatible_runtime, NATIVE_SOURCES


class FakeAPI:
    def __init__(self, tokens):
        self.tokens = tokens
        self.samples = 0
        self.lib = SimpleNamespace(llama_sampler_sample=self.sample, llama_sampler_free=Mock(),
                                   llama_free=Mock(), llama_n_ctx_seq=lambda ctx: 34816)

    def sample(self, sampler, ctx, index):
        self.samples += 1
        return next(sampler)

    def sampler(self, model, seed):
        return iter(self.tokens)

    def context_slots(self, model, slots):
        return object()

    def encode(self, model, text):
        return [1]

    def prefill(self, ctx, ids, seq, check):
        check()

    def batch(self, ctx, entries):
        pass


def request(cases=1, output=3):
    return {'kind': 'target', 'slots': 2, 'output_tokens': output, 'stop_token_ids': [9], 'request_seconds': 2700,
            'cases': [{'id': 'case-' + str(i), 'input_ids': [1], 'rendered_prompt': 'x', 'rng_seed': i} for i in range(cases)]}


class BudgetTests(unittest.TestCase):
    def test_zero_budget_never_enters_sampler(self):
        with temporary_directory() as directory:
            budget = runtime.TokenBudget(directory, 0, 'nonce')
            api = FakeAPI([1, 2, 3])
            try:
                with self.assertRaisesRegex(RuntimeError, 'before sampling'):
                    worker.generate(api, object(), request(), directory, None, budget, runtime.Deadline(10), lambda *a, **k: None)
            finally:
                budget.close()
            self.assertEqual(api.samples, 0)
            self.assertEqual(runtime.usage(directory, 'nonce')['charged_tokens'], 0)

    def test_two_sequences_with_one_token_remaining_cannot_overshoot(self):
        with temporary_directory() as directory:
            budget = runtime.TokenBudget(directory, 1, 'nonce')
            api = FakeAPI([1, 2, 3])
            try:
                with self.assertRaises(RuntimeError):
                    worker.generate(api, object(), request(2), directory, None, budget, runtime.Deadline(10), lambda *a, **k: None)
            finally:
                budget.close()
            self.assertEqual(api.samples, 1)
            self.assertEqual(runtime.usage(directory, 'nonce')['charged_tokens'], 1)

    def test_last_output_token_is_counted_without_extra_lookahead(self):
        with temporary_directory() as directory:
            budget = runtime.TokenBudget(directory, 10, 'nonce')
            api = FakeAPI([1, 2, 3, 4])
            tokenizer = SimpleNamespace(decode=lambda tokens, **kw: 'text')
            result = worker.generate(api, object(), request(), directory, tokenizer, budget, runtime.Deadline(10), lambda *a, **k: None)
            budget.settle()
            self.assertEqual(result, ['case-0'])
            self.assertEqual(api.samples, 3)
            self.assertEqual(runtime.usage(directory, 'nonce')['charged_tokens'], 3)
            self.assertTrue(runtime.usage(directory, 'nonce')['measurement_complete'])

    def test_crash_before_record_keeps_durable_reservation(self):
        with temporary_directory() as directory:
            budget = runtime.TokenBudget(directory, 100, 'nonce', block=4)
            budget.before_sample()
            budget.close()
            measured = runtime.usage(directory, 'nonce')
            self.assertEqual(measured['observed_tokens'], 0)
            self.assertEqual(measured['charged_tokens'], 4)
            self.assertEqual(measured['uncertain_tokens_upper_bound'], 4)
            self.assertFalse(measured['measurement_complete'])
            with self.assertRaises(ValueError):
                runtime.TokenBudget(directory, 100, 'nonce')

    def test_truncated_journal_is_explicit_and_settled_corruption_is_rejected(self):
        with temporary_directory() as directory:
            budget = runtime.TokenBudget(directory, 5, 'nonce', block=4)
            budget.before_sample(); budget.record('x', 7); budget.close()
            with (Path(directory) / 'tokens.jsonl').open('ab') as stream:
                stream.write(b'{"case":')
            measured = runtime.usage(directory, 'nonce')
            self.assertTrue(measured['truncated_journal_tail'])
            self.assertEqual(measured['charged_tokens'], 4)
            state = json.loads((Path(directory) / 'usage.json').read_text())
            state.update(state='settled', reserved=1, emitted=1)
            atomic(Path(directory) / 'usage.json', state)
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                runtime.usage(directory, 'nonce')

    def test_grader_failure_does_not_erase_successful_inference(self):
        with temporary_directory() as directory:
            root = Path(directory); folder = root / 'phase'; folder.mkdir()
            payload = root / 'request.json'; atomic(payload, request())
            binding = {'nonce': 'nonce', 'request_sha256': sha(payload)}
            budget = runtime.TokenBudget(folder, 10, binding)
            budget.before_sample(); budget.record('case-0', 9); budget.settle()
            atomic(folder / 'CLOSED.json', {'token': 'nonce'})
            atomic(folder / 'case-0.json', {'generated_tokens': 1})
            result = {'request_sha256': sha(payload), 'responses': ['case-0'], 'generated_tokens': 1}
            with patch.object(owned, 'launch', return_value=result):
                with self.assertRaisesRegex(RuntimeError, 'grader'):
                    owned.inference_phase(root, folder, [], runtime.Deadline(10), payload, root/'usage.json', 'phase', Mock(side_effect=RuntimeError('grader failed')))
            self.assertEqual(json.loads((root / 'usage.json').read_text())['charged_tokens'], 1)

    def test_failed_worker_without_closure_still_charges_uncertain_tail(self):
        with temporary_directory() as directory:
            root = Path(directory); folder = root / 'phase'; folder.mkdir()
            payload = root / 'request.json'; atomic(payload, request())
            binding = {'nonce': 'nonce', 'request_sha256': sha(payload)}
            budget = runtime.TokenBudget(folder, 10, binding, block=4)
            budget.before_sample(); budget.close()
            with patch.object(owned, 'launch', side_effect=RuntimeError('worker failed')):
                with self.assertRaisesRegex(RuntimeError, 'worker failed'):
                    owned.inference_phase(root, folder, [], runtime.Deadline(10), payload, root/'usage.json', 'phase', Mock())
            self.assertEqual(json.loads((root / 'usage.json').read_text())['charged_tokens'], 4)


class LifecycleTests(unittest.TestCase):
    def test_owned_launcher_cannot_return_success_when_worker_survives_cleanup(self):
        with temporary_directory() as directory:
            root = Path(directory); folder = root / 'phase'
            job = SimpleNamespace(attach_and_resume=Mock(), close=Mock())
            child = SimpleNamespace(pid=12345, returncode=0, poll=lambda: 0, wait=Mock(return_value=0))
            def spawn(command, **kwargs):
                atomic(folder/'RESULT.json', {'token': command[-2], 'status': 'completed', 'cleanup_complete': True})
                return child
            with patch.dict(sys.modules, {'windows_job': SimpleNamespace(Job=lambda **kw: job)}), \
                 patch.object(owned.subprocess, 'BELOW_NORMAL_PRIORITY_CLASS', 0x4000, create=True), \
                 patch.object(owned, 'admission'), patch.object(owned.subprocess, 'Popen', side_effect=spawn), \
                 patch.object(owned, 'alive', return_value=True), patch.object(owned.time, 'sleep'):
                with self.assertRaisesRegex(ValueError, 'closure'):
                    owned.launch(root, folder, ['fake'], runtime.Deadline(10))
            self.assertFalse(json.loads((folder/'CLOSED.json').read_text())['owned_worker_closed'])
            job.close.assert_called_once()

    def test_platform_queries_receive_remaining_deadline(self):
        clock = [0.]
        deadline = runtime.Deadline(1, clock=lambda: clock[0])
        def query(*args, **kwargs):
            self.assertEqual(kwargs['timeout'], 1)
            clock[0] = 2.
            return 'No running processes found'
        with patch.object(supervisor.subprocess, 'check_output', side_effect=query) as called:
            with self.assertRaises(TimeoutError):
                supervisor.ownership(remaining=deadline.remaining)
            self.assertEqual(called.call_count, 1)
        with patch.object(supervisor.subprocess, 'check_output') as called:
            with self.assertRaises(ValueError): supervisor.snapshot(timeout=0)
            called.assert_not_called()

    def test_slow_admission_cannot_admit_an_expired_phase(self):
        clock = [0.]
        deadline = runtime.Deadline(3, clock=lambda: clock[0])
        def observe(timeout):
            clock[0] = 4.
            return {'free_vram_mib': 9999, 'free_ram_kib': 16*2**20, 'free_commit_bytes': 8*2**30, 'disk_bytes': 30*2**30, 'utilization': 0}
        with self.assertRaises(TimeoutError):
            owned.admission(observe, deadline, sleep=lambda seconds: None, clock=lambda: clock[0])

    def test_child_deadline_includes_prefill_and_cannot_extend_parent(self):
        clock = [0.]
        parent = runtime.Deadline(4, clock=lambda: clock[0]); child = parent.child(2700)
        self.assertEqual(child.end, parent.end)
        clock[0] = 4.
        with self.assertRaises(TimeoutError): child.remaining()
        sample = {'free_ram_kib': 16*2**20, 'free_commit_bytes': 8*2**30, 'gpu': []}
        self.assertEqual(owned.running_guard(sample, {'request_deadlines': {'prefill': 3}}, 4, 10, 20*2**30), 'request_deadline')
        self.assertIsNone(owned.running_guard(sample, {'request_deadlines': {}}, 4, 10, 20*2**30))

    def test_between_batch_timers_are_cleared(self):
        with temporary_directory() as directory:
            budget = runtime.TokenBudget(directory, 10, 'n')
            events = []
            api = FakeAPI([9])
            worker.generate(api, object(), request(3), directory, SimpleNamespace(decode=lambda *a, **kw: ''), budget,
                            runtime.Deadline(10), lambda kind, **data: events.append((kind, data)))
            budget.settle()
            self.assertEqual(len([kind for kind, _ in events if kind == 'between_batches']), 2)
            self.assertTrue(all(not data['request_deadlines'] for kind, data in events if kind == 'between_batches'))
            self.assertEqual(api.samples, 3)

    def test_missing_vacuous_live_or_mismatched_closure_is_rejected(self):
        with temporary_directory() as directory:
            root = Path(directory); folder = root / 'phase'; folder.mkdir()
            with self.assertRaises(ValueError): runtime.completed_phases(root, [])
            with self.assertRaises(FileNotFoundError): runtime.completed_phases(root, ['phase'])
            result = {'token': 'n', 'status': 'completed', 'cleanup_complete': True}
            valid = {'token': 'n', 'status': 'completed', 'owned_worker_closed': True, 'returncode': 0, 'launcher_pid': 1, 'worker_pid': 2}
            atomic(folder/'RESULT.json', result)
            for change in ({'owned_worker_closed': False}, {'token': 'other'}, {'returncode': 1}, {'worker_pid': None}):
                atomic(folder/'CLOSED.json', {**valid, **change})
                with self.assertRaises(ValueError): runtime.completed(folder, is_alive=lambda pid: False)
            atomic(folder/'CLOSED.json', valid)
            with self.assertRaises(ValueError): runtime.completed(folder, is_alive=lambda pid: True)
            self.assertEqual(runtime.completed(folder, is_alive=lambda pid: False), result)

    def test_guards_survive_optimized_python_and_imports_are_cpu_inert(self):
        code = """import sys;sys.path.insert(0,'evaluations')
import weight_editor_worker,weight_editor_owned,weight_editor_native
from weight_editor_runtime import unique_artifact
try: unique_artifact('a'*64,{'a'*64})
except ValueError: pass
else: raise RuntimeError('optimized integrity bypass')
if any(n in sys.modules for n in ('torch','transformers','numpy','tokenizers')): raise RuntimeError('ML import')
print('inert')
"""
        result = subprocess.run([sys.executable, '-O', '-B', '-X', 'utf8', '-c', code], cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'inert')


class DesignTests(unittest.TestCase):
    def reference_fixture(self, root):
        folder=root/'cell'; folder.mkdir()
        cases=[{'id':'case-0','rendered_prompt':'x','input_ids':[1],'rng_seed':7}]
        model={'path':'model','sha256':'a'*64}; tokenizer={'path':'tokenizer','files':{'tokenizer.json':'b'*64}}
        payload={'kind':'target','slots':2,'output_tokens':32768,'request_seconds':2700,'stop_token_ids':[248044,248046],
                 'model_sha256':model['sha256'],'cases':cases,'tokenizer':tokenizer['path'],'tokenizer_files':tokenizer['files']}
        path=root/'request.json'; atomic(path,payload)
        budget=runtime.TokenBudget(folder,20,{'nonce':'n','request_sha256':sha(path)})
        budget.before_sample(); budget.record('case-0',248046); budget.settle()
        atomic(folder/'CLOSED.json',{'status':'completed','owned_worker_closed':True,'returncode':0,'token':'n','seconds':1})
        atomic(folder/'RESULT.json',{'status':'completed','cleanup_complete':True,'token':'n','request_sha256':sha(path),'generated_tokens':1,'responses':['case-0']})
        atomic(folder/'case-0.json',{'tokens':[248046],'generated_tokens':1,'rng_seed':7,'input_tokens':1,'context_per_slot':34816,'slots':2,'finish_reason':'eos'})
        atomic(folder/'GRADES.json',[{'id':'case-0','status':'ok','correct':True,'generated_tokens':1,'finish_reason':'eos'}])
        return folder,path,model,cases,tokenizer

    def test_only_exact_complete_target_references_can_be_reused(self):
        with temporary_directory() as directory:
            root=Path(directory); args=self.reference_fixture(root)
            self.assertEqual(target_reference(*args)['cases'],1)
            wrong=copy.deepcopy(args[3]); wrong[0]['rng_seed']=8
            with self.assertRaisesRegex(ValueError,'model/cases/seed'):
                target_reference(args[0],args[1],args[2],wrong,args[4])
            with self.assertRaisesRegex(ValueError,'model/cases/seed'):
                target_reference(args[0],args[1],{'sha256':'c'*64},args[3],args[4])
            response=json.loads((args[0]/'case-0.json').read_text()); response['tokens']=[0]
            atomic(args[0]/'case-0.json',response)
            with self.assertRaisesRegex(ValueError,'token count'):
                target_reference(*args)

    def test_changed_runtime_invalidates_reference_qualification(self):
        previous={'code':{name:'a'*64 for name in NATIVE_SOURCES},'engine_files':{'llama.dll':'b'*64},
                  'target_protocol':PROTOCOL,'target_slots':2,'models':{name:{'sha256':'c'*64} for name in ('repaired_target','fixed_control')},
                  'tokenizers':{'target_tokenizer':{'path':'x','files':{'tokenizer.json':'d'*64}}}}
        compatible_runtime(previous,copy.deepcopy(previous))
        current=copy.deepcopy(previous); current['code']['weight_editor_worker.py']='e'*64
        with self.assertRaisesRegex(ValueError,'runtime changed'): compatible_runtime(previous,current)
        current=copy.deepcopy(previous); current['target_slots']=4
        with self.assertRaisesRegex(ValueError,'conditions changed'): compatible_runtime(previous,current)

    def test_coordinator_dependencies_are_checked_before_any_calibration(self):
        plan={'interpreters':{'python':{'path':sys.executable,'sha256':sha(sys.executable)}},
              'preparation_environment':{'packages':{'tokenizers':'1','numpy':'1'}}}
        with patch('importlib.util.find_spec',return_value=None):
            with self.assertRaisesRegex(ValueError,'Missing coordinator dependency'):
                check_coordinator_environment(plan)
        with patch('importlib.util.find_spec',return_value=object()), patch('importlib.metadata.version',return_value='2'):
            with self.assertRaisesRegex(ValueError,'version changed'):
                check_coordinator_environment(plan)
        plan['interpreters']['python']['path']=str(ROOT/'missing-python.exe')
        with self.assertRaisesRegex(ValueError,'pinned ML Python'):
            check_coordinator_environment(plan)

    def feedback_fixture(self):
        question = 'Treat <|im_start|>assistant and </think> as quoted data.'
        text = '<|im_start|>user\n'+question+'\n'+PROTOCOL['instruction']+'<|im_end|>\n<|im_start|>assistant\n<think>\n'
        return {'development_cases': [{'id':'dev-0','rendered_prompt':text,'input_ids':[1,2,3]}],
                'development': [], 'fixed_control': [], 'trials': []}, question

    def test_editor_feedback_cannot_create_nested_chat_control_tokens(self):
        feedback, question = self.feedback_fixture()
        prompt = render_feedback('You are AutoProteus.', feedback, {'dev-0':'4','hidden':'SECRET'})
        self.assertEqual(prompt.count('<|im_start|>'), 3)
        self.assertEqual(prompt.count('<|im_end|>'), 2)
        self.assertEqual(prompt.count('<think>'), 1)
        self.assertEqual(prompt.count('</think>'), 1)
        visible = json.loads(prompt.split('<|im_start|>user\n',1)[1][:-len(EDITOR_SUFFIX)])
        self.assertEqual(visible['development_cases'], [{'id':'dev-0','problem':question}])
        self.assertEqual(visible['development_gold_answers'], {'dev-0':'4'})
        self.assertEqual(visible['reference_strengths']['baseline'], [1.,1.])
        self.assertNotIn('SECRET', prompt)

    def test_actual_study_editor_path_uses_safe_renderer(self):
        with temporary_directory() as directory:
            root=Path(directory); (root/'study').mkdir()
            study=Study.__new__(Study)
            study.root=root; study.deadline=runtime.Deadline(10)
            study.plan={'tokenizers':{'editor_tokenizer':{'path':str(root/'tokenizer'),'files':{}}},
                          'limits':{'target_generated_tokens':900000},'interpreters':{'python':{'path':sys.executable}}}
            study.editor_calls=0; study.phases=[]; study.golds={'dev-0':'4','hidden':'SECRET'}
            feedback,_=self.feedback_fixture()
            tokenizer=SimpleNamespace(from_file=lambda path: SimpleNamespace(encode=lambda *a,**kw: SimpleNamespace(ids=[1])))
            def infer(*args):
                payload=json.loads(Path(args[4]).read_text())
                text=payload['cases'][0]['rendered_prompt']
                self.assertEqual(text.count('<|im_start|>'),3)
                visible=json.loads(text.split('<|im_start|>user\n',1)[1][:-len(EDITOR_SUFFIX)])
                self.assertNotIn('rendered_prompt',visible['development_cases'][0])
                self.assertNotIn('input_ids',visible['development_cases'][0])
                return [{'text':'{"stop":true}'}]
            with patch.dict(sys.modules,{'tokenizers':SimpleNamespace(Tokenizer=tokenizer)}), \
                 patch('weight_editor_study.inference_phase',side_effect=infer):
                self.assertEqual(study.infer('editor-1',{'path':'dummy','sha256':'a'*64},feedback,editor=True),'{"stop":true}')

    def test_one_json_fence_is_supported_without_weakening_numeric_contract(self):
        valid='{"strength15":1.08,"strength19":1.15}'
        for language in ('json','JSON',''):
            self.assertEqual(proposal('```'+language+'\n'+valid+'\n```')['strengths'],[1.08,1.15])
        for value in ('```python\n'+valid+'\n```', 'prefix '+valid,
                      '```json\n'+valid+'\n```\n```json\n'+valid+'\n```',
                      '```json\n{"strength15":true,"strength19":1}\n```','{"stop":1}'):
            with self.assertRaises(ValueError): proposal(value)

    def scripted_study(self, *, confirmation_failure=False, build_failure=False, all_calibration_correct=False):
        plan = {'models': {key: {'path': key, 'sha256': str(i)*64} for i, key in enumerate(('editor_model', 'repaired_target', 'fixed_control'))}}
        cases = [{'id': split+'-'+str(i), 'split': split, 'rendered_prompt': 'PRIVATE-'+split+'-'+str(i), 'input_ids': [1], 'rng_seed': i}
                 for split, count in [('calibration', 8), ('heldout', 6)] for i in range(count)]
        calls, saves, feedback = [], {}, []
        def infer(name, model, values, *, editor=False):
            calls.append((name, 0 if editor else len(values)))
            if editor:
                feedback.append(copy.deepcopy(values))
                return json.dumps({'strength15': 1.05 + .01*len(feedback), 'strength19': 1.08})
            if name == 'selected-confirmation':
                self.assertIn('FROZEN-CANDIDATE.json', saves)
            return [{'id': c['id'], 'status': 'ok', 'correct': (all_calibration_correct or int(c['id'][-1]) < 3) if name == 'calibration'
                     else not (confirmation_failure and name == 'selected-confirmation' and c['id'].endswith('-4')),
                     'generated_tokens': 20, 'finish_reason': 'eos'} for c in values]
        def build(name, chosen, existing):
            if build_failure: raise ValueError('source hash corrupted')
            return {'path': name, 'sha256': str(3+len(saves))*64}
        result = experiment(plan, cases, {}, infer, build, lambda name, value: saves.update({name: copy.deepcopy(value)}))
        return result, calls, saves, feedback

    def test_scripted_full_coordinator_preserves_bounds_and_hides_confirmation(self):
        result, calls, saves, feedback = self.scripted_study()
        self.assertEqual(result['outcome'], 'fresh_local_heldout_observed')
        self.assertEqual(sum(count for _, count in calls), 36)
        self.assertEqual(len(feedback), 2)
        for visible in feedback:
            text = json.dumps(visible)
            self.assertNotIn('PRIVATE-heldout-', text)
            self.assertNotIn('PRIVATE-calibration-1', text)
            self.assertNotIn('PRIVATE-calibration-4', text)
        self.assertTrue(saves['CONFIRMATION.json']['selected']['qualified_quality_gain'])

    def test_confirmation_failure_cannot_be_carried_by_development_gain(self):
        result, calls, _, _ = self.scripted_study(confirmation_failure=True)
        self.assertEqual(result['outcome'], 'independent_confirmation_failed')
        self.assertEqual(result['heldout_untested'], 18)
        self.assertFalse(any('heldout' in name for name, _ in calls))

    def test_calibration_balance_stop_is_not_an_infrastructure_failure(self):
        result, calls, _, _ = self.scripted_study(all_calibration_correct=True)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['outcome'], 'calibration_pool_not_informative')
        self.assertEqual(calls, [('calibration', 8)])

    def test_candidate_source_failure_stops_instead_of_retrying_editor(self):
        with self.assertRaisesRegex(ValueError, 'source hash corrupted'):
            self.scripted_study(build_failure=True)

    def test_numeric_proposal_rejects_paths_code_nan_boolean_and_out_of_range(self):
        for value in ({'strength15': 1., 'strength19': 1., 'path': 'elsewhere'},
                      {'strength15': float('nan'), 'strength19': 1.},
                      {'strength15': True, 'strength19': 1.}, {'strength15': 1.4, 'strength19': 1.}):
            with self.assertRaises(ValueError): proposal(json.dumps(value))
        self.assertEqual(proposal('{"strength15":1.1,"strength19":1.2}')['strengths'], [1.1, 1.2])

    def test_post_rounding_duplicate_artifact_is_not_a_new_candidate(self):
        runtime.unique_artifact('a'*64, {'b'*64})
        with self.assertRaises(ValueError): runtime.unique_artifact('a'*64, {'a'*64})

    def test_efficiency_does_not_substitute_for_quality_or_empty_retention(self):
        base = [{'id': 'a', 'status': 'ok', 'correct': False, 'generated_tokens': 100}]
        other = [{**base[0], 'generated_tokens': 1}]
        self.assertFalse(runtime.verdict(base, other)['correctness_improved'])
        base.append({'id': 'b', 'status': 'ok', 'correct': True, 'generated_tokens': 100})
        other = [{**row, 'correct': True} for row in base]
        self.assertTrue(runtime.verdict(base, other)['correctness_improved'])
        other[1]['correct'] = False
        self.assertFalse(runtime.verdict(base, other)['retained'])

    def test_calibration_is_once_only_bounded_and_nonempty(self):
        rows = [{'id': str(i), 'status': 'ok', 'correct': i < 3} for i in range(8)]
        result = runtime.calibration_split(rows)
        self.assertEqual(result['development'], ['0', '3'])
        self.assertEqual(result['confirmation'], ['1', '4'])
        self.assertEqual(set(result['editor_may_see']), {'0', '3'})
        rows[1]['correct'] = rows[2]['correct'] = False
        with self.assertRaisesRegex(ValueError, 'without expanding'):
            runtime.calibration_split(rows)

    def test_data_selection_excludes_old_inputs_and_train_benchmark_overlap(self):
        benchmark = [{'id': str(i), 'problem': 'benchmark ' + str(i), 'answer': '1'} for i in range(500)]
        train = [{'problem': 'train ' + str(i), 'solution': r'\boxed{1}'} for i in range(40)]
        train.append({'problem': ' BENCHMARK   0 ', 'solution': r'\boxed{1}'})
        pool, heldout = select_data(train, benchmark, {'train 0', 'benchmark 1'}, {1, 2})
        self.assertEqual(len(pool), 8); self.assertEqual(len(heldout), 6)
        self.assertTrue(all(index not in {0, 1, 2, 40} for index, _ in pool))
        self.assertTrue(all(row['id'] != '1' for row in heldout))

    def test_saved_small_drift_is_not_requalified_by_argmax_or_probability_agreement(self):
        checks = [{'order': order, 'prompt': 1, 'position': 6, 'max_abs': .0016, 'tv': .00008,
                   'argmax_equal': True, 'passed': False} for order in ([0, 1, 2, 3], [3, 1, 0, 2])]
        result = analyze({'status': 'completed', 'cleanup_complete': True, 'models': [{'id': 'x', 'checks': checks}]})['models'][0]
        self.assertFalse(result['scored_four_slot_qualified'])
        self.assertFalse(result['cause_established'])
        self.assertEqual(len(result['repeated_failure_orders'][0]), 2)


if __name__ == '__main__':
    unittest.main()
