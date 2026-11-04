"""Offline protocol controls and an externally timed, CPU-only math grader."""
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys


PROTOCOL = {'name': 'think35', 'enable_thinking': True, 'temperature': .6, 'top_p': .95,
    'top_k': 20, 'presence_penalty': 1.5, 'max_new_tokens': 32768, 'context_tokens': 34816,
    'instruction': r'Please reason step by step, and put your final answer within \boxed{}.',
    'skip_special_tokens': True, 'score': 'mean_sample_correctness', 'math_verify': '0.9.0',
    'early_repetition_stop': False, 'truncate_input': False}

GRADER_CASES = (
    {'name': 'fraction', 'text': r'\boxed{\frac{1}{2}}', 'gold': '0.5', 'correct': True},
    {'name': 'algebra', 'text': r'\boxed{(x+1)^2}', 'gold': 'x^2+2*x+1', 'correct': True},
    {'name': 'set', 'text': r'\boxed{\{1,2\}}', 'gold': r'\{2,1\}', 'correct': True},
    {'name': 'interval', 'text': r'\boxed{[0,1]}', 'gold': '[0,1]', 'correct': True},
    {'name': 'interval_boundary', 'text': r'\boxed{(0,1)}', 'gold': '[0,1]', 'correct': False},
    {'name': 'nested_braces', 'text': r'\boxed{\frac{2}{4}}', 'gold': r'\frac{1}{2}', 'correct': True},
    {'name': 'wrong_number', 'text': r'\boxed{2}', 'gold': '3', 'correct': False},
    {'name': 'no_box', 'text': 'The answer is 3.', 'gold': '3', 'correct': False},
    {'name': 'malformed_last_box', 'text': r'\boxed{3} then \boxed{', 'gold': '3', 'correct': False},
    {'name': 'thinking_only', 'text': r'\boxed{3}</think>No final answer.', 'gold': '3', 'correct': False})


def validate_protocol(value):
    if value != PROTOCOL:
        raise ValueError('Frozen think35 protocol changed')


def sample_probabilities(logits, generated, *, temperature=.6, top_p=.95, top_k=20, presence_penalty=1.5):
    """Pure reference: generated-token presence, temperature, top-k, then top-p.

    A future runtime processor must be checked against this AND pinned vLLM
    semantics before sampler equivalence is claimed. No RNG or GPU is used here.
    """
    if (not logits or any(not math.isfinite(v) for v in logits) or temperature <= 0
            or not 0 < top_p <= 1 or type(top_k) is not int or top_k < 1
            or any(type(t) is not int or not 0 <= t < len(logits) for t in generated)):
        raise ValueError('Invalid sampling input')
    seen = set(generated)
    values = [(v - (presence_penalty if i in seen else 0)) / temperature for i, v in enumerate(logits)]
    threshold = sorted(values, reverse=True)[min(top_k, len(values)) - 1]
    maximum = max(values)
    probabilities = [math.exp(v - maximum) if v >= threshold else 0. for v in values]
    total = sum(probabilities); probabilities = [p / total for p in probabilities]
    order = sorted(range(len(values)), key=lambda i: (-probabilities[i], i))
    keep, cumulative = set(), 0.
    for index in order:
        keep.add(index); cumulative += probabilities[index]
        if cumulative >= top_p: break
    total = sum(probabilities[i] for i in keep)
    return [p / total if i in keep else 0. for i, p in enumerate(probabilities)]


def extract_answer(text):
    """Match exp8 mathqa.extract, including its boxed-before-fbox preference."""
    if '</think>' in text: text = text.rsplit('</think>', 1)[1].strip()
    index = text.rfind(r'\boxed')
    if index < 0: index = text.rfind(r'\fbox')
    if index < 0: return None
    key = r'\boxed' if text.startswith(r'\boxed', index) else r'\fbox'
    rest = text[index + len(key):]; trimmed = rest.lstrip()
    if trimmed.startswith('{'):
        depth = 0
        for i, char in enumerate(trimmed):
            if char == '{': depth += 1
            elif char == '}':
                depth -= 1
                if depth == 0: return trimmed[1:i].strip() or None
        return None
    if key == r'\boxed' and rest.startswith(' '):
        return rest.strip().split('$')[0].split('\n')[0].strip() or None
    return None


def offline_environment():
    return {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'HF_HUB_OFFLINE': '1',
        'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
        'PYTHONDONTWRITEBYTECODE': '1', 'OMP_NUM_THREADS': '1', 'MKL_NUM_THREADS': '1'}


def owned_command(command, payload, timeout):
    """Bound a newly created owned process tree, never a PID discovered later."""
    if not 0 < timeout <= 60: raise ValueError('CPU worker timeout must be within 60 seconds')
    job, process = None, None
    try:
        kwargs = {'creationflags': 0x00000004 | 0x08000000} if os.name == 'nt' else {'start_new_session': True}
        if os.name == 'nt':
            here = Path(__file__).resolve().parent
            helper = here / 'windows_job.py'
            if not helper.exists(): helper = here.parent / 'controller/windows_job.py'
            spec = importlib.util.spec_from_file_location('repair_owned_job', helper)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            job = module.Job(vm_limits=False)
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8', env=offline_environment(), **kwargs)
        if job: job.attach_and_resume(process)
        try:
            stdout, stderr = process.communicate(json.dumps(payload), timeout=timeout)
            return {'status': 'ok' if process.returncode == 0 else 'error',
                    'stdout': stdout, 'stderr': stderr, 'returncode': process.returncode,
                    'owned_pid': process.pid}
        except subprocess.TimeoutExpired:
            return {'status': 'timeout', 'stdout': '', 'stderr': '', 'returncode': None,
                    'owned_pid': process.pid}
    finally:
        if job: job.close()
        if process:
            if os.name != 'nt':
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
            if process.poll() is None: process.kill()
            process.communicate(timeout=10)


def grade(python, text, gold, *, timeout=10):
    if not isinstance(text, str) or not isinstance(gold, str) or len(text.encode()) > 4 * 2**20:
        raise ValueError('Invalid or excessive grader input; no truncation permitted')
    pred = extract_answer(text)
    if pred is None:
        return {'status': 'ok', 'correct': False, 'prediction': None, 'answer_omitted': True}
    result = owned_command([str(python), '-I', '-X', 'utf8', str(Path(__file__).resolve()), '--grade-worker'],
        {'prediction': pred, 'gold': gold}, timeout)
    if result['status'] != 'ok':
        return {'status': 'grader_' + result['status'], 'correct': None,
                'prediction': pred, 'detail': result['stderr'][-2000:]}
    try:
        value = json.loads(result['stdout'])
        if value.get('status') != 'ok' or type(value.get('correct')) is not bool:
            raise ValueError('Invalid worker receipt')
        return {**value, 'prediction': pred, 'answer_omitted': False}
    except (ValueError, AttributeError):
        return {'status': 'grader_error', 'correct': None, 'prediction': pred,
                'detail': 'Malformed grader worker response'}


def check_grader(python, versions):
    required = {'math-verify': '0.9.0', 'latex2sympy2_extended': '1.11.0', 'antlr4-python3-runtime': '4.13.2'}
    missing = {name: {'required': value, 'observed': versions.get(name)}
               for name, value in required.items() if versions.get(name) != value}
    if missing:
        return {'status': 'blocked_dependencies', 'passed': False, 'dependencies': missing,
                'cases_attempted': 0, 'cases_scheduled': len(GRADER_CASES), 'gpu_accessed': False}
    rows = []
    for case in GRADER_CASES:
        result = grade(python, case['text'], case['gold'])
        rows.append({'name': case['name'], 'expected': case['correct'], **result,
                     'passed': result['status'] == 'ok' and result['correct'] == case['correct']})
    return {'status': 'checked', 'passed': all(row['passed'] for row in rows), 'cases': rows,
            'cases_attempted': len(rows), 'cases_scheduled': len(rows), 'gpu_accessed': False}


def compare_logits(reference, candidate, *, atol=1e-5, rtol=1e-4):
    if (len(reference) != len(candidate) or not reference or not math.isfinite(atol)
            or not math.isfinite(rtol) or atol < 0 or rtol < 0
            or any(not math.isfinite(v) for v in [*reference, *candidate])):
        raise ValueError('Invalid numerical control')
    differences = [abs(a - b) for a, b in zip(reference, candidate, strict=True)]
    return {'passed': all(d <= atol + rtol * abs(a) for a, d in zip(reference, differences)),
        'max_abs': max(differences), 'atol': atol, 'rtol': rtol,
        'argmax_equal': max(range(len(reference)), key=reference.__getitem__) ==
                        max(range(len(candidate)), key=candidate.__getitem__)}


NUMERICAL_CONTROLS = ('incremental_cache', 'prompt_chunking', 'projection_last_position',
                      'attention_path', 'linear_attention_fallback', 'base_restore')


def numerical_controls(rows, *, synthetic=True):
    if set(rows) != set(NUMERICAL_CONTROLS): raise ValueError('Missing runtime numerical controls')
    results = {}
    for key, pair in rows.items():
        a, b = pair['reference'], pair['candidate']
        for field in ('input_ids_sha256', 'canonical_weights_sha256', 'dtype'):
            if a.get(field) != b.get(field) or not a.get(field): raise ValueError('Numerical control scope changed')
        if a['dtype'] != 'float32': raise ValueError('FP32 controls required')
        results[key] = compare_logits(a['logits'], b['logits'])
        if not results[key]['passed']: raise ValueError('Numerical deviation: ' + key)
    # Caller cannot qualify hardware by flipping a boolean on synthetic data.
    return {'controls': results, 'scope': 'synthetic' if synthetic else 'supplied_measurements',
            'hardware_qualified': False, 'live_supervisor_required': True}


def _grader_worker():
    from importlib.metadata import version
    if version('math-verify') != PROTOCOL['math_verify']:
        raise RuntimeError('math-verify version differs from pinned protocol')
    from math_verify import parse, verify
    value = json.load(sys.stdin)
    # No signal.alarm: the parent owns a Windows Job Object and wall watchdog.
    # Exceptions propagate as infrastructure errors instead of wrong answers.
    gold = parse(r'\boxed{' + value['gold'] + '}', parsing_timeout=None)
    pred = parse(r'\boxed{' + value['prediction'] + '}', parsing_timeout=None)
    if not gold: raise ValueError('Unparseable benchmark gold answer')
    correct = bool(pred) and bool(verify(gold, pred, timeout_seconds=None))
    print(json.dumps({'status': 'ok', 'correct': correct, 'math_verify': version('math-verify')}))


if __name__ == '__main__':
    if sys.argv[1:] != ['--grade-worker']: raise SystemExit('Internal CPU grader worker only')
    _grader_worker()
