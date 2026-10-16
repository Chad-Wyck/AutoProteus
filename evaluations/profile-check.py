"""Validate an experimental local profile using the normal managed app connection."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'evaluations')]
from controller.config import DEFAULTS
from controller.compatibility import model_identity
from controller.evaluation import freeze_source, run_task, source_identity
from controller.isolation import IsolatedAgent, seed_files
from controller.providers import request_json
from controller.runtime import LocalRuntime
from controller.storage import Store, atomic_json, now
from observations import CallRecorder, call_metrics, read_events
from run_budget import BudgetModelClient, GeneratedTokenBudget, DEFAULT_OUTPUT_TOKENS, DEFAULT_TASK_SECONDS
import generalization as study


def main(args):
    GeneratedTokenBudget(args.output_token_budget)
    if args.timeout < 1: raise ValueError('Positive deadline required')
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Keep evidence under .data')
    output.mkdir(parents=True, exist_ok=False)
    config = {**DEFAULTS, 'configured': True, 'provider': 'ollama', 'base_url': 'http://127.0.0.1:11435',
        'model': args.model, 'context_tokens': 131072, 'response_tokens': 4096, 'temperature': 0.6,
        'thinking': False, 'terminal': True, 'protocol': 'native', 'max_steps': 128}
    settings = SimpleNamespace(values=config, key=lambda: '')
    engine = LocalRuntime(ROOT, settings)
    source = seed_files(ROOT)
    report = {'started': now(), 'config': config, 'source_sha256': source_identity(source), 'trials': [],
        'trusted_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'controller/providers.py', 'controller/evaluation.py', 'controller/isolation.py', 'evaluations/run_budget.py',
            'evaluations/generalization.py', 'evaluations/generalization-probe.py', 'evaluations/local-model-benchmark.py')},
        'connection': 'Production ModelClient through managed Ollama; no custom wire adapter or call-ID rewrite.',
        'qualification': 'Bounded transfer check; not a repeatability or default-profile qualification.'}
    atomic_json(output / 'results.json', report)
    try:
        base = engine.ensure_service(allow_download=False)
        settings.values['base_url'] = base
        if args.gguf:
            path = Path(args.gguf).resolve()
            receipt = json.loads(Path(str(path) + '.receipt.json').read_text())
            digest = hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()
            if digest != receipt['sha256']: raise ValueError('GGUF checksum mismatch')
            report['weights'] = receipt
            modelfile = output / 'Modelfile'
            modelfile.write_text('FROM "' + path.as_posix() + '"\n' +
                '\n'.join('PARAMETER ' + key + ' ' + str(value) for key, value in {
                    'num_ctx': 131072, 'temperature': 0.6, 'top_p': 0.8, 'top_k': 20,
                    'min_p': 0, 'repeat_penalty': 1, 'presence_penalty': 0}.items()) + '\n')
            import os
            binary = ROOT / ('.runtime/ollama/ollama.exe' if sys.platform == 'win32' else '.runtime/ollama-linux/bin/ollama')
            with (output / 'import.log').open('wb') as log:
                subprocess.run([str(binary), 'create', args.model, '-f', str(modelfile)], check=True,
                    env={**os.environ, 'OLLAMA_HOST': base}, stdout=log, stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0, timeout=600)
        report['model_identity'] = model_identity(settings.values)
        report['model_properties'] = request_json(base + '/api/show', {'model': args.model})
        atomic_json(output / 'results.json', report)
        for name in ('sha256_file', 'format_json'):
            folder = output / name
            store = Store(folder / 'sessions')
            recorder = CallRecorder(folder / 'provider-calls.jsonl')
            budget = GeneratedTokenBudget(args.output_token_budget)
            clients = []
            def factory(values):
                client = BudgetModelClient(values, observer=recorder, token_budget=budget)
                clients.append(client); return client
            agent = IsolatedAgent(ROOT, store, settings, factory)
            try:
                if agent.execution.mode != 'vm': raise ValueError('VM protection required')
                print('STANDARD APP TASK', name, flush=True)
                row = {'task': name, 'run': run_task(agent, store, settings.values, {
                    'name': name, 'task': 'Add exactly one new public tool. ' + study.CONTRACTS[name] + study.RECIPE,
                    'checks': []}, freeze_source(store, source, 'Frozen starter'), args.timeout)}
                row['review'] = study.assess(store, source, row['run'], name, folder / 'review')
                row['token_budget'] = budget.summary()
                row['calls'] = call_metrics(read_events(recorder.path))
                row['capture'] = {**recorder.summary(), 'observer_failed': any(c.observation_failed for c in clients)}
                report['trials'].append(row)
                atomic_json(output / 'results.json', report)
                print('STANDARD APP RESULT', name, row['review']['accepted'], flush=True)
            finally:
                agent.close()
    except BaseException as error:
        report['failure'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        try: request_json(settings.values['base_url'] + '/api/generate', {'model': args.model, 'keep_alive': 0}, timeout=30)
        except Exception: pass
        engine.close()
        report.update(finished=now(), source_unchanged=source_identity(seed_files(ROOT)) == report['source_sha256'])
        atomic_json(output / 'results.json', report)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--model', default='autoproteus-qwen35-4b-q4km:experimental')
    p.add_argument('--gguf', help='Import already downloaded, receipt-verified weights without changing app preferences')
    p.add_argument('--timeout', type=int, default=DEFAULT_TASK_SECONDS)
    p.add_argument('--output-token-budget', type=int, default=DEFAULT_OUTPUT_TOKENS)
    main(p.parse_args())
