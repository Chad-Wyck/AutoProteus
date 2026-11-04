"""Explicit FP32/Pascal readiness worker. Imported by no application/seed path."""
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lora6k_state import atomic, identity, read, sha
from weight_repair_protocol import compare_logits, sample_probabilities


class Worker:
    def __init__(self, run):
        self.run = Path(run); self.plan = read(self.run / 'plan.json')
        if identity(self.plan) != (self.run / 'plan.sha256').read_text().strip(): raise ValueError('Plan changed')
        self.progress = {'operation': 'importing', 'operation_started': time.monotonic(), 'gpu_loaded': False}
        self.event('started')
        import torch
        self.torch = torch
        torch.set_num_threads(2); torch.set_num_interop_threads(2)
        torch.set_default_dtype(torch.float32)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        from transformers import AutoTokenizer, Qwen3_5ForCausalLM, Qwen3_5TextConfig
        from transformers.models.qwen3_5 import modeling_qwen3_5
        from transformers.integrations import sdpa_attention
        self.classes = Qwen3_5ForCausalLM, Qwen3_5TextConfig
        self.modeling = modeling_qwen3_5
        # Process-local Pascal GQA compatibility: no installed file is edited.
        sdpa_attention.use_gqa_in_sdpa = lambda *a, **kw: False
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_mem_efficient_sdp(True)
        torch.backends.cuda.enable_math_sdp(False)
        torch.backends.cuda.enable_cudnn_sdp(False)
        self.tokenizer = AutoTokenizer.from_pretrained(self.plan['tokenizer'], local_files_only=True, trust_remote_code=False)
        self.inputs = read(self.run / 'inputs.json')
        self.attention = 'sdpa'
        self.event('device', torch=torch.__version__, cuda=torch.version.cuda,
            name=torch.cuda.get_device_name(0), capability=list(torch.cuda.get_device_capability(0)),
            supported_arches=torch.cuda.get_arch_list())

    def event(self, kind, **values):
        row = {'type': kind, 'time': datetime.now(timezone.utc).isoformat(), **values}
        with (self.run / 'events.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, allow_nan=False) + '\n')
        self.progress.update(last_event=kind, **values)
        atomic(self.run / 'progress.json', self.progress)

    def operation(self, name, **values):
        self.progress.update(operation=name, operation_started=time.monotonic(), **values)
        self.event('operation', name=name)

    def load(self, arm):
        torch = self.torch
        from safetensors import safe_open
        self.operation('loading', arm=arm, gpu_loaded=False)
        model_class, config_class = self.classes
        config = config_class(**read(Path(self.plan['tokenizer']) / 'config.json'))
        config._attn_implementation = self.attention
        torch.manual_seed(0)
        model = model_class(config).eval()
        parameters = dict(model.named_parameters(remove_duplicate=False))
        mapping = self.plan['mapping']
        expected = set(parameters) - {'lm_head.weight'}
        if set(mapping.values()) != expected: raise ValueError('Runtime parameter mapping differs')
        path = self.plan['weights'][arm]
        with torch.no_grad(), safe_open(path, framework='pt', device='cpu') as source:
            for canonical, runtime in mapping.items():
                value = source.get_tensor(canonical).to(dtype=torch.float32)
                parameters[runtime].copy_(value)
                del value
        del parameters
        model = model.to(device='cuda', dtype=torch.float32)
        if model.lm_head.weight.data_ptr() != model.model.embed_tokens.weight.data_ptr():
            raise ValueError('Tied output head lost')
        checks = {}
        parameters = dict(model.named_parameters(remove_duplicate=False))
        with torch.no_grad(), safe_open(path, framework='pt', device='cpu') as source:
            for canonical, runtime in mapping.items():
                value = source.get_tensor(canonical).view(-1)
                actual = parameters[runtime].detach().view(-1)
                if actual.dtype != torch.float32: raise ValueError('Non-FP32 runtime weight')
                digest = hashlib.sha256()
                for offset in range(0, value.numel(), 2**20):
                    expected = value[offset:offset + 2**20].float()
                    observed = actual[offset:offset + 2**20].cpu()
                    if not torch.equal(expected, observed): raise ValueError('Runtime weight promotion differs')
                    digest.update(observed.numpy().tobytes())
                checks[canonical] = digest.hexdigest()
        atomic(self.run / f'weight-promotion-{arm}.json', checks)
        self.progress['gpu_loaded'] = True
        self.event('loaded', arm=arm, allocated_bytes=torch.cuda.memory_allocated(),
            reserved_bytes=torch.cuda.memory_reserved(), head_alias_verified=True)
        return model

    def release(self, model):
        # The caller must drop its own last reference before calling cleanup().
        del model

    def cleanup(self):
        gc.collect(); self.torch.cuda.empty_cache(); self.torch.cuda.synchronize()
        self.progress['gpu_loaded'] = False
        self.event('released', allocated_bytes=self.torch.cuda.memory_allocated(), reserved_bytes=self.torch.cuda.memory_reserved())

    def check(self, name, reference, candidate):
        result = compare_logits(reference.cpu().float().flatten().tolist(), candidate.cpu().float().flatten().tolist())
        self.event('numerical_control', control=name, **result)
        if not result['passed']: raise ValueError('Numerical control failed: ' + name)
        return result

    def logits(self, model, ids, **kwargs):
        torch = self.torch
        with torch.inference_mode():
            result = model(input_ids=ids, logits_to_keep=1, **kwargs)
        if not torch.isfinite(result.logits).all().item(): raise ValueError('Nonfinite logits')
        return result

    def sampler_controls(self):
        torch = self.torch
        from transformers.generation.logits_process import TemperatureLogitsWarper, TopKLogitsWarper, TopPLogitsWarper
        self.filters = (TemperatureLogitsWarper(.6), TopKLogitsWarper(20), TopPLogitsWarper(.95))
        vectors = [([2., -1., 0., 1.], [1, 1, 3]), ([float(i) / 20 for i in range(32)], [0, 12, 31]),
                   ([0., 0., 0., 0.], [0])]
        for i, (values, generated) in enumerate(vectors):
            scores = torch.tensor([values], device='cuda')
            seen = torch.zeros(len(values), dtype=torch.bool, device='cuda')
            seen[list(set(generated))] = True
            scores -= seen.float().unsqueeze(0) * 1.5
            blank = torch.empty((1, 0), dtype=torch.long, device='cuda')
            for processor in self.filters: scores = processor(blank, scores)
            actual = scores.softmax(-1).cpu().flatten().tolist()
            reference = sample_probabilities(values, generated, top_k=20)
            self.event('sampler_control', case=i, max_abs=max(abs(a - b) for a, b in zip(actual, reference)))
            if max(abs(a - b) for a, b in zip(actual, reference)) > 1e-6:
                raise ValueError('Sampler probability parity failed')

    def numerical(self):
        torch = self.torch
        self.operation('numerical_controls')
        self.sampler_controls()
        # Compare pure Torch linear-attention fallback paths on a fixed input.
        rng = torch.Generator().manual_seed(20261102)
        q, k, v = [torch.randn((1, 7, 2, 8), generator=rng) for _ in range(3)]
        g = -torch.rand((1, 7, 2), generator=rng); beta = torch.rand((1, 7, 2), generator=rng)
        kwargs = dict(g=g, beta=beta, use_qk_l2norm_in_kernel=True, output_final_state=True)
        cpu, _ = self.modeling.torch_chunk_gated_delta_rule(q, k, v, **kwargs)
        gpu, _ = self.modeling.torch_chunk_gated_delta_rule(q.cuda(), k.cuda(), v.cuda(),
            **{key: value.cuda() if hasattr(value, 'cuda') else value for key, value in kwargs.items()})
        recurrent, _ = self.modeling.torch_recurrent_gated_delta_rule(q.cuda(), k.cuda(), v.cuda(),
            **{key: value.cuda() if hasattr(value, 'cuda') else value for key, value in kwargs.items()})
        self.check('linear_attention_cpu_gpu', cpu, gpu)
        self.check('linear_attention_chunk_recurrent', gpu, recurrent)
        del q, k, v, g, beta, cpu, gpu, recurrent, kwargs
        ids = torch.tensor([self.inputs['probe']['input_ids']], device='cuda')
        model = self.load('base')
        model.config._attn_implementation = 'eager'
        reference = self.logits(model, ids, use_cache=False).logits.cpu()
        first = self.logits(model, ids[:, :-1], use_cache=True)
        incremental = self.logits(model, ids[:, -1:], use_cache=True, past_key_values=first.past_key_values)
        self.check('incremental_cache', reference, incremental.logits)
        del first, incremental
        split = ids.shape[1] // 2
        first = self.logits(model, ids[:, :split], use_cache=True)
        second = self.logits(model, ids[:, split:], use_cache=True, past_key_values=first.past_key_values)
        self.check('prompt_chunking', reference, second.logits)
        del first, second
        with torch.inference_mode():
            full = model(input_ids=ids, use_cache=False, logits_to_keep=0).logits[:, -1:, :]
        self.check('projection_last_position', reference, full)
        del full
        model.config._attn_implementation = 'sdpa'
        try:
            efficient = self.logits(model, ids, use_cache=False).logits
        except RuntimeError as error:
            # A supported eager route is allowed; never change precision/context.
            self.event('sdpa_unavailable', detail=str(error))
            self.attention = 'eager'; model.config._attn_implementation = 'eager'
            efficient = self.logits(model, ids, use_cache=False).logits
        self.check('attention_path', reference, efficient)
        del efficient
        model.config._attn_implementation = self.attention
        deterministic = self.greedy(model, ids, 12)
        del model; self.cleanup()
        edited = self.load('edited')
        edited_logits = self.logits(edited, ids, use_cache=False).logits.cpu()
        self.event('edited_probe', logits_sha256=hashlib.sha256(edited_logits.numpy().tobytes()).hexdigest())
        del edited_logits, edited; self.cleanup()
        restored = self.load('base')
        # Compare the same attention path, using an eager control reference.
        restored.config._attn_implementation = 'eager'
        restored_logits = self.logits(restored, ids, use_cache=False).logits.cpu()
        self.check('base_restore', reference, restored_logits)
        restored.config._attn_implementation = self.attention
        if self.greedy(restored, ids, 12) != deterministic: raise ValueError('Deterministic restoration differs')
        del restored_logits, reference, restored, ids; self.cleanup()
        atomic(self.run / 'NUMERICAL-PASSED.json', {'passed': True, 'attention': self.attention,
            'atol': 1e-5, 'rtol': 1e-4, 'runtime': 'FP32 Transformers port', 'source': self.plan['code']})

    def greedy(self, model, ids, count):
        torch = self.torch; generated, cache = [], None
        for _ in range(count):
            output = self.logits(model, ids, use_cache=True, past_key_values=cache)
            token = output.logits[:, -1].argmax(-1).item()
            generated.append(token); cache = output.past_key_values
            if token in self.inputs['stop_token_ids']: break
            ids = torch.tensor([[token]], device='cuda')
        self.event('deterministic_response', token_ids=generated,
                   text=self.tokenizer.decode(generated, skip_special_tokens=True))
        return generated

    def generate(self, slot):
        torch = self.torch
        practice = self.inputs['practices'][slot['practice']]
        self.operation('request', slot=slot['id'], generated_tokens=0)
        self.progress['request_started'] = time.monotonic()
        self.event('request_start', slot=slot, input_ids_sha256=practice['input_ids_sha256'])
        model = self.load(slot['arm'])
        model.config._attn_implementation = self.attention
        ids = torch.tensor([practice['input_ids']], device='cuda')
        rng = torch.Generator(device='cuda').manual_seed(slot['rng_seed'])
        seen = torch.zeros(model.config.vocab_size, dtype=torch.bool, device='cuda')
        blank = torch.empty((1, 0), dtype=torch.long, device='cuda')
        tokens, cache, ttft = [], None, None
        start = time.monotonic(); torch.cuda.reset_peak_memory_stats()
        journal = self.run / (slot['id'] + '.tokens.jsonl')
        with journal.open('x', encoding='utf-8') as stream, torch.inference_mode():
            for n in range(32768):
                if time.monotonic() - self.progress['request_started'] >= 2700: raise RuntimeError('Request watchdog')
                output = self.logits(model, ids, past_key_values=cache, use_cache=True)
                scores = output.logits[:, -1].float() - seen.float().unsqueeze(0) * 1.5
                for processor in self.filters: scores = processor(blank, scores)
                token = torch.multinomial(scores.softmax(-1), 1, generator=rng).item()
                tokens.append(token); seen[token] = True; cache = output.past_key_values
                if ttft is None: ttft = time.monotonic() - start
                stream.write(json.dumps({'index': n, 'token_id': token, 'elapsed_seconds': time.monotonic() - start}) + '\n')
                if n % 64 == 0:
                    stream.flush()
                    self.event('generation_progress', slot=slot['id'], generated_tokens=n + 1,
                        elapsed_seconds=time.monotonic() - start, allocated_bytes=torch.cuda.memory_allocated())
                if token in self.inputs['stop_token_ids']: break
                ids = torch.tensor([[token]], device='cuda')
        elapsed = time.monotonic() - start
        result = {'status': 'completed', 'slot': slot, 'input_tokens': len(practice['input_ids']),
            'token_ids': tokens, 'text': self.tokenizer.decode(tokens, skip_special_tokens=True, clean_up_tokenization_spaces=False),
            'raw_text': self.tokenizer.decode(tokens, skip_special_tokens=False, clean_up_tokenization_spaces=False),
            'finish_reason': 'eos' if tokens[-1] in self.inputs['stop_token_ids'] else 'length', 'generation_seconds': elapsed,
            'stop_token_ids': self.inputs['stop_token_ids'],
            'ttft_seconds': ttft, 'tokens_per_second': (len(tokens) - 1) / (elapsed - ttft) if len(tokens) > 1 else None,
            'peak_allocated_bytes': torch.cuda.max_memory_allocated(), 'peak_reserved_bytes': torch.cuda.max_memory_reserved(),
            'attention': self.attention, 'protocol': self.inputs['protocol'], 'readiness_only': True}
        atomic(self.run / (slot['id'] + '.json'), result)
        self.event('request_complete', slot=slot['id'], generated_tokens=len(tokens), finish_reason=result['finish_reason'],
            generation_seconds=elapsed, tokens_per_second=result['tokens_per_second'])
        del model, cache, output, scores, ids, seen; self.cleanup()
        self.progress.pop('request_started', None)


def main():
    run = Path(sys.argv[1]).resolve(); worker = None
    try:
        worker = Worker(run)
        worker.numerical()
        for slot in worker.inputs['slots']: worker.generate(slot)
        atomic(run / 'RESULT.json', {'status': 'readiness_completed', 'slots': 4,
            'behavioral_benchmark_started': False, 'runtime': 'FP32 Transformers/Pascal port'})
    except BaseException as error:
        atomic(run / 'RESULT.json', {'status': 'readiness_failed', 'error': type(error).__name__ + ': ' + str(error),
                                    'behavioral_benchmark_started': False})
        raise
    finally:
        if worker is not None:
            gc.collect(); worker.torch.cuda.empty_cache()


if __name__ == '__main__': main()
