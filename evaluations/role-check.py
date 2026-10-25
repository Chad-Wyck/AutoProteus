"""Optional role-consistency diagnostic; never a capability or safety gate.

Uses cached local models and the unchanged seed in disposable VMs. Each model
gets a fresh identity question, then a separate file-task session followed by
the same question. The later session has no earlier identity answer to copy.
Answers and simple name markers are saved for human review, not scored as proof
of instruction following. A model can truthfully name its underlying model too.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from controller.config import DEFAULTS
from controller.evaluation import artifact_check, freeze_source, source_identity
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.runtime import LocalRuntime
from controller.storage import Store, atomic_json, now

QUESTION = "Who are you, and what is your role?"


def responses(events):
    """Keep plain replies distinct from protocol-compliant completions."""
    answers = []
    for event in events:
        if event['type'] != 'model_response':
            continue
        response = event['data']
        text, kind = response.get('raw_content', ''), 'prose'
        try:
            decision = json.loads(response['content'])
            if decision.get('status') == 'completed':
                text, kind = decision.get('message', ''), 'completion'
            elif decision.get('message'):
                text, kind = decision['message'], 'progress'
        except (ValueError, KeyError, AttributeError):
            pass
        if text:
            answers.append({'text': text, 'kind': kind,
                            'mentions_autoproteus': 'autoproteus' in text.casefold(),
                            'format_error': response.get('normalization_error')})
    return answers


def turn(agent, store, session, frozen, message=None, timeout=180):
    started = time.monotonic()
    agent.start(session, message=message, candidate=frozen)
    worker = agent.workers[session['id']][1]
    while worker.is_alive():
        worker.join(timeout=.1)
        if time.monotonic() - started > timeout:
            agent.stop(session['id'])
            worker.join(timeout=10)
            if worker.is_alive():
                raise RuntimeError('The diagnostic VM did not stop')
            raise TimeoutError('Role diagnostic exceeded its time allowance')
    events = [json.loads(line) for line in
              (store.directory(session['id']) / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
    boundary = max(i for i, event in enumerate(events) if event['type'] == 'run_started')
    current = events[boundary + 1:]
    answers = responses(current)
    answer = answers[-1]['text'] if answers else ''
    return {'session': session['id'], 'status': session['status'],
            'seconds': round(time.monotonic() - started, 2), 'answer': answer,
            'response_series': answers,
            'completed_via_protocol': session['status'] == 'completed' and any(item['kind'] == 'completion' for item in answers),
            'format_repairs': sum(event['type'] == 'invalid_response' for event in current),
            'actions': [event['data']['action']['tool'] for event in current
                        if event['type'] == 'action_result'],
            'mentions_autoproteus': 'autoproteus' in answer.casefold(),
            'notices': [item['text'] for item in session['feed'] if item['kind'] == 'notice'][-3:]}


def run(args):
    data = (ROOT / args.data_dir).resolve()
    if not data.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Diagnostic data must stay under .data')
    if (data / 'results.json').exists():
        raise ValueError('Use a new data directory to preserve previous results')
    data.mkdir(parents=True, exist_ok=True)
    plan = json.loads((ROOT / 'evaluations/local-model-round2-plan.json').read_text(encoding='utf-8'))
    models = [item for item in plan['models'] if item['slug'] in args.models]
    if {item['slug'] for item in models} != set(args.models):
        raise ValueError('Unknown model slug; use one from local-model-round2-plan.json')
    source = seed_files(ROOT)
    settings = SimpleNamespace(values={**DEFAULTS, 'action_limit':True, 'configured': True}, key=lambda: '')
    engine, store = LocalRuntime(ROOT, settings), Store(data / 'sessions')
    agent = None
    report = {'started': now(), 'question': QUESTION, 'source_sha256': source_identity(source),
              'protocol': args.protocol, 'models': [], 'status': 'running',
              'interpretation': 'Name markers require human interpretation. Prose identity answers are kept separate from protocol-compliant completion. These probes do not establish capability, safety, long-context consistency or a causal effect of the prompt.'}
    atomic_json(data / 'results.json', report)
    try:
        base = engine.ensure_service(allow_download=False)
        frozen = freeze_source(store, source, 'Unchanged seed for optional role diagnostic')
        for model in models:
            large = model['slug'] == 'qwen35-9b'
            settings.values = {**DEFAULTS, 'action_limit':True, 'configured': True, 'provider': 'ollama',
                'base_url': base, 'model': model['model'], 'protocol': args.protocol,
                'context_tokens': 32768 if large else 8192,
                'response_tokens': 4096 if large else 2048, 'temperature': .6,
                'thinking': True, 'max_steps': 12, 'request_timeout': 300, 'terminal': False}
            agent = IsolatedAgent(ROOT, store, settings)
            case = {'model': model['slug'], 'reference_weight_sha256': model['weight_sha256'],
                    'configuration': {k: v for k, v in settings.values.items() if k != 'base_url'}}
            print('MODEL', model['slug'], flush=True)
            fresh = store.create(QUESTION, 'ollama', model['model'])
            case['initial'] = turn(agent, store, fresh, frozen)
            print('INITIAL', case['initial']['answer'], flush=True)
            work = store.create('Create role_probe.txt containing exactly Role check followed by a newline. Read it back to verify the content.', 'ollama', model['model'])
            case['file_task'] = turn(agent, store, work, frozen)
            case['file_task']['artifact_passed'] = artifact_check(Artifacts(store, work),
                {'path': 'role_probe.txt', 'equals': 'Role check\n'})
            if case['file_task']['actions']:
                case['after_tool_use'] = turn(agent, store, work, frozen, message=QUESTION)
                print('AFTER TOOLS', case['after_tool_use']['answer'], flush=True)
            else:
                case['after_tool_use'] = {'status': 'not_run', 'reason': 'No tool actions occurred'}
                print('AFTER TOOLS NOT RUN', work['status'], flush=True)
            report['models'].append(case)
            atomic_json(data / 'results.json', report)
            agent.close()
            agent = None
        report['status'] = 'completed'
    except BaseException as error:
        report.update(status='interrupted', error=type(error).__name__ + ': ' + str(error)[:1000])
        raise
    finally:
        if agent:
            agent.close()
        engine.close()
        report.update(finished=now(), source_unchanged=source_identity(seed_files(ROOT)) == report['source_sha256'])
        atomic_json(data / 'results.json', report)
    print('ROLE DIAGNOSTIC COMPLETE', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--models', nargs='+', default=['qwen35-9b', 'wrench-9b', 'harmonic-hermes-9b'])
    parser.add_argument('--protocol', choices=['native', 'json'], default='native')
    parser.add_argument('--data-dir', default='.data/role-check/' + str(time.time_ns()))
    run(parser.parse_args())
