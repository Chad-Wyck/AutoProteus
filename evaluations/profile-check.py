"""Validate an experimental local profile using the normal managed app connection."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'evaluations')]
from controller.config import DEFAULTS
from controller.compatibility import model_identity, qualify_profile
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
    if args.defaults and args.gguf: raise ValueError('Importing an experimental GGUF is not a fresh-default check')
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Keep evidence under .data')
    output.mkdir(parents=True, exist_ok=False)
    config = {**DEFAULTS, 'action_limit':True, 'configured': True, 'base_url': 'http://127.0.0.1:11435'}
    if not args.defaults:
        config.update(model=args.model, context_tokens=131072, response_tokens=4096, temperature=0.6,
                      thinking=False, terminal=True, protocol='native', max_steps=128)
    settings = SimpleNamespace(values=config, key=lambda: '')
    engine = LocalRuntime(ROOT, settings)
    source = seed_files(ROOT)
    report = {'started': now(), 'config': config, 'source_sha256': source_identity(source), 'trials': [],
        'trusted_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
            'controller/providers.py', 'controller/evaluation.py', 'controller/isolation.py',
            'controller/artifacts.py', 'controller/transport.py', 'evaluations/run_budget.py',
            'evaluations/generalization.py', 'evaluations/generalization-probe.py', 'evaluations/local-model-benchmark.py')},
        'connection': 'Production ModelClient through managed Ollama; no custom wire adapter or call-ID rewrite.',
        'qualification': 'Source-bound observations; transport, ordinary tasks and extensions are distinct. No automatic default promotion.',
        'profile_kind': 'fresh_install_defaults' if args.defaults else 'experimental_upgrade_profile',
        'requested_repeats': args.repeats, 'seed_extension_qualified': False}
    atomic_json(output / 'results.json', report)
    try:
        base = engine.ensure_service(allow_download=args.allow_download)
        settings.values['base_url'] = base
        if args.allow_download:
            report['model_download'] = request_json(base + '/api/pull', {'model': config['model'], 'stream': False}, timeout=1800)
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
        report['model_properties'] = request_json(base + '/api/show', {'model': config['model']})
        report['transport_qualification'] = qualify_profile(settings.values)
        atomic_json(output / 'results.json', report)
        if args.defaults:
            report['ordinary'] = []
            for task in json.loads((ROOT / 'evaluations/tasks.json').read_text(encoding='utf-8'))[:3]:
                folder = output / ('ordinary-' + task['name'])
                store = Store(folder / 'sessions')
                recorder = CallRecorder(folder / 'provider-calls.jsonl')
                budget = GeneratedTokenBudget(args.output_token_budget)
                agent = IsolatedAgent(ROOT, store, settings, lambda values: BudgetModelClient(values, observer=recorder, token_budget=budget))
                try:
                    row = run_task(agent, store, settings.values, task, freeze_source(store, source, 'Default starter'), args.timeout)
                    report['ordinary'].append({'run': row, 'calls': call_metrics(read_events(recorder.path)), 'budget': budget.summary()})
                    atomic_json(output / 'results.json', report)
                finally: agent.close()
            report['extension_status'] = 'not_run: fresh defaults do not grant terminal access for development checks'
            return
        for repeat in range(1, args.repeats + 1):
          for name in ('sha256_file', 'format_json'):
            folder = output / ('repeat-%02d-' % repeat + name)
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
                    'checks': []}, freeze_source(store, source, 'Frozen starter'), args.timeout,
                    deadline=(deadline := time.monotonic() + args.timeout))}
                row['repeat'] = repeat
                row['review'] = study.benchmark.assess(store, source, row['run'], name, folder / 'review',
                    lambda store, source, name: study.verify_feature(store, source, name, deadline=deadline),
                    lambda store, source, name: study.verify_public(store, source, name, deadline=deadline),
                    lambda root, store, source: study.run_regressions(root, store, source, deadline=deadline))
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
    p.add_argument('--defaults', action='store_true', help='Check actual fresh-install defaults on ordinary tasks; never silently enable terminal access')
    p.add_argument('--repeats', type=int, choices=range(1, 6), default=1)
    p.add_argument('--allow-download', action='store_true', help='Explicitly allow managed engine/model downloads for a fresh setup check')
    p.add_argument('--timeout', type=int, default=DEFAULT_TASK_SECONDS)
    p.add_argument('--output-token-budget', type=int, default=DEFAULT_OUTPUT_TOKENS)
    main(p.parse_args())
