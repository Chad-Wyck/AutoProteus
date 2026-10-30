"""Owned training worker. ML imports occur only after a supervised start handshake."""
import argparse
from datetime import datetime, timezone
import gc
import json
import math
import os
from pathlib import Path
import random
import re
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lora6k_state import atomic, execute, identity, read


def update_progress(progress, name, data, timestamp):
    if name.endswith('_started'): progress['operation_started_at'] = timestamp
    if name.endswith(('_complete', '_committed')): progress.pop('operation_started_at', None)
    if name == 'update_committed': progress['completed_updates'] = data['update']
    if name in ('restore_complete', 'checkpoint_complete') and 'completed_updates' in data:
        progress['completed_updates'] = data['completed_updates']
    progress.update(last_event=name, updated=timestamp)


def cpu_tree(value):
    """Detach only adapter/optimizer state; never serialize frozen base weights."""
    if hasattr(value, 'detach'): return value.detach().to('cpu').clone()
    if isinstance(value, dict): return {k: cpu_tree(v) for k, v in value.items()}
    if isinstance(value, list): return [cpu_tree(v) for v in value]
    if isinstance(value, tuple): return tuple(cpu_tree(v) for v in value)
    return value


class Backend:
    def __init__(self, plan, rows, event):
        import torch
        import numpy as np
        from transformers import AutoModelForImageTextToText, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model
        from accelerate.hooks import remove_hook_from_module
        from sdpa_compat import enable_explicit_kv_repetition
        from checkpoint_offload import offload_checkpoint_inputs
        self.torch, self.np, self.event = torch, np, event
        self.plan = plan; cfg = plan['pilot']['configuration']
        torch.set_num_threads(2); random.seed(cfg['seed']); np.random.seed(cfg['seed']); torch.manual_seed(cfg['seed'])
        event('load_started')
        self.attention = enable_explicit_kv_repetition()
        root = Path(plan['project_root']); lock = read(root / plan['pilot']['model']['checkpoint_lock'])
        model = AutoModelForImageTextToText.from_pretrained(lock['checkpoint'], local_files_only=True,
            trust_remote_code=False, use_safetensors=True, torch_dtype=torch.float16,
            quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type='nf4',
                bnb_4bit_use_double_quant=True, bnb_4bit_compute_dtype=torch.float32, llm_int8_enable_fp32_cpu_offload=True),
            device_map={'': 0, 'model.language_model.embed_tokens': 'cpu'}, low_cpu_mem_usage=True, attn_implementation='sdpa')
        model.config.use_cache = False
        vocab = {id(model.get_input_embeddings().weight), id(model.get_output_embeddings().weight)}
        for parameter in model.parameters():
            parameter.requires_grad_(False)
            if id(parameter) not in vocab and parameter.dtype in (torch.float16, torch.bfloat16) and parameter.__class__.__name__ != 'Params4bit':
                parameter.data = parameter.data.float()
        embedding = model.get_input_embeddings(); remove_hook_from_module(embedding); embedding.to('cpu')
        if embedding.weight.dtype != torch.float16 or embedding.weight.device.type != 'cpu': raise ValueError('Embedding placement changed')
        embedding.register_forward_pre_hook(lambda module, inputs: (inputs[0].to('cpu'), *inputs[1:]))
        embedding.register_forward_hook(lambda module, inputs, value: value.to('cuda'))
        self.head = model.get_output_embeddings()
        if self.head.weight.requires_grad or self.head.weight.dtype != torch.float16: raise ValueError('Vocabulary changed')
        self.head.register_forward_pre_hook(lambda module, inputs: (inputs[0].to(module.weight.dtype), *inputs[1:]))
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
        suffixes = {'q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj',
            'in_proj_qkv', 'in_proj_qkvz', 'in_proj_z', 'in_proj_a', 'in_proj_b', 'out_proj'}
        targets = [n for n, m in model.named_modules() if n.split('.')[-1] in suffixes and isinstance(m, torch.nn.Linear)
            and not any(part in n.lower() for part in ('visual', 'vision'))]
        self.model = get_peft_model(model, LoraConfig(r=cfg['rank'], lora_alpha=cfg['alpha'], target_modules=targets,
            lora_dropout=0, bias='none', task_type='CAUSAL_LM'))
        self.offload = offload_checkpoint_inputs(self.model)
        self.trainable = [(n, p) for n, p in self.model.named_parameters() if p.requires_grad]
        layers = sorted({int(re.search(r'\.layers\.(\d+)\.', n).group(1)) for n, _ in self.trainable})
        if not (len(self.trainable) == plan['adapter']['gradient_tensors'] and layers == plan['adapter']['layers']
                and sum(p.numel() for _, p in self.trainable) == plan['adapter']['parameters']
                and all('lora_' in n and p.dtype == torch.float32 for n, p in self.trainable)):
            raise ValueError('Trainable architecture differs from the successful readiness check')
        if any(torch.count_nonzero(p).item() for n, p in self.trainable if 'lora_B' in n): raise ValueError('Fresh adapter B must be zero')
        self.signature = [(n, list(p.shape), str(p.dtype)) for n, p in self.trainable]
        settings = plan['optimizer']
        self.optimizer = torch.optim.AdamW([p for _, p in self.trainable], lr=cfg['learning_rate'],
            betas=tuple(settings['betas']), eps=settings['eps'], weight_decay=settings['weight_decay'])
        event('model_prepared', trainable_parameters=sum(p.numel() for _, p in self.trainable), memory=self.memory())
        from chunked_math_control import check
        from practical_math import selected_targets
        from transformers.loss.loss_utils import ForCausalLMLoss
        agreement = check(self.model, self.head, self.trainable, rows['train'][0], torch, ForCausalLMLoss, selected_targets, event)
        event('math_control_complete', control=agreement)

    def memory(self):
        torch = self.torch
        return {'allocated_mib': torch.cuda.memory_allocated() / 2**20, 'reserved_mib': torch.cuda.memory_reserved() / 2**20}

    def loss(self, row):
        torch = self.torch
        from practical_math import selected_targets
        from chunked_loss import loss
        tensors = {k: torch.tensor([row[k]], dtype=torch.long, device='cuda') for k in ('input_ids', 'attention_mask', 'labels')}
        positions, target = selected_targets(tensors['labels'])
        value = self.model.get_base_model().model(input_ids=tensors['input_ids'], attention_mask=tensors['attention_mask'], use_cache=False)
        return loss(value.last_hidden_state[:, positions, :], target, self.head, chunk_size=64)

    def evaluate(self, row):
        self.model.eval()
        with self.torch.no_grad(): value = float(self.loss(row).detach().cpu())
        self.cleanup()
        return value

    def cleanup(self):
        self.optimizer.zero_grad(set_to_none=True); gc.collect(); self.torch.cuda.empty_cache()

    def update(self, row, rate):
        torch = self.torch; started = time.monotonic()
        for group in self.optimizer.param_groups: group['lr'] = rate
        self.optimizer.zero_grad(set_to_none=True); self.model.train()
        value = self.loss(row)
        if not torch.isfinite(value).item(): raise ValueError('Nonfinite training loss')
        value.backward()
        if not all(p.grad is not None and torch.isfinite(p.grad).all().item() for _, p in self.trainable):
            raise ValueError('Missing/nonfinite adapter gradient')
        witnesses = [(n, p) for n, p in self.trainable if 'lora_B' in n and torch.count_nonzero(p.grad).item()]
        if not witnesses: raise ValueError('No nonzero adapter gradient')
        _, parameter = witnesses[0]; before = parameter.detach().clone()
        norm = torch.nn.utils.clip_grad_norm_([p for _, p in self.trainable], self.plan['pilot']['configuration']['gradient_clip'])
        if not torch.isfinite(norm).item(): raise ValueError('Nonfinite gradient norm')
        self.optimizer.step(); torch.cuda.synchronize()
        if torch.equal(before, parameter): raise ValueError('Optimizer did not update the adapter')
        if not all(torch.isfinite(p).all().item() for _, p in self.trainable): raise ValueError('Nonfinite updated adapter')
        measured = {'loss': float(value.detach().cpu()), 'gradient_norm': float(norm.cpu()),
            'finite_gradient_tensors': len(self.trainable), 'seconds': time.monotonic() - started, 'memory': self.memory()}
        del value, before, witnesses
        self.cleanup()
        return measured

    def save(self, path):
        from peft import get_peft_model_state_dict
        from safetensors.torch import save_file
        torch = self.torch; path = Path(path); (path / 'adapter').mkdir()
        state = cpu_tree(get_peft_model_state_dict(self.model))
        if not state or any('lora_' not in key for key in state): raise ValueError('Refusing to save non-adapter weights')
        save_file(state, str(path / 'adapter/adapter_model.safetensors'))
        self.model.peft_config['default'].save_pretrained(path / 'adapter')
        rng = self.np.random.get_state()
        torch.save({'optimizer': cpu_tree(self.optimizer.state_dict()), 'python_rng': random.getstate(),
            'torch_rng': torch.get_rng_state(), 'cuda_rng': torch.cuda.get_rng_state_all(),
            'numpy_rng': [rng[0], rng[1].tolist(), rng[2], rng[3], rng[4]],
            'signature': self.signature}, path / 'backend.pt')
        del state

    def restore(self, path):
        from peft import get_peft_model_state_dict, set_peft_model_state_dict
        from safetensors.torch import load_file
        torch = self.torch; path = Path(path)
        saved = torch.load(path / 'backend.pt', map_location='cpu', weights_only=True)
        if saved['signature'] != self.signature: raise ValueError('Checkpoint parameter order/shape changed')
        state = load_file(str(path / 'adapter/adapter_model.safetensors'), device='cpu')
        current = get_peft_model_state_dict(self.model)
        if state.keys() != current.keys() or any(state[k].shape != current[k].shape or not torch.isfinite(state[k]).all().item() for k in state):
            raise ValueError('Checkpoint adapter is incompatible/nonfinite')
        result = set_peft_model_state_dict(self.model, state)
        if result.unexpected_keys: raise ValueError('Unexpected adapter state')
        self.optimizer.load_state_dict(saved['optimizer'])
        random.setstate(saved['python_rng']); torch.set_rng_state(saved['torch_rng']); torch.cuda.set_rng_state_all(saved['cuda_rng'])
        rng = saved['numpy_rng']; self.np.random.set_state((rng[0], self.np.array(rng[1], dtype='uint32'), *rng[2:]))
        self.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True); parser.add_argument('--attempt', required=True)
    parser.add_argument('--supervisor-token', required=True)
    args = parser.parse_args(); run = Path(args.input).resolve(); attempt = Path(args.attempt).resolve()
    attempt.relative_to(run / 'attempts')
    gate = read(attempt / 'START.json')
    if gate.get('token') != args.supervisor_token or gate.get('plan_sha256') != (run / 'run-plan.sha256').read_text().strip():
        raise ValueError('Missing supervised start handshake')
    from lora6k import offline
    os.environ.update(offline()); os.environ.pop('PYTORCH_CUDA_ALLOC_CONF', None); os.environ.pop('PYTORCH_ALLOC_CONF', None)
    plan = read(run / 'run-plan.json')
    if identity(plan) != gate['plan_sha256']: raise ValueError('Worker plan changed')
    from lora6k_state import checked_rows
    rows = checked_rows(Path(plan['project_root']) / plan['dataset'], plan['pilot'])
    progress = {'pid': os.getpid(), 'status': 'starting', 'completed_updates': 0}
    def event(name, **data):
        timestamp = datetime.now(timezone.utc).isoformat()
        update_progress(progress, name, data, timestamp)
        atomic(attempt / 'progress.json', progress)
        record = {'event': name, 'time': timestamp, **data}
        with (attempt / 'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(record, allow_nan=False) + '\n'); stream.flush()
        print(json.dumps(record, allow_nan=False), flush=True)
    try:
        event('worker_started')
        backend = Backend(plan, rows, event)
        result = execute(backend, plan, rows, run, event, stop=lambda: (run / 'STOP').exists())
        progress.update(status=result['status'], completed_updates=result['completed_updates'])
        event('worker_complete')
        atomic(attempt / 'result.json', result)
    except BaseException as error:
        progress.update(status='failed', error_type=type(error).__name__, error=str(error))
        event('worker_failed')
        raise


if __name__ == '__main__': main()
