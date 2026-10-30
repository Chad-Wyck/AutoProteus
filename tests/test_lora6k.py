"""CPU-only runner controls. No Qwen weights, CUDA work or generation."""
import copy
import json
import math
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'evaluations'))
import lora6k
import lora6k_state as state
import lora6k_supervisor as supervisor


class ArithmeticBackend:
    """Small scalar state machine, not a model or a training demonstration."""
    def __init__(self, fail_update=None, fail_save=None):
        self.value = {'weight': 0., 'momentum': 0., 'rng': 17, 'updates': 0}
        self.calls = []; self.evaluations = []; self.fail_update = fail_update; self.fail_save = fail_save
    def update(self, row, rate):
        self.calls.append(row['id']); self.value['updates'] += 1
        self.value['rng'] = (self.value['rng'] * 13 + 7) % 101
        self.value['momentum'] = .9 * self.value['momentum'] + self.value['rng'] / 101
        self.value['weight'] += rate * self.value['momentum']
        if self.value['updates'] == self.fail_update: raise RuntimeError('Crash after optimizer, before commit')
        return {'loss': 2. - self.value['weight'], 'gradient_norm': self.value['momentum']}
    def evaluate(self, row):
        self.evaluations.append(row['id']); return 2. - self.value['weight']
    def save(self, path):
        state.atomic(path / 'backend.json', self.value)
        if self.value['updates'] == self.fail_save: raise RuntimeError('Partial checkpoint write')
    def restore(self, path): self.value = state.read(path / 'backend.json')


class RunnerTests(unittest.TestCase):
    def fixtures(self):
        plan = {'pilot': {'configuration': {'learning_rate': .01, 'warmup_updates': 1}}}
        rows = {'train': [{'id': 'train-' + str(i)} for i in range(3)],
            'validation': [{'id': key, 'bucket': key, 'group': 'heldout-' + str(i % 2), 'completion_tokens': i + 1}
                for i, key in enumerate(('activation', 'capability_use', 'save_output', 'completion'))]}
        return plan, rows

    def run_fake(self, root, backend, stop=lambda: False):
        plan, rows = self.fixtures()
        return state.execute(backend, plan, rows, root, lambda *a, **kw: None, stop)

    def test_uninterrupted_epoch_records_validation_and_retains_two_commits(self):
        with temporary_directory() as directory:
            root = Path(directory); backend = ArithmeticBackend()
            result = self.run_fake(root, backend)
            self.assertEqual(result['status'], 'completed_one_epoch')
            self.assertEqual(backend.calls, ['train-0', 'train-1', 'train-2'])
            self.assertEqual(len(list((root / 'checkpoints').glob('step-*'))), 2)
            self.assertEqual(result['baseline']['examples'], 4)
            self.assertEqual(result['candidate']['examples'], 4)
            self.assertFalse(result['generation_started'])
            self.assertFalse(result['adapter_exported_for_inference'])

    def test_resume_restores_cursor_optimizer_and_rng_after_uncommitted_update(self):
        for failure in ('update', 'save'):
            with self.subTest(failure=failure), temporary_directory() as directory:
                root = Path(directory); clean = ArithmeticBackend(); self.run_fake(root / 'clean', clean)
                failed = ArithmeticBackend(**{'fail_' + failure: 2})
                with self.assertRaises(RuntimeError): self.run_fake(root / 'interrupted', failed)
                resumed = ArithmeticBackend(); result = self.run_fake(root / 'interrupted', resumed)
                self.assertEqual(resumed.value, clean.value)
                self.assertEqual(resumed.calls, ['train-1', 'train-2'])
                self.assertEqual(result['candidate_checkpoint'], 'step-0003')

    def test_recovery_uses_committed_directory_if_latest_pointer_was_not_saved(self):
        with temporary_directory() as directory:
            root = Path(directory); original = state.atomic
            def crash(path, value):
                if Path(path).name == 'LATEST.json' and value['checkpoint'] == 'step-0002':
                    raise RuntimeError('Crash between commit and pointer')
                original(path, value)
            with patch.object(state, 'atomic', side_effect=crash), self.assertRaises(RuntimeError):
                self.run_fake(root, ArithmeticBackend())
            resumed = ArithmeticBackend(); self.run_fake(root, resumed)
            self.assertEqual(resumed.calls, ['train-2'])
            self.assertEqual(resumed.value['updates'], 3)

    def test_corrupt_or_differently_bound_checkpoint_never_silently_falls_back(self):
        with temporary_directory() as directory:
            root = Path(directory); self.run_fake(root, ArithmeticBackend())
            path = root / 'checkpoints/step-0003/backend.json'; path.write_text('{}')
            plan, _ = self.fixtures()
            with self.assertRaisesRegex(ValueError, 'Corrupt'): state.Checkpoints(root / 'checkpoints', state.identity(plan)).latest()
            with self.assertRaisesRegex(ValueError, 'different'): state.Checkpoints(root / 'checkpoints', 'other-plan').latest()

    def test_graceful_stop_commits_last_update_then_resumes_without_repeating_it(self):
        with temporary_directory() as directory:
            root = Path(directory); first = ArithmeticBackend()
            stopped = self.run_fake(root, first, stop=lambda: first.value['updates'] == 1)
            self.assertEqual(stopped['status'], 'paused'); self.assertEqual(stopped['completed_updates'], 1)
            resumed = ArithmeticBackend(); self.run_fake(root, resumed)
            self.assertEqual(resumed.calls, ['train-1', 'train-2'])

    def test_nonfinite_update_does_not_advance_checkpoint(self):
        with temporary_directory() as directory:
            root = Path(directory); backend = ArithmeticBackend()
            backend.update = lambda *a: {'loss': math.nan, 'gradient_norm': 1.}
            with self.assertRaisesRegex(ValueError, 'Nonfinite'): self.run_fake(root, backend)
            plan, _ = self.fixtures()
            self.assertEqual(state.Checkpoints(root / 'checkpoints', state.identity(plan)).latest()['progress']['completed_updates'], 0)

    def test_learning_rate_uses_absolute_frozen_update_number(self):
        cfg = {'learning_rate': 5e-5, 'warmup_updates': 5}
        self.assertAlmostEqual(state.learning_rate(0, 93, cfg), 1e-5)
        self.assertAlmostEqual(state.learning_rate(4, 93, cfg), 5e-5)
        self.assertAlmostEqual(state.learning_rate(92, 93, cfg), 5e-6)
        with self.assertRaises(ValueError): state.learning_rate(93, 93, cfg)

    def test_partial_validation_resumes_only_against_same_checkpoint_and_valid_checksum(self):
        with temporary_directory() as directory:
            root = Path(directory); _, rows = self.fixtures(); backend = ArithmeticBackend()
            path = root / 'validation.json'; checkpoint = {'manifest_sha256': 'fixed'}
            self.assertIsNone(state.validate(backend, rows['validation'], path, checkpoint, lambda *a, **kw: None,
                stop=lambda: len(backend.evaluations) == 2))
            resumed = ArithmeticBackend()
            result = state.validate(resumed, rows['validation'], path, checkpoint, lambda *a, **kw: None, lambda: False)
            self.assertEqual(resumed.evaluations, ['save_output', 'completion']); self.assertEqual(result['examples'], 4)
            with self.assertRaisesRegex(ValueError, 'another checkpoint'):
                state.validate(resumed, rows['validation'], path, {'manifest_sha256': 'changed'}, lambda *a: None, lambda: False)
            value = state.read(path); value['records'][0]['nll'] = .01; state.atomic(path, value)
            with self.assertRaisesRegex(ValueError, 'checksum'):
                state.validate(resumed, rows['validation'], path, checkpoint, lambda *a: None, lambda: False)

    def test_validation_weights_tokens_and_reports_bucket_and_lineage_macros_separately(self):
        records = [{'id': '1', 'bucket': 'activation', 'group': 'A', 'targets': 1, 'nll': 1.},
                   {'id': '2', 'bucket': 'completion', 'group': 'B', 'targets': 3, 'nll': 3.}]
        result = state.summarize_validation(records)
        self.assertEqual(result['token_weighted_nll'], 2.5)
        self.assertEqual(result['workflow_macro_nll'], 2.)
        self.assertEqual(result['lineage_macro_nll'], 2.)

    def test_guards_cover_ram_commit_shared_memory_operation_time_and_cumulative_budget(self):
        guards = {'minimum_free_host_ram_mib': 6144, 'minimum_commit_headroom_mib': 4096,
            'shared_gpu_memory_mib': 4096, 'update_seconds': 600, 'full_run_seconds': 14400}
        healthy = {'free_ram_kib': 10 * 1024**2, 'free_commit_bytes': 10 * 2**30, 'gpu': []}
        self.assertIsNone(supervisor.reason(healthy, guards, 1, 1))
        for field, bad, expected in [('free_ram_kib', 1, 'host_ram_floor'), ('free_commit_bytes', 1, 'commit_floor'),
                ('gpu', [{'SharedUsage': 4096 * 2**20 + 1}], 'shared_gpu_allowance')]:
            self.assertEqual(supervisor.reason({**healthy, field: bad}, guards, 1, 1), expected)
        self.assertEqual(supervisor.reason(healthy, guards, 601, 1), 'operation_time_guard')
        self.assertEqual(supervisor.reason(healthy, guards, 1, 14400), 'cumulative_time_guard')
        self.assertEqual(supervisor.reason(healthy, guards, 1, 1, stopped=True), 'operator_stop')

    def test_start_without_explicit_flags_never_checks_gpu_or_constructs_worker(self):
        with patch.object(supervisor, 'idle') as gpu, patch.object(supervisor.subprocess, 'Popen') as process:
            with self.assertRaisesRegex(ValueError, 'Explicit'): supervisor.start(SimpleNamespace())
            gpu.assert_not_called(); process.assert_not_called()

    def test_wddm_desktop_context_is_not_a_compute_owner_but_unknown_and_real_compute_are_blocked(self):
        rows = [['123', '[Insufficient Permissions]', '[N/A]'], ['456', r'C:\Discord\Discord.exe', '[N/A]']]
        self.assertEqual(len(supervisor.check_owners(rows, {123: 'dwm.exe', 456: 'Discord.exe'}, [])), 2)
        for bad_rows, names, engines in [
            ([['123', 'python.exe', '[N/A]']], {123: 'python.exe'}, []),
            ([['123', 'custom-inference.exe', '[N/A]']], {}, []),
            ([['123', 'Discord.exe', '1024']], {123: 'Discord.exe'}, []),
            (rows, {123: 'dwm.exe', 456: 'Discord.exe'}, [{'UtilizationPercentage': 1}]),
            ([['unknown', 'Discord.exe', '[N/A]']], {}, [])]:
            with self.assertRaises(ValueError): supervisor.check_owners(bad_rows, names, engines)

    def test_importing_runner_and_worker_does_not_import_ml_or_use_gpu(self):
        import subprocess
        code = ('import sys;sys.path.insert(0,' + repr(str(ROOT / 'evaluations')) + ');'
            "import lora6k,lora6k_worker;assert not any(n in sys.modules for n in ('torch','transformers','peft'));print('no ML imports')")
        answer = subprocess.check_output([sys.executable, '-X', 'utf8', '-c', code], text=True)
        self.assertIn('no ML imports', answer)

    def test_checkpoint_storage_cannot_escape_owned_root(self):
        with temporary_directory() as directory:
            with self.assertRaises(ValueError): state.inside(directory, '../outside')

    def test_progress_never_advertises_an_uncommitted_update_as_saved(self):
        from lora6k_worker import update_progress
        progress = {'completed_updates': 1}
        update_progress(progress, 'checkpoint_started', {'completed_updates': 2}, 'start')
        self.assertEqual(progress['completed_updates'], 1)
        self.assertEqual(progress['operation_started_at'], 'start')
        update_progress(progress, 'update_committed', {'update': 2}, 'end')
        self.assertEqual(progress['completed_updates'], 2)
        self.assertNotIn('operation_started_at', progress)
        update_progress(progress, 'restore_complete', {'completed_updates': 7}, 'resume')
        self.assertEqual(progress['completed_updates'], 7)

    @unittest.skipUnless(os.name == 'nt', 'Windows owned-process primitive')
    def test_closing_owned_job_terminates_only_its_suspended_child(self):
        import subprocess
        from controller.windows_job import Job
        child = None; job = Job(vm_limits=False)
        try:
            child = subprocess.Popen([sys.executable, '-X', 'utf8', '-c',
                "import time;print('owned-ready',flush=True);time.sleep(30)"], stdout=subprocess.PIPE,
                text=True, creationflags=subprocess.CREATE_NO_WINDOW | 0x4)
            job.attach_and_resume(child)
            self.assertEqual(child.stdout.readline().strip(), 'owned-ready')
            job.close(); child.wait(timeout=15)
            # Windows kill-on-job-close may report exit code zero. Exiting
            # within 15 seconds proves the 30-second sleeper did not survive.
            self.assertIsNotNone(child.returncode)
        finally:
            job.close()
            if child is not None:
                if child.poll() is None: child.kill(); child.wait(timeout=15)
                if child.stdout: child.stdout.close()


@unittest.skipUnless((ROOT / '.data/lora6k-pilot-20261029/pilot-plan-v2.json').exists(), 'Private reviewed local-Qwen data not shipped')
class ReviewedDatasetTests(unittest.TestCase):
    def test_reviewed_dataset_matches_frozen_order_masks_teacher_and_disjoint_groups(self):
        folder = ROOT / '.data/lora6k-pilot-20261029'
        pilot = state.read(folder / 'pilot-plan-v2.json')
        rows = state.checked_rows(folder / 'dataset', pilot)
        self.assertEqual([r['id'] for r in rows['train']], pilot['epoch_order'])
        self.assertEqual([len(rows[key]) for key in ('train', 'validation')], [93, 27])
        self.assertFalse({r['group'] for r in rows['train']} & {r['group'] for r in rows['validation']})

    def test_even_rehashed_data_cannot_admit_remote_or_adapter_teachers_or_unmasked_context(self):
        folder = ROOT / '.data/lora6k-pilot-20261029'
        for fault in ('teacher', 'remote', 'mask'):
            with self.subTest(fault=fault), temporary_directory() as directory:
                dataset = Path(directory) / 'dataset'; shutil.copytree(folder / 'dataset', dataset)
                pilot = state.read(folder / 'pilot-plan-v2.json'); manifest = state.read(dataset / 'manifest.json')
                name = 'train.jsonl' if fault != 'mask' else 'train-tokens.jsonl'
                rows = [json.loads(line) for line in (dataset / name).read_text(encoding='utf-8').splitlines()]
                if fault == 'teacher': rows[0]['metadata']['teacher']['adapter'] = True
                elif fault == 'remote': rows[0]['metadata']['teacher']['endpoint'] = 'remote'
                else: rows[0]['labels'][0] = rows[0]['input_ids'][0]
                (dataset / name).write_text(''.join(json.dumps(row) + '\n' for row in rows), encoding='utf-8')
                manifest['files'][name] = pilot['dataset_files'][name] = state.sha(dataset / name)
                state.atomic(dataset / 'manifest.json', manifest); pilot['dataset_manifest_sha256'] = state.sha(dataset / 'manifest.json')
                with self.assertRaisesRegex(ValueError, 'teacher|mask'): state.checked_rows(dataset, pilot)


@unittest.skipUnless(os.environ.get('AUTOPROTEUS_LORA_CPU_TESTS') == '1', 'Optional installed-ML CPU serialization control')
class TorchCPUCheckpointTests(unittest.TestCase):
    def test_real_peft_optimizer_and_rng_roundtrip_on_tiny_cpu_model(self):
        import random
        import numpy as np
        import torch
        from transformers import GPT2Config, GPT2LMHeadModel
        from peft import LoraConfig, get_peft_model
        from lora6k_worker import Backend
        model = get_peft_model(GPT2LMHeadModel(GPT2Config(n_layer=1, n_head=1, n_embd=8, vocab_size=16, n_positions=16,
            bos_token_id=0, eos_token_id=1)), LoraConfig(r=2, lora_alpha=4, target_modules=['c_attn'],
            task_type='CAUSAL_LM', lora_dropout=0, fan_in_fan_out=True))
        backend = object.__new__(Backend)
        # CUDA methods are stubbed, not merely hidden by a device selector.
        class CPUOnly:
            cuda = SimpleNamespace(get_rng_state_all=lambda: [], set_rng_state_all=lambda state: None, empty_cache=lambda: None)
            def __getattr__(self, name): return getattr(torch, name)
        backend.torch = CPUOnly(); backend.np = np; backend.model = model
        backend.trainable = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
        backend.signature = [(n, list(p.shape), str(p.dtype)) for n, p in backend.trainable]
        backend.optimizer = torch.optim.AdamW([p for _, p in backend.trainable], lr=.01)
        model(torch.tensor([[1, 2, 3]]), labels=torch.tensor([[1, 2, 3]])).loss.backward(); backend.optimizer.step()
        with temporary_directory() as directory:
            root = Path(directory); backend.save(root)
            before = [p.detach().clone() for _, p in backend.trainable]
            expected = (torch.rand(1), random.random(), np.random.rand())
            for _, parameter in backend.trainable:
                with torch.no_grad(): parameter.add_(1)
            backend.optimizer.param_groups[0]['lr'] = .5
            backend.restore(root)
            self.assertTrue(all(torch.equal(p, old) for (_, p), old in zip(backend.trainable, before)))
            self.assertEqual(backend.optimizer.param_groups[0]['lr'], .01)
            observed = (torch.rand(1), random.random(), np.random.rand())
            self.assertTrue(torch.equal(observed[0], expected[0])); self.assertEqual(observed[1:], expected[1:])
            self.assertTrue(backend.optimizer.state)


if __name__ == '__main__': unittest.main()
