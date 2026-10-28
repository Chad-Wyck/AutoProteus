import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

from controller.config import DEFAULTS
from controller.isolation import seed_files
from controller.storage import atomic_json
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from observations import latency_metrics
from study_support import ResultCache, StudyQueue, identity
import model_study as study


class StudySupportTests(unittest.TestCase):
    def test_cache_requires_exact_identity_and_preserves_provenance(self):
        with temporary_directory() as directory:
            cache = ResultCache(directory)
            execute = Mock(return_value={'passed': True, 'session': 'original'})
            first, receipt = cache.run({'seed': 'a', 'fixture': 'unicode'}, execute)
            second, reused = cache.run({'seed': 'a', 'fixture': 'unicode'}, execute)
            self.assertEqual(first, second)
            self.assertFalse(receipt['hit'])
            self.assertTrue(reused['hit'])
            self.assertEqual(receipt['origin'], reused['origin'])
            self.assertEqual(execute.call_count, 1)
            for key in ({'seed': 'b', 'fixture': 'unicode'}, {'seed': 'a', 'fixture': 'bytes'}):
                self.assertFalse(cache.run(key, execute)[1]['hit'])

    def test_failed_and_interrupted_checks_are_not_cached(self):
        with temporary_directory() as directory:
            cache = ResultCache(directory)
            execute = Mock(return_value={'passed': False})
            for _ in range(2):
                self.assertFalse(cache.run({'key': 1}, execute, lambda row: row['passed'])[1]['hit'])
            self.assertEqual(execute.call_count, 2)
            with self.assertRaises(RuntimeError):
                cache.run({'key': 2}, Mock(side_effect=RuntimeError('infrastructure')))
            self.assertFalse((Path(directory) / (identity({'key': 2}) + '.json')).exists())

    def test_corrupt_cache_is_recomputed_and_returns_are_independent(self):
        with temporary_directory() as directory:
            cache = ResultCache(directory)
            execute = Mock(return_value={'passed': True, 'values': []})
            result, first = cache.run({'key': 1}, execute)
            result['values'].append('local change')
            self.assertEqual(cache.run({'key': 1}, execute)[0]['values'], [])
            path = Path(directory) / (first['key'] + '.json')
            record = json.loads(path.read_text())
            record['result']['passed'] = False
            atomic_json(path, record)
            self.assertFalse(cache.run({'key': 1}, execute)[1]['hit'])
            self.assertEqual(execute.call_count, 2)

    def test_completed_cells_resume_without_inference_and_cannot_change_plan(self):
        with temporary_directory() as directory:
            queue = StudyQueue(directory, 'frozen')
            execute = Mock(return_value={'passed': False})
            first = queue.run('model_first_01', execute)
            resumed = StudyQueue(directory, 'frozen')
            self.assertEqual(resumed.run('model_first_01', execute), first)
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(resumed.summary()['launched_attempts'], 1)
            with self.assertRaises(ValueError):
                StudyQueue(directory, 'changed')

    def test_interrupted_launch_is_preserved_and_retry_is_a_new_attempt(self):
        with temporary_directory() as directory:
            queue = StudyQueue(directory, 'frozen')
            queue.data['cells']['model_first_01'] = [{'cell': 'model_first_01', 'attempt': 1, 'state': 'running'}]
            queue.save()
            resumed = StudyQueue(directory, 'frozen')
            execute = Mock(return_value={'passed': True})
            self.assertEqual(resumed.run('model_first_01', execute)['state'], 'interrupted')
            execute.assert_not_called()
            retry = resumed.run('model_first_01', execute, retry=True)
            self.assertEqual(retry['attempt'], 2)
            self.assertEqual(resumed.data['cells']['model_first_01'][0]['state'], 'interrupted')
            self.assertEqual(resumed.summary()['launched_attempts'], 2)
            self.assertEqual(resumed.summary()['unresolved_cells'], [])

    def test_unlaunched_dependency_can_become_eligible_and_paths_cannot_escape(self):
        with temporary_directory() as directory:
            queue = StudyQueue(directory, 'frozen')
            queue.skip('growth', 'No accepted parent yet')
            self.assertEqual(queue.summary()['not_run'], 1)
            launched = queue.run('growth', lambda folder: {'passed': True})
            self.assertEqual(launched['state'], 'completed')
            self.assertEqual(launched['attempt'], 1)
            self.assertEqual(queue.summary()['launched_attempts'], 1)
            for name in ('../outside', 'a/b', 'C:\\outside'):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    queue.run(name, lambda _: {})

    def test_live_exception_retains_launch_and_needs_explicit_retry(self):
        with temporary_directory() as directory:
            queue = StudyQueue(directory, 'frozen')
            with self.assertRaises(RuntimeError):
                queue.run('first', Mock(side_effect=RuntimeError('fixture error')))
            execute = Mock()
            self.assertEqual(StudyQueue(directory, 'frozen').run('first', execute)['state'], 'error')
            execute.assert_not_called()

    def test_benchmark_checks_both_prompt_lengths_and_does_not_execute_tools(self):
        with temporary_directory() as directory:
            client = Mock(observation_failed=False)
            client.complete.return_value = {'content': '{"status":"completed","message":"BENCH_READY"}'}
            with patch.object(study, 'BudgetModelClient', return_value=client):
                result = study.benchmark(Path(directory), {**DEFAULTS, 'thinking': False}, {'tools': [{'type': 'function'}]})
            self.assertTrue(result['passed'])
            self.assertEqual(client.complete.call_count, 2)
            self.assertGreater(result['requests'][1]['reference_characters'], result['requests'][0]['reference_characters'])
            client.complete.return_value = {'content': '{"status":"needs_input","message":"BENCH_READY"}'}
            with temporary_directory() as other, patch.object(study, 'BudgetModelClient', return_value=client):
                self.assertFalse(study.benchmark(Path(other), DEFAULTS, {'tools': []})['passed'])

    @staticmethod
    def trace(payloads):
        rows = []
        for index, data in enumerate(payloads):
            for kind, value in (('call_start', {}), ('provider_request', {}), ('provider_response', data),
                                ('transport_end', {'finished': True}), ('call_end', {'status': 'returned', 'usage': {}})):
                rows.append({'type': kind, 'call_id': str(index), 'data': value, 'elapsed_seconds': 1})
        return rows

    def test_timing_units_and_partial_coverage_are_separate_from_trace_completeness(self):
        rows = self.trace([{'frames': [{'done': True, 'load_duration': 1000000000,
                                       'prompt_eval_duration': 2000000000, 'eval_duration': 3000000000}]},
                           {'payload': {'timings': {'prompt_ms': 500, 'predicted_ms': 1500}}}])
        result = latency_metrics(rows)['measurements']
        self.assertEqual(result['prompt_processing_seconds']['known_sum'], 2.5)
        self.assertEqual(result['generation_seconds']['known_sum'], 4.5)
        self.assertTrue(result['generation_seconds']['complete'])
        self.assertFalse(result['model_load_seconds']['complete'])
        self.assertEqual(result['model_load_seconds']['status'], 'partial')
        self.assertIsNone(result['cached_input_tokens']['known_sum'])

    def test_prompt_totals_do_not_imply_cache_hits_and_missing_times_are_not_zero(self):
        rows = self.trace([{'payload': {'usage': {'prompt_tokens': 1000}}}])
        result = latency_metrics(rows)
        self.assertIsNone(result['time_to_first_token'])
        self.assertTrue(all(value['status'] == 'unavailable' for value in result['measurements'].values()))
        rows[2]['data']['payload']['usage']['prompt_tokens_details'] = {'cached_tokens': 900}
        self.assertEqual(latency_metrics(rows)['measurements']['cached_input_tokens']['known_sum'], 900)

    def test_growth_contract_requires_actual_activation_use_and_mutation(self):
        plan = {'contracts': study.study.CONTRACTS, 'recipe': study.study.RECIPE, 'invoke_tool': 'inert'}
        for parent, added in [('sha256_file', 'format_json'), ('format_json', 'sha256_file'), ('csv_preview', 'sha256_file')]:
            selected, task = study.growth_task(parent, plan)
            self.assertEqual(selected, added)
            self.assertIn('finish needs_input requesting activation', task['task'])
            self.assertIn('Do not edit the seed after activation', task['task'])
            self.assertIn('audit.json', task['task'])
            self.assertNotIn('sample.txt unchanged during development', task['task'])
            if added == 'format_json':
                self.assertIn('Replace it with', task['task'])

    def test_summary_keeps_functional_growth_separate_from_completion_and_skips(self):
        with temporary_directory() as directory:
            queue = StudyQueue(directory, 'frozen')
            queue.run('fixture_first_01_sha256_file', lambda _: {'review': {'accepted': False}})
            queue.run('fixture_growth_01_sha256_file', lambda _: {'verified_extension': True,
                'final_artifacts_correct': True, 'scores': {'functional_growth': False}})
            queue.skip('fixture_first_01_format_json', 'not scheduled after interruption')
            summary = study.summarize(queue, {'profiles': [{'id': 'fixture'}], 'mode': 'full', 'scope': '',
                'upgrade_tasks': ['sha256_file', 'format_json'], 'repeats': 1})
            result = summary['profiles']['fixture']
            self.assertEqual(result['scheduled_first_tasks'], 2)
            self.assertEqual(result['first_attempts'], 1)
            self.assertEqual(result['second_verified'], 1)
            self.assertEqual(result['complete_growth'], 0)
            self.assertEqual(summary['queue']['not_run'], 1)

    def test_summary_separates_correct_basic_artifacts_from_completion_and_missing_checks(self):
        with temporary_directory() as directory:
            queue = StudyQueue(directory, 'frozen')
            queue.run('fixture_basic_files', lambda _: {'run': {
                'checks': [{'passed': True}], 'status': 'waiting', 'passed': False}})
            queue.run('fixture_basic_error', lambda _: {'run': {
                'checks': [], 'status': 'error', 'passed': False}})
            queue.skip('fixture_basic_skipped', 'Inference gate did not qualify')
            summary = study.summarize(queue, {'profiles': [{'id': 'fixture'}], 'mode': 'full', 'scope': '',
                'upgrade_tasks': [], 'repeats': 1})['profiles']['fixture']['ordinary']
            self.assertEqual(summary, {'attempts': 2, 'artifact_checks': 1, 'artifacts_correct': 1,
                'completion_observations': 2, 'explicit_completion': 0, 'passed': 0, 'not_run': 1})

    def test_basic_mode_runs_each_seed_without_requesting_an_extension(self):
        with temporary_directory() as directory:
            root=Path(directory);folder=root/'.data/basic';folder.mkdir(parents=True)
            names=['one','two','three','four','five']
            plan={'mode':'basic','repeats':2,'source':[],'source_sha256':'fixture','scope':'basic fixture',
                  'profiles':[{'id':'fixture','config':dict(DEFAULTS)}], 'upgrade_tasks':[],
                  'ordinary_tasks':names,'tasks':[{'name':name} for name in names],
                  'repeatability':{'sampling_seeds':[11,22]}}
            atomic_json(folder/'plan.json',plan);(folder/'plan.sha256').write_text(identity(plan))
            calls=[]
            def attempt(_folder,task,source,config,inputs,*extra):
                self.assertEqual(extra,())
                calls.append(config['sampling_seed'])
                return {'run':{'status':'waiting','passed':False,'checks':[{'passed':True}]}}
            with patch.object(study,'ROOT',root),patch.object(study,'check'),patch.object(study,'Appliance'),\
                    patch.object(study,'calibrate'),patch.object(study,'model_identity',return_value={'model':'fixture'}),\
                    patch.object(study,'benchmark',return_value={'passed':True}),patch.object(study,'trial',side_effect=attempt),\
                    patch('builtins.print'):
                study._run(SimpleNamespace(input=str(folder),retry=[]))
            self.assertEqual(calls,[11]*5+[22]*5)
            summary=json.loads((folder/'summary.json').read_text())['profiles']['fixture']
            self.assertEqual(summary['first_attempts'],0)
            self.assertEqual(summary['ordinary']['artifacts_correct'],10)
            self.assertEqual(summary['ordinary']['explicit_completion'],0)

    def test_candidate_check_cache_is_scoped_to_attempt_and_changed_source_invalidates(self):
        from controller.evaluation import freeze_source
        from controller.storage import Store
        with temporary_directory() as directory:
            folder = Path(directory)
            store = Store(folder / 'sessions')
            original = seed_files(ROOT)
            frozen = freeze_source(store, original, 'inert')
            inputs = {'trusted_sha256': {'grader': 'a'}, 'environment': {'vm': 'a'}}
            execute = Mock(return_value={'passed': True})
            first = study.Checks(folder / 'attempt-1', inputs)
            for _ in range(2):
                first.run(store, frozen, 'fixture', execute)
            self.assertEqual(execute.call_count, 1)
            fresh = study.Checks(folder / 'attempt-2', inputs)
            fresh.run(store, frozen, 'fixture', execute)
            self.assertEqual(execute.call_count, 2)
            changed = [dict(row) for row in original]
            import base64
            changed[0]['data'] = base64.b64encode(b'# Different inert source').decode()
            first.run(store, freeze_source(store, changed, 'different'), 'fixture', execute)
            self.assertEqual(execute.call_count, 3)

    def test_full_queue_activates_only_accepted_parents_and_resume_never_repeats_inference(self):
        with temporary_directory() as directory:
            root = Path(directory)
            output = root / '.data/study'
            output.mkdir(parents=True)
            source = [{'path': 'seed.py', 'data': 'IyBJbmVydA=='}]
            plan = {'profiles': [{'id': 'fixture', 'config': dict(DEFAULTS)}], 'mode': 'full', 'repeats': 1,
                'source': [], 'source_sha256': 'fixture', 'trusted_sha256': {}, 'environment': {}, 'scope': 'test',
                'ordinary_tasks': ['one', 'two', 'three'], 'tasks': [{'name': key} for key in ('one', 'two', 'three')],
                'upgrade_tasks': list(study.study.CONTRACTS), 'contracts': study.study.CONTRACTS,
                'recipe': study.study.RECIPE, 'invoke_tool': ''}
            atomic_json(output / 'plan.json', plan)
            (output / 'plan.sha256').write_text(identity(plan))
            def calibration(folder, source):
                atomic_json(folder / 'calibration.json', {'passed': True})
            calls = []
            def attempt(folder, task, starter, config, plan, feature=None, earlier=None):
                calls.append((feature, earlier, starter))
                if earlier:
                    self.assertEqual(starter, source)
                    return {'verified_extension': True, 'scores': {'functional_growth': True}}
                if feature:
                    if feature == 'sha256_file':
                        atomic_json(folder / 'review/candidate-source.json', source)
                    return {'review': {'accepted': feature == 'sha256_file'}}
                return {'run': {'passed': True}}
            args = SimpleNamespace(input=str(output), retry=[])
            with patch.object(study, 'ROOT', root), patch.object(study, 'check'), patch.object(study, 'Appliance'), \
                    patch.object(study, 'model_identity', return_value={'model': 'fixture'}), \
                    patch.object(study.study, 'self_check', side_effect=calibration), \
                    patch.object(study, 'benchmark', return_value={'passed': True}) as bench, \
                    patch.object(study, 'trial', side_effect=attempt):
                study.run(args)
                count = len(calls)
                study.run(args)
                self.assertEqual(len(calls), count)
                self.assertEqual(bench.call_count, 1)
            self.assertEqual(sum(earlier is not None for _, earlier, _ in calls), 1)
            summary = json.loads((output / 'summary.json').read_text())
            self.assertEqual(summary['profiles']['fixture']['first_attempts'], 3)
            self.assertEqual(summary['profiles']['fixture']['first_accepted'], 1)
            self.assertEqual(summary['profiles']['fixture']['second_attempts'], 1)
            self.assertEqual(summary['queue']['not_run'], 2)
            self.assertTrue(json.loads((output / 'calibration-receipt.json').read_text())['cache']['hit'])

    def assert_last_cell_change_rejected(self, changed):
        with temporary_directory() as directory:
            root = Path(directory)
            output = root / '.data/study'
            output.mkdir(parents=True)
            plan = {'profiles': [{'id': 'fixture', 'config': dict(DEFAULTS)}], 'mode': 'benchmark',
                    'repeats': 1, 'upgrade_tasks': [], 'scope': 'test', 'trusted_sha256': {}, 'environment': {}}
            atomic_json(output / 'plan.json', plan)
            (output / 'plan.sha256').write_text(identity(plan))
            state = {'changed': False}
            def check(plan):
                if state['changed'] and changed == 'source':
                    raise ValueError('Frozen source changed during the final attempt')
            def describe(config):
                return {'model': 'fixture', 'digest': 'new' if state['changed'] and changed == 'model' else 'old'}
            def benchmark(*args):
                state['changed'] = True
                return {'passed': True}
            with patch.object(study, 'ROOT', root), patch.object(study, 'check', side_effect=check), \
                    patch.object(study, 'model_identity', side_effect=describe), \
                    patch.object(study, 'benchmark', side_effect=benchmark):
                with self.assertRaises(ValueError):
                    study.run(SimpleNamespace(input=str(output), retry=[]))
            ledger = json.loads((output / 'queue.json').read_text())
            last = ledger['cells']['fixture_benchmark_01'][-1]
            self.assertEqual(last['state'], 'error')
            self.assertNotIn('result', last)

    def test_source_changed_during_last_cell_cannot_be_credited(self):
        self.assert_last_cell_change_rejected('source')

    def test_model_changed_during_last_cell_cannot_be_credited(self):
        self.assert_last_cell_change_rejected('model')

    def test_source_paths_and_host_preferences_are_not_modified_by_growth_preparation(self):
        before = dict(DEFAULTS)
        source = seed_files(ROOT)
        study.growth_task('format_json', {'contracts': study.study.CONTRACTS, 'recipe': study.study.RECIPE, 'invoke_tool': ''})
        self.assertEqual(source, seed_files(ROOT))
        self.assertEqual(DEFAULTS, before)
        with self.assertRaises(ValueError):
            study.private('../outside')

    @unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Real VM check requires explicit opt in')
    def test_cached_scripted_regression_preserves_real_vm_execution_and_provenance(self):
        from controller.evaluation import freeze_source
        from controller.storage import Store
        with temporary_directory() as directory:
            folder = Path(directory)
            store = Store(folder / 'sessions')
            frozen = freeze_source(store, seed_files(ROOT), 'Unchanged protected starter')
            checks = study.Checks(folder, {'trusted_sha256': study.trusted_files(), 'environment': study.environment()})
            first = checks.regressions(ROOT, store, frozen)
            self.assertTrue(first['passed'])
            with patch.object(study, 'run_regressions', side_effect=AssertionError('Must reuse the exact observation')):
                self.assertEqual(checks.regressions(ROOT, store, frozen), first)
            self.assertFalse(checks.receipts[0]['hit'])
            self.assertTrue(checks.receipts[1]['hit'])


if __name__ == '__main__':
    unittest.main()
