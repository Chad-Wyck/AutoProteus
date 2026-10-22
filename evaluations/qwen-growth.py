"""Extend an independently checked candidate, then use both tools after restart.

This is trusted experiment orchestration. Candidate JSON is read as data and
all candidate execution, tests and invocations stay inside disposable VMs.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import threading
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from controller.config import DEFAULTS
from controller.evaluation import candidate_source, freeze_source, run_task, source_identity, growth_scores, tool_use
from controller.isolation import Artifacts, IsolatedAgent
from controller.providers import request_json
from controller.runtime import LocalRuntime
from controller.storage import Store, atomic_json, now

spec = importlib.util.spec_from_file_location('benchmark', ROOT / 'evaluations/local-model-benchmark.py')
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def data_path(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Experiment files must remain inside .data')
    return path


def main(args):
    directory = data_path(args.output)
    directory.mkdir(parents=True, exist_ok=False)
    source = json.loads(data_path(args.candidate).read_text(encoding='utf-8'))
    store = Store(directory / 'sessions')
    config = {**DEFAULTS, 'configured': True, 'base_url': 'http://127.0.0.1:11435',
              'model': 'hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q4_K_M',
              'context_tokens': args.context_tokens, 'response_tokens': args.response_tokens, 'temperature': args.temperature,
              'max_steps': 128, 'request_timeout': 300, 'terminal': True,
              'thinking': args.thinking == 'on', 'protocol': 'native'}
    settings = SimpleNamespace(values=config, key=lambda: '')
    engine, agent = LocalRuntime(ROOT, settings), None
    report = {'started': now(), 'status': 'running', 'source_sha256': source_identity(source),
              'method': config, 'handoff': args.handoff, 'candidate_promotion': False, 'operator_code_repair': False}
    trusted = [Path(__file__), ROOT / 'evaluations/local-model-benchmark.py',
               ROOT / 'evaluations/local-feature-probe.py', ROOT / 'evaluations/local-upgrade-tasks.json',
               ROOT / 'controller/isolation.py', ROOT / 'controller/evaluation.py',
               ROOT / 'controller/artifacts.py', ROOT / 'controller/transport.py',
               ROOT / 'controller/providers.py', ROOT / 'guest/worker.py', ROOT / 'tests/test_seed.py',
               ROOT / 'tests/test_text_helpers.py']
    report['trusted_runner_sha256'] = {}
    for path in trusted:
        name = path.relative_to(ROOT).as_posix()
        content = path.read_bytes()
        report['trusted_runner_sha256'][name] = hashlib.sha256(content).hexdigest()
        target = directory / 'trusted-runner' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    atomic_json(directory / 'starter-source.json', source)
    atomic_json(directory / 'report.json', report)
    sample = 'café\r\n猫 and dog\n'
    expected = {'path': 'inputs/sample.txt', 'bytes': len(sample.encode()), 'characters': len(sample),
                'lines': len(sample.splitlines()), 'words': len(sample.split())}
    extension = next(task['task'] for task in benchmark.TASKS if task['name'] == 'append_text')
    extension = extension.replace('Finish with a concise explanation of the change and checks.', '')
    extension = extension.replace('Finish as completed only once the feature is implemented and the entire candidate test suite passes.', '')
    if any(item['path'] == 'autoproteus/extensions.py' for item in source):
        extension = extension.replace('Register the tool in TOOL_SPECS so native and JSON descriptions share its definition.',
            'Prefer implementing and registering the tool in harness/autoproteus/extensions.py, following its TOOLS registry. Both native and JSON descriptions share its definition.')
        extension = extension.replace('Change runtime code only in harness/autoproteus/tools.py and harness/autoproteus/providers.py; keep the patch small.',
            'Change runtime code only in harness/autoproteus/extensions.py, harness/autoproteus/tools.py and harness/autoproteus/providers.py; keep the patch small.')
    task = {'name': 'cumulative-audit', 'checks': [],
            'fixtures': {'inputs/sample.txt': sample, 'audit.log': 'BEGIN\r\n'},
            'task': 'Complete this audit using your existing file_summary tool and a further seed improvement. There are two phases.\n'
                    'Use file_summary on inputs/sample.txt and save its complete returned object as audit.json.\n'
                    'The final audit.log must contain its existing bytes followed by exactly AUDIT COMPLETE\\n.\n'
                    'Use a new public append_text tool to add that line. It is currently missing; improve your harness to complete the task.\n'
                    + extension + '\n'
                    'Phase 1: implement append_text, add its new test file, and pass development checks on disposable files. '
                    'Keep audit.log unchanged during this phase. Only after doing that work, finish with status needs_input '
                    'and a concise explanation requesting checkpoint activation.\n'
                    'The controller will independently check and activate your edit. After that restart, use both file_summary and append_text '
                    'through public tool calls, finish audit.json and audit.log, verify their contents, and report completed. '
                    'Phase 2 starts when the controller tells you the edited seed is active. '
                    'Preserve the existing file_summary implementation and tests. Do not append the final line before activation.'}
    atomic_json(directory / 'task.json', task)
    try:
        settings.values['base_url'] = engine.ensure_service(allow_download=False)
        frozen = freeze_source(store, source, 'Previously accepted model-written summary seed')
        report['prior_feature'] = benchmark.verify_feature(store, frozen, 'file_summary')
        report['prior_public'] = benchmark.verify_public(store, frozen, 'file_summary')
        if not report['prior_feature']['passed'] or not report['prior_public']['passed']:
            raise ValueError('Starting candidate failed independent verification')
        report['next_feature_already_available'] = benchmark.verify_public(store, frozen, 'append_text')['passed']
        if report['next_feature_already_available']:
            raise ValueError('The next feature is already available; this would not demonstrate further growth')
        agent = IsolatedAgent(ROOT, store, settings, lambda config: benchmark.DiagnosticClient(
            config, directory / 'provider-errors', {'kind': 'cumulative-growth'}))
        print('GROWTH: model extends the accepted summary seed', flush=True)
        result = benchmark.enrich(store, run_task(agent, store, settings.values, task, frozen, args.timeout))
        trial = directory / 'extension'
        trial.mkdir()
        report['extension_run'] = result
        review = benchmark.assess(store, source, result, 'append_text', trial)
        report['extension_review'] = review
        # Waiting for activation is explicitly required, so completed is not a gate here.
        ready = (result['status'] in ('waiting', 'completed') and not result['timed_out'] and
                 review.get('runtime_changed') and review.get('new_test_files') and
                 review.get('protected_unchanged') and review.get('allowed_files_only') and
                 all(review.get(key, {}).get('passed') for key in ('regressions', 'feature', 'public')))
        session = store.get(result['session'])
        report['audit_log_before_activation'] = Artifacts(store, session).read('audit.log').decode('utf-8')
        ready = ready and report['audit_log_before_activation'] == 'BEGIN\r\n'
        edited = candidate_source(store, session)
        combined = freeze_source(store, edited, 'Cumulative model-written candidate')
        report['retained_feature'] = benchmark.verify_feature(store, combined, 'file_summary')
        report['retained_public'] = benchmark.verify_public(store, combined, 'file_summary')
        ready = bool(ready and report['retained_feature']['passed'] and report['retained_public']['passed'])
        report['ready_for_restart'] = ready
        atomic_json(directory / 'report.json', report)
        if ready:
            print('GROWTH: independent checks passed; activating the same checkpoint', flush=True)
            started = time.monotonic()
            before = session['steps']
            agent.restart_seed(session, handoff=args.handoff)
            worker = agent.workers[session['id']][1]
            while worker.is_alive():
                worker.join(timeout=.2)
                if time.monotonic() - started > 600:
                    agent.stop(session['id']); worker.join(timeout=10)
                    break
            files = Artifacts(store, session)
            try:
                report['audit_json'] = json.loads(files.read('audit.json'))
                report['audit_log'] = files.read('audit.log').decode('utf-8')
                report['input_preserved'] = files.read('inputs/sample.txt') == sample.encode()
            except (OSError, ValueError, KeyError) as error:
                report['artifact_error'] = str(error)
            events = [json.loads(line) for line in (store.directory(session['id']) / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
            boundary = max(index for index, event in enumerate(events) if event['type'] == 'run_started')
            used = [event['data']['action']['tool'] for event in events[boundary:]
                    if event['type'] == 'action_result' and event['data'].get('ok')]
            report['restart'] = {'status': session['status'], 'steps': session['steps'] - before,
                                 'tools_used': used, 'same_task': session['task'] == task['task'],
                                 'seconds': round(time.monotonic() - started, 2)}
            report['tool_usage'] = tool_use(events[boundary:])
            report['scores'] = growth_scores(True, True, session['status'] == 'completed',
                report.get('audit_json') == expected and report.get('audit_log') == 'BEGIN\r\nAUDIT COMPLETE\n' and
                report.get('input_preserved'), report['tool_usage'], ['file_summary', 'append_text'])
            report['passed'] = report['scores']['functional_growth']
        else:
            report['passed'] = False
        report.update(status='completed', finished=now())
        print('GROWTH RESULT', report['passed'], flush=True)
    except BaseException as error:
        report.update(status='interrupted', error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        if agent:
            agent.close()
        try:
            request_json(settings.values['base_url'] + '/api/generate', {'model': config['model'], 'keep_alive': 0}, timeout=30)
        except Exception:
            pass
        engine.close()
        atomic_json(directory / 'report.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidate', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--temperature', type=float, default=0.6)
    parser.add_argument('--thinking', choices=['on', 'off'], default='on')
    parser.add_argument('--context-tokens', type=int, default=32768)
    parser.add_argument('--response-tokens', type=int, default=8192)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--handoff', choices=['full', 'concise'], default='full')
    main(parser.parse_args())
