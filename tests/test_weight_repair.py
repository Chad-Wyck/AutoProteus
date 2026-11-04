"""Synthetic offline controls only: no assets, ML imports, sockets or GPU APIs."""
import copy
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
from test_seed import temporary_directory
import weight_repair as runner
import weight_repair_artifacts as artifacts
import weight_repair_protocol as protocol
import weight_repair_acquire as acquisition
from weight_repair_state import GUARDS, Receipts, guard_reason, summarize
from lora6k_state import atomic, identity, sha


def tensor_file(path, tensors):
    header, data = {}, bytearray()
    for name, (shape, values) in tensors.items():
        raw = struct.pack('<' + 'H' * len(values), *values)
        header[name] = {'dtype': 'BF16', 'shape': shape, 'data_offsets': [len(data), len(data) + len(raw)]}
        data.extend(raw)
    raw = json.dumps(header, separators=(',', ':')).encode()
    raw += b' ' * (-len(raw) % 8)
    Path(path).write_bytes(struct.pack('<Q', len(raw)) + raw + data)


def vector(values, dtype='<i8'):
    header = repr({'descr': dtype, 'fortran_order': False, 'shape': (len(values),)}).encode() + b'\n'
    fmt = {'<i8': 'q', '<u2': 'H'}[dtype]
    return b'\x93NUMPY\x01\x00' + struct.pack('<H', len(header)) + header + struct.pack('<' + fmt * len(values), *values)


def patch_file(path, indices=(0, 4), values=(0x4000, 0x4000)):
    with zipfile.ZipFile(path, 'w') as archive:
        for i in range(2):
            archive.writestr(f't{i}_idx.npy', vector(indices))
            archive.writestr(f't{i}_val.npy', vector(values, '<u2'))


class ArtifactTests(unittest.TestCase):
    def fixture(self, directory):
        directory = Path(directory); base, edited, patch_path = (directory / n for n in ('base.st', 'edited.st', 'edit.npz'))
        before = {'layer15': ([2, 4], [0x3f80] * 8), 'layer19': ([2, 4], [0x3f80] * 8),
                  'embedding': ([2], [0x3f80, 0x4000])}
        after = copy.deepcopy(before)
        for name in ('layer15', 'layer19'):
            after[name][1][0] = after[name][1][4] = 0x4000
        tensor_file(base, before); tensor_file(edited, after); patch_file(patch_path)
        left, right = artifacts.TensorFile(base), artifacts.TensorFile(edited)
        targets = {name: {'shape': [2, 4], 'base_sha256': left.digest(name), 'edited_sha256': right.digest(name)}
                   for name in ('layer15', 'layer19')}
        return base, edited, patch_path, targets, before, after

    def test_sparse_reconstruction_and_canonical_hashes(self):
        with temporary_directory() as directory:
            base, edited, patch_path, targets, _, _ = self.fixture(directory)
            original = sha(base); output = Path(directory) / 'result.st'
            receipt = artifacts.rebuild_sparse(base, patch_path, output, targets,
                changed_entries=4, columns=1, touched_entries=4)
            self.assertTrue(receipt['unchanged_tensor_audit'])
            self.assertEqual(artifacts.TensorFile(edited).inventory(), artifacts.TensorFile(output).inventory())
            self.assertEqual(sha(base), original)
            with self.assertRaises(ValueError):
                artifacts.rebuild_sparse(base, patch_path, base, targets, changed_entries=4, columns=1, touched_entries=4)
            with self.assertRaises(ValueError):
                artifacts.rebuild_sparse(base, patch_path, output, targets, changed_entries=4, columns=1, touched_entries=4)

    def test_bf16_to_fp32_promotion_is_exact_including_signed_zero_and_subnormal(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'bits.st'
            bits = [0, 0x8000, 1, 0x3f80, 0xc000]
            tensor_file(path, {'x': ([len(bits)], bits)})
            raw = b''.join(struct.pack('<I', value << 16) for value in bits)
            self.assertEqual(artifacts.TensorFile(path).digest('x', promoted=True), hashlib.sha256(raw).hexdigest())
            self.assertEqual(struct.unpack('<5f', raw), (0., -0., 2**-133, 1., -2.))

    def test_sparse_export_may_omit_targeted_entries_unchanged_after_bf16_rounding(self):
        with temporary_directory() as directory:
            base, edited, patch_path, targets, before, after = self.fixture(directory)
            for name in targets:
                after[name][1][4] = before[name][1][4]
            tensor_file(edited, after)
            for name in targets:
                targets[name]['edited_sha256'] = artifacts.TensorFile(edited).digest(name)
            patch_file(patch_path, indices=(0,), values=(0x4000,))
            receipt = artifacts.rebuild_sparse(base, patch_path, Path(directory) / 'sparse.st', targets,
                changed_entries=2, columns=1, touched_entries=4)
            self.assertEqual(receipt['stored_patch_assignments'], 2)
            self.assertEqual(receipt['targeted_entries'], 4)

    def test_wrong_base_extra_edit_nan_and_column_boundary_are_rejected(self):
        with temporary_directory() as directory:
            base, edited, _, targets, before, after = self.fixture(directory)
            for fault in ('wrong_base', 'extra_edit', 'nan', 'wrong_column'):
                with self.subTest(fault=fault):
                    damaged = copy.deepcopy(after)
                    if fault == 'wrong_base':
                        bad = copy.deepcopy(before); bad['embedding'][1][0] = 0x4040
                        tensor_file(base, bad)
                    elif fault == 'extra_edit': damaged['embedding'][1][0] = 0x4040
                    elif fault == 'nan': damaged['embedding'][1][0] = 0x7fc0
                    else: damaged['layer15'][1][1] = 0x4000
                    tensor_file(edited, damaged)
                    # A wrong base embedding changes the unchanged-tensor comparison.
                    with self.assertRaises(ValueError):
                        artifacts.audit_pair(base, edited, targets, changed_entries=4, columns=1)
                    tensor_file(base, before)

    def test_patch_wrong_target_hash_duplicate_or_negative_indices_nan_values(self):
        with temporary_directory() as directory:
            base, _, patch_path, targets, _, _ = self.fixture(directory)
            for indices, values in (((-1, 4), (0x4000, 0x4000)), ((0, 0), (0x4000, 0x4000)),
                                    ((0, 8), (0x4000, 0x4000)), ((0, 4), (0x7fc0, 0x4000))):
                patch_file(patch_path, indices, values)
                with self.assertRaises(ValueError):
                    artifacts.rebuild_sparse(base, patch_path, Path(directory) / 'out.st', targets,
                        changed_entries=4, columns=1, touched_entries=4)
            patch_file(patch_path)
            wrong = copy.deepcopy(targets); wrong['layer15']['edited_sha256'] = '0' * 64
            with self.assertRaises(ValueError):
                artifacts.rebuild_sparse(base, patch_path, Path(directory) / 'out.st', wrong,
                    changed_entries=4, columns=1, touched_entries=4)
            self.assertFalse((Path(directory) / 'out.st').exists())

    def test_truncated_overlapping_duplicate_header_and_pickle_vectors(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'bad.st'
            for raw in (b'bad', struct.pack('<Q', 2**30),
                        struct.pack('<Q', 13) + b'{"x":1,"x":2}',
                        struct.pack('<Q', 2) + b'{}'):
                path.write_bytes(raw)
                with self.assertRaises(ValueError): artifacts.TensorFile(path)
            tensor_file(path, {'x': ([2], [0, 0])}); raw = path.read_bytes(); path.write_bytes(raw[:-1])
            with self.assertRaises(ValueError): artifacts.TensorFile(path)
            header = {name: {'dtype': 'BF16', 'shape': [2], 'data_offsets': [0, 4]} for name in ('a', 'b')}
            raw = json.dumps(header).encode()
            path.write_bytes(struct.pack('<Q', len(raw)) + raw + b'\0' * 4)
            with self.assertRaises(ValueError): artifacts.TensorFile(path)
            for raw in (b'pickle', vector([0])[:-1], vector([0]).replace(b"'<i8'", b"'|O8'")):
                with self.assertRaises((ValueError, SyntaxError)): artifacts.npy_vector(raw)

    def test_tied_mapping_checks_head_identity_and_excludes_vision(self):
        inventory = {'model.language_model.embed_tokens.weight': {'sha256': 'same'},
                     'lm_head.weight': {'sha256': 'same'}, 'model.visual.foo': {'sha256': 'other'}}
        value = artifacts.text_mapping(inventory, tied_embeddings=True)
        self.assertEqual(value['mapping']['model.language_model.embed_tokens.weight'], 'model.embed_tokens.weight')
        self.assertEqual(value['omitted_non_text_tensors'], ['model.visual.foo'])
        inventory['lm_head.weight'] = {'sha256': 'different'}
        with self.assertRaises(ValueError): artifacts.text_mapping(inventory, tied_embeddings=True)
        del inventory['lm_head.weight']
        with self.assertRaises(ValueError): artifacts.text_mapping(inventory, tied_embeddings=False)


class ProtocolTests(unittest.TestCase):
    def test_gpu_worker_import_does_not_import_ml_or_start_cuda(self):
        code = ("import sys;sys.path.insert(0,'evaluations');import weight_repair_gpu_worker;"
                "assert 'torch' not in sys.modules and 'transformers' not in sys.modules;print('isolated')")
        value = subprocess.run([sys.executable, '-X', 'utf8', '-c', code], cwd=ROOT,
                               capture_output=True, text=True, timeout=10)
        self.assertEqual(value.returncode, 0, value.stderr)
        self.assertEqual(value.stdout.strip(), 'isolated')

    def test_readiness_greedy_stops_at_either_pinned_eos_without_extra_calls(self):
        from unittest.mock import Mock
        from weight_repair_gpu_worker import Worker
        class Logits:
            def __init__(self, value): self.value = value
            def __getitem__(self, key): return self
            def argmax(self, axis): return self
            def item(self): return self.value
        for terminal in (248044, 248046):
            worker = Worker.__new__(Worker)
            worker.torch = SimpleNamespace(tensor=lambda *a, **kw: object())
            worker.inputs = {'stop_token_ids': [248044, 248046]}
            worker.event = Mock(); worker.tokenizer = SimpleNamespace(decode=lambda *a, **kw: '')
            worker.logits = Mock(side_effect=[SimpleNamespace(logits=Logits(10), past_key_values=object()),
                                             SimpleNamespace(logits=Logits(terminal), past_key_values=object())])
            self.assertEqual(worker.greedy(object(), object(), 12), [10, terminal])
            self.assertEqual(worker.logits.call_count, 2)

    def test_math_equivalence_cases_are_explicit_but_missing_library_is_not_a_pass(self):
        self.assertEqual({case['name'] for case in protocol.GRADER_CASES},
            {'fraction', 'algebra', 'set', 'interval', 'interval_boundary', 'nested_braces',
             'wrong_number', 'no_box', 'malformed_last_box', 'thinking_only'})
        with patch.object(protocol, 'grade', side_effect=AssertionError('must not invoke an unpinned grader')):
            value = protocol.check_grader(sys.executable, {})
        self.assertEqual(value['status'], 'blocked_dependencies')
        self.assertFalse(value['passed']); self.assertEqual(value['cases_attempted'], 0)

    def test_wrong_thinking_penalty_length_and_early_stop_cannot_change_protocol(self):
        for key, value in (('enable_thinking', False), ('presence_penalty', 0),
                           ('max_new_tokens', 4096), ('early_repetition_stop', True)):
            bad = {**protocol.PROTOCOL, key: value}
            with self.subTest(key=key), self.assertRaises(ValueError): protocol.validate_protocol(bad)

    def test_presence_once_generated_only_positive_negative_eos_and_special_ids(self):
        logits = [2., -1., 0., 1.]
        # Generated special/EOS token IDs receive the same one-time penalty.
        expected = [2., -2.5, 0., -.5]
        a = protocol.sample_probabilities(logits, [1, 1, 3], temperature=1, top_p=1, top_k=4)
        b = protocol.sample_probabilities(expected, [], temperature=1, top_p=1, top_k=4)
        self.assertEqual(a, b)
        self.assertNotEqual(a, protocol.sample_probabilities(logits, [], temperature=1, top_p=1, top_k=4))
        self.assertAlmostEqual(sum(a), 1)
        # No prompt argument is mixed into generated-token history.
        self.assertEqual(protocol.sample_probabilities(logits, [1]), protocol.sample_probabilities(logits, [1, 1]))

    def test_top_k_top_p_order_and_finite_validation(self):
        values = protocol.sample_probabilities([3., 2., 1., 0.], [], temperature=1, top_k=2, top_p=.5)
        self.assertEqual(values, [1., 0., 0., 0.])
        for logits in ([float('nan')], [float('inf')], []):
            with self.assertRaises(ValueError): protocol.sample_probabilities(logits, [])

    def test_extraction_matches_nested_braces_reasoning_and_upstream_box_preference(self):
        cases = [(r'work \boxed{\frac{1}{2}}', r'\frac{1}{2}'),
                 (r'\boxed{3} </think> no final answer', None),
                 (r'\boxed{3} </think> \boxed{4}', '4'),
                 (r'\boxed{3} then \boxed{', None), (r'\boxed{}', None),
                 (r'\fbox{8}', '8'), (r'\boxed 5$ trailing', '5'),
                 (r'\boxed{2} then \fbox{9}', '2'), ('Final Answer: 5', None)]
        for text, expected in cases:
            with self.subTest(text=text): self.assertEqual(protocol.extract_answer(text), expected)

    def test_grader_errors_timeouts_and_bad_receipts_are_not_wrong_answers(self):
        for status in ('error', 'timeout', 'ok'):
            receipt = {'status': status, 'stdout': 'not json', 'stderr': 'failure'}
            with patch.object(protocol, 'owned_command', return_value=receipt):
                value = protocol.grade(sys.executable, r'\boxed{1}', '1')
            self.assertEqual(value['status'], 'grader_timeout' if status == 'timeout' else 'grader_error')
            self.assertIsNone(value['correct'])
        with patch.object(protocol, 'owned_command', side_effect=AssertionError('must not spawn')):
            value = protocol.grade(sys.executable, 'No answer.', '1')
        self.assertFalse(value['correct']); self.assertTrue(value['answer_omitted'])

    def test_numerical_path_controls_fail_on_scope_nan_drift_and_missing_path(self):
        reference = {'input_ids_sha256': 'ids', 'canonical_weights_sha256': 'weights',
                     'dtype': 'float32', 'logits': [0., .25, -1.]}
        rows = {name: {'reference': copy.deepcopy(reference), 'candidate': copy.deepcopy(reference)}
                for name in protocol.NUMERICAL_CONTROLS}
        result = protocol.numerical_controls(rows)
        self.assertFalse(result['hardware_qualified'])
        self.assertEqual(result['scope'], 'synthetic')
        for field, value in (('input_ids_sha256', 'other'), ('dtype', 'bfloat16'),
                             ('logits', [0., 1., -1.]), ('logits', [0., float('nan'), -1.])):
            bad = copy.deepcopy(rows); bad['base_restore']['candidate'][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError): protocol.numerical_controls(bad)
        del rows['attention_path']
        with self.assertRaises(ValueError): protocol.numerical_controls(rows)


class StateTests(unittest.TestCase):
    def test_guard_controls_include_deadline_grading_and_missing_counters(self):
        state = {'ram_bytes': 9 * 2**30, 'vram_bytes': 9 * 2**30, 'disk_bytes': 21 * 2**30,
                 'commit_bytes': 8 * 2**30, 'shared_gpu_bytes': 0, 'gpu_percent': 0}
        self.assertIsNone(guard_reason(state, phase_seconds=0, request_seconds=0, phase_limit=7200, admission=True))
        for key, value, expected in (('ram_bytes', 0, 'ram_floor'), ('commit_bytes', 0, 'commit_floor'),
                ('disk_bytes', 0, 'disk_floor'), ('vram_bytes', 0, 'vram_admission'),
                ('gpu_percent', 50, 'gpu_busy'), ('shared_gpu_bytes', 513 * 2**20, 'shared_gpu_allowance')):
            with self.subTest(key=key):
                self.assertEqual(guard_reason({**state, key: value}, phase_seconds=0, request_seconds=0,
                    phase_limit=7200, admission=True), expected)
        self.assertEqual(guard_reason(state, phase_seconds=7200, request_seconds=0, phase_limit=7200), 'cumulative_deadline')
        self.assertEqual(guard_reason(state, phase_seconds=0, request_seconds=2700, phase_limit=7200), 'request_deadline')
        self.assertEqual(guard_reason({}, phase_seconds=0, request_seconds=0, phase_limit=7200), 'resource_counters_unavailable')
        self.assertEqual(guard_reason(state, phase_seconds=math.nan, request_seconds=0, phase_limit=7200), 'resource_counters_unavailable')

    def test_transactional_resume_duplicates_checksum_source_and_interrupted_commit(self):
        slots = runner.schedule()['slots']
        with temporary_directory() as directory:
            store = Receipts(directory, 'binding', slots)
            value = {'status': 'completed', 'elapsed_seconds': 1, 'token_ids': [1, 2],
                     'finish_reason': 'eos', 'text': r'\boxed{1}', 'correct': True}
            store.commit(slots[0]['id'], value)
            self.assertEqual(store.records(), {slots[0]['id']: value})
            with self.assertRaises(ValueError): store.commit(slots[0]['id'], value)
            with self.assertRaises(ValueError): Receipts(directory, 'other', slots).records()
            staging = store.root / '.staging-crashed'; staging.mkdir()
            atomic(staging / 'response.json', value)
            self.assertEqual(len(store.records()), 1)
            atomic(store.root / slots[0]['id'] / 'response.json', {**value, 'correct': False})
            with self.assertRaises(ValueError): store.records()

    def test_cutoff_can_be_correct_but_timeout_cannot_be_scored_wrong(self):
        value = {'status': 'completed', 'elapsed_seconds': 2, 'token_ids': [1] * 32768,
                 'finish_reason': 'length', 'text': r'\boxed{1}', 'correct': True}
        Receipts.validate(value)
        with self.assertRaises(ValueError): Receipts.validate({**value, 'token_ids': [1]})
        with self.assertRaises(ValueError): Receipts.validate({**value, 'status': 'interrupted', 'correct': False})
        Receipts.validate({'status': 'interrupted', 'elapsed_seconds': 2, 'correct': None})

    def test_report_retains_missing_denominators_pairing_and_partial_timing(self):
        slots = runner.schedule()['slots']; records = {}
        for slot in slots[:2]:
            records[slot['id']] = {'status': 'completed', 'elapsed_seconds': 2, 'token_ids': [1],
                'finish_reason': 'eos', 'text': r'\boxed{1}', 'correct': slot['arm'] == 'edited'}
        records[slots[2]['id']] = {'status': 'resource_stop', 'elapsed_seconds': 1, 'correct': None}
        value = summarize(slots, records)
        self.assertEqual(value['matched_samples'], 1); self.assertEqual(value['paired_gains'], 1)
        self.assertEqual(sum(arm['missing'] for arm in value['arms'].values()), 29)
        self.assertEqual(sum(arm['infrastructure_observations'] for arm in value['arms'].values()), 1)
        self.assertFalse(value['arms']['base']['ttft_seconds']['complete'])


class PreparationTests(unittest.TestCase):
    def test_download_verification_checks_both_git_blobs_and_lfs_and_refuses_bad_bytes(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'asset'; raw = b'pinned public fixture'
            path.write_bytes(raw)
            digest = hashlib.sha256(raw).hexdigest()
            git = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
            self.assertEqual(acquisition.verify_download(path, {'size': len(raw), 'blobId': git}), digest)
            self.assertEqual(acquisition.verify_download(path, {'size': len(raw), 'lfs': {'sha256': digest}}), digest)
            for remote in ({'size': len(raw) + 1, 'blobId': git},
                           {'size': len(raw), 'blobId': '0' * 40},
                           {'size': len(raw), 'lfs': {'sha256': '0' * 64}}):
                with self.assertRaises(ValueError): acquisition.verify_download(path, remote)

    def test_acquisition_requires_explicit_authorization_before_network_or_directory_creation(self):
        with temporary_directory() as directory, patch.object(acquisition, 'get_inventory', side_effect=AssertionError('network')):
            path = Path(directory) / 'new'
            with self.assertRaises(ValueError): acquisition.acquire(path)
            self.assertFalse(path.exists())

    def test_asset_lock_refuses_moving_revisions_wrong_urls_and_missing_files(self):
        records = runner.assets()
        for name, value in records.items():
            value.update(sha256='a' * 64, bytes=1, revision=value['revision'] or 'b' * 40)
        self.assertEqual(runner.locked_assets(records), records)
        for key, value in (('revision', 'main'), ('sha256', 'unknown'), ('bytes', True), ('url', 'https://example.org/file')):
            bad = copy.deepcopy(records); bad['base/model.safetensors'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): runner.locked_assets(bad)
        del records['base/model.safetensors']
        with self.assertRaises(ValueError): runner.locked_assets(records)

    def test_sample_order_frozen_before_inputs_and_counterbalanced(self):
        a, b = runner.schedule(), runner.schedule()
        self.assertEqual(a, b); self.assertEqual(len(set(a['selected_ranks'])), 16)
        self.assertEqual(len(a['slots']), 32)
        self.assertEqual([s['arm'] for s in a['slots'][:4]], ['base', 'edited', 'edited', 'base'])
        for i in range(0, 32, 2): self.assertEqual(a['slots'][i]['rng_seed'], a['slots'][i + 1]['rng_seed'])
        rows = [{'id': f'problem-{n:03d}', 'problem': str(n), 'answer': str(n)} for n in range(500)]
        self.assertEqual(runner.bind_dataset(rows, a), runner.bind_dataset(list(reversed(rows)), a))
        with self.assertRaises(ValueError): runner.bind_dataset(rows[:-1], a)

    def test_metadata_collects_versions_without_importing_ml(self):
        value = runner.metadata(sys.executable)
        self.assertEqual(value['ml_imports'], [])
        self.assertIn('transformers', value['packages'])

    def test_prepare_verify_missing_assets_no_overwrite_or_silent_execution(self):
        with temporary_directory() as directory:
            root = Path(directory); output = root / '.data/run'
            with patch.object(runner, 'git', return_value='fixture-head'):
                result = runner.prepare(output, root=root)
            self.assertEqual(result['scheduled_pilot_requests'], 32)
            self.assertFalse(result['model_loaded']); self.assertFalse(result['downloads_started'])
            self.assertTrue(result['missing_assets']); self.assertTrue(result['unpinned_assets'])
            self.assertEqual(runner.report(output)['status'], 'no_live_observations')
            with patch.object(runner, 'git', return_value='fixture-head'), self.assertRaises(ValueError):
                runner.prepare(output, root=root)
            with self.assertRaises(ValueError): runner.rebuild(output)
            target = output / 'assets/base/model.safetensors'; target.parent.mkdir(parents=True)
            target.write_bytes(b'unreviewed asset')
            with self.assertRaises(ValueError): runner.verify(output)
            target.unlink()
            (output / 'code/weight_repair.py').write_text('changed', encoding='utf-8')
            with self.assertRaises(ValueError): runner.verify(output)

    def test_wrong_manifest_source_and_protocol_hashes_fail_before_any_runtime(self):
        with temporary_directory() as directory:
            root = Path(directory); output = root / '.data/run'
            with patch.object(runner, 'git', return_value='fixture-head'): runner.prepare(output, root=root)
            plan = json.loads((output / 'manifest.json').read_text())
            plan['protocol']['enable_thinking'] = False
            atomic(output / 'manifest.json', plan)
            with self.assertRaises(ValueError): runner.verify(output)
            (output / 'manifest.sha256').write_text(identity(plan))
            with self.assertRaises(ValueError): runner.verify(output)

    def test_live_and_download_commands_fail_closed(self):
        for command in ('acquire', 'preflight', 'run', 'resume'):
            with self.subTest(command=command):
                value = subprocess.run([sys.executable, '-X', 'utf8', str(ROOT / 'evaluations/weight_repair.py'),
                    command, '--input', 'must-not-be-opened'], text=True, capture_output=True, timeout=10)
                self.assertNotEqual(value.returncode, 0)
                self.assertIn('Execution hold', value.stderr)


class OwnedGraderProcessTests(unittest.TestCase):
    def test_timeout_closes_an_owned_descendant(self):
        with temporary_directory() as directory:
            ready, done = (Path(directory) / name for name in ('ready', 'done'))
            child = ('from pathlib import Path;import time;'
                     f'Path({str(ready)!r}).write_text("ready");time.sleep(2);'
                     f'Path({str(done)!r}).write_text("escaped")')
            parent = 'import subprocess,sys,time;subprocess.Popen([sys.executable,"-c",' + repr(child) + ']);time.sleep(30)'
            result = protocol.owned_command([sys.executable, '-c', parent], {}, 1)
            self.assertEqual(result['status'], 'timeout')
            self.assertTrue(ready.exists(), 'Descendant did not start: control is inconclusive')
            threading.Event().wait(1.3)
            self.assertFalse(done.exists(), 'Owned descendant survived its parent timeout')

    def test_real_owned_cpu_child_returns_or_times_out_without_touching_other_children(self):
        # Real subprocess/Job Object check with trusted synthetic Python only.
        sleeper = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(30)'])
        try:
            value = protocol.owned_command([sys.executable, '-c', 'print("ok")'], {}, 5)
            self.assertEqual(value['status'], 'ok'); self.assertEqual(value['stdout'].strip(), 'ok')
            value = protocol.owned_command([sys.executable, '-c', 'import time;time.sleep(30)'], {}, .2)
            self.assertEqual(value['status'], 'timeout')
            self.assertIsNone(sleeper.poll())
        finally:
            sleeper.terminate(); sleeper.wait(timeout=5)


if __name__ == '__main__': unittest.main()
