"""Prepare independent, opt-in Hermes-inspired comparisons. Never launches on prepare."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evaluations'))
from controller.evaluation import freeze_source, run_regressions, run_task, source_identity
from controller.isolation import IsolatedAgent, seed_files
from controller.storage import Store, atomic_json, now
from experience import ExperienceSuite, CONTRACTS, variant, reference, feature_check, public_check

spec = importlib.util.spec_from_file_location('navigation_research', ROOT / 'evaluations/navigation-study.py')
navigation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(navigation)
GROUPS = {'procedure': ('procedure', list(CONTRACTS)), 'history': ('retrieval', ['recover_receipt']),
          'context': ('usage', list(CONTRACTS)), 'programs': ('program', ['inspect_files'])}
EXTRA_TRUSTED = ('evaluations/experience-study.py', 'evaluations/experience.py', 'evaluations/experience_probe.py',
    'evaluations/experience_calibration.py', 'evaluations/journal_tools.py', 'evaluations/usage_budget.py',
    'evaluations/inspect_workspace.py', 'evaluations/invoke_tool.py', 'evaluations/upgrade-procedure.md')


class Suite(ExperienceSuite):
    def __init__(self):
        super().__init__(navigation)

    def calibrate(self, directory, plan, sources):
        store = Store(directory / 'calibration/sessions')
        record = {'started': now(), 'sources': plan['sources'], 'trusted_sha256': plan['trusted_sha256'], 'variants': {}}
        for name, source in sources.items():
            frozen = freeze_source(store, source, 'Frozen ' + name)
            result = run_regressions(ROOT, store, frozen)
            record['variants'][name] = result
            atomic_json(directory / 'calibration.json', record)
            if not result['passed']:
                raise RuntimeError('Protected regressions failed: ' + name)
        name = GROUPS[plan['experiment']][0]
        settings = SimpleNamespace(values={**plan['config'], 'provider': 'demo'}, key=lambda: '')
        if name in ('retrieval', 'usage'):
            agent = IsolatedAgent(ROOT, store, settings, lambda _: navigation.study.benchmark.ScriptedClient([
                {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 experience_calibration.py ' + name}}},
                {'status': 'completed'}]))
            try:
                result = run_task(agent, store, settings.values, {'name': name + '-fixture', 'task': 'Run the fixture.',
                    'fixtures': {'experience_calibration.py': (ROOT / 'evaluations/experience_calibration.py').read_text()},
                    'checks': [{'path': 'experience-calibration.json', 'contains': '"passed": true'}]},
                    freeze_source(store, sources[name], name), 120)
                record['helper'] = result
                if not result['passed']:
                    raise RuntimeError('Helper fixture failed: ' + name + ': ' + str(result))
            finally:
                agent.close()
        if plan['experiment'] in ('procedure', 'context'):
            original = freeze_source(store, sources['baseline'], 'Negative control')
            positive = freeze_source(store, reference(sources['baseline']), 'Human-written grader reference, never offered to model')
            faulty = freeze_source(store, reference(sources['baseline'], byte_limited=True), 'Faulty byte-limit control, never offered to model')
            record['grader_controls'] = {}
            for feature in CONTRACTS:
                negative = feature_check(navigation, store, original, feature)
                control = feature_check(navigation, store, positive, feature)
                public = public_check(navigation, store, positive, feature)
                record['grader_controls'][feature] = {'negative': negative, 'positive': control, 'public': public}
                atomic_json(directory / 'calibration.json', record)
                if negative['passed'] or not control['passed'] or not public['passed']:
                    raise RuntimeError('Independent grader calibration failed: ' + feature)
            faulty_result = feature_check(navigation, store, faulty, 'json_keys')
            record['byte_limited_json_negative'] = faulty_result
            boundary = next((item for item in faulty_result.get('probe', {}).get('checks', [])
                             if item['name'] == 'unicode-character-bound'), None)
            atomic_json(directory / 'calibration.json', record)
            if faulty_result['passed'] or not boundary or boundary['passed']:
                raise RuntimeError('The JSON grader did not reject the faulty byte-limited control at the Unicode boundary')
            escaping = freeze_source(store, reference(sources['baseline'], bypass_boundary=True), 'Faulty path-bypass control')
            boundary_result = feature_check(navigation, store, escaping, 'json_keys')
            record['path_bypass_json_negative'] = boundary_result
            path_checks = {item['name']: item['passed'] for item in boundary_result['probe']['checks']}
            atomic_json(directory / 'calibration.json', record)
            if boundary_result['passed'] or any(path_checks.get(key) is not False for key in ('../outside.txt', 'escaping-link')):
                raise RuntimeError('The JSON grader did not reject both path-bypass controls')
        elif plan['experiment'] == 'programs':
            cell = plan['schedule'][1]
            task = self.task(plan, cell)
            expected = task['checks'][0]['json']
            negative = [] == expected
            paths = ' '.join('inputs/item_' + str(index) + '.py' for index in range(6))
            agent = IsolatedAgent(ROOT, store, settings, lambda _: navigation.study.benchmark.ScriptedClient([
                {'action': {'tool': 'run_command', 'arguments': {'command': 'python3 experience/inspect_workspace.py ' + paths + ' > inspection.json'}}},
                {'status': 'completed'}]))
            try:
                task['fixtures']['experience/inspect_workspace.py'] = plan['program']
                result = run_task(agent, store, settings.values, task,
                                  freeze_source(store, sources['baseline'], 'Program calibration'), 120)
                record['program'] = result
                if negative or not result['passed']:
                    raise RuntimeError('Guest inspection program or artifact grader failed')
            finally:
                agent.close()
        else:
            # This checks actual omission + recovery across two VM launches.
            class RecoveryClient:
                calls = 0
                def complete(self, messages, cancel):
                    self.calls += 1
                    if self.calls == 1:
                        joined = '\n'.join(item['content'] for item in messages)
                        expected_receipt = hashlib.sha256(b'calibration-').hexdigest()[:24]
                        if expected_receipt in joined:
                            raise RuntimeError('Fixture did not omit the earlier receipt')
                        decision = {'action': {'tool': 'history_search', 'arguments': {'query': 'receipt.txt'}}}
                    else:
                        result = json.loads(next(item['content'].split('\n', 1)[1] for item in reversed(messages)
                                                 if item['content'].startswith('ACTION RESULT\n')))['result']
                        if self.calls == 2:
                            decision = {'action': {'tool': 'history_read', 'arguments': {'id': result['matches'][0]['id']}}}
                        elif self.calls == 3:
                            old = json.loads(json.loads(result['content'])['result']['content'])
                            decision = {'action': {'tool': 'write_file', 'arguments': {'path': 'recovery.json', 'content': json.dumps({
                                'receipt': old['receipt'], 'tested_seed_sha256': old['tested_seed_sha256'], 'verification': 'historical_only'})}}}
                        else:
                            decision = {'status': 'completed'}
                    return {'content': json.dumps(decision), 'usage': {}}
            recovery_settings = SimpleNamespace(values={**settings.values, 'provider': 'hosted', 'protocol': 'json'}, key=lambda: '')
            agent = IsolatedAgent(ROOT, store, recovery_settings, lambda _: RecoveryClient())
            try:
                cell = {'id': 'calibration-retrieval', 'variant': 'retrieval', 'task': 'recover_receipt'}
                result = self.run_case(agent, store, recovery_settings.values, plan, cell,
                    freeze_source(store, sources['retrieval'], 'Recovery calibration'))
                record['resumed_recovery'] = result
                if not result['passed']:
                    raise RuntimeError('Resumed recovery calibration failed: ' + str(result))
            finally:
                agent.close()
        record.update(passed=True, finished=now())
        atomic_json(directory / 'calibration.json', record)
        return record


def prepare(args):
    output = navigation.private_path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    # Rebuild the navigation plan because trusted host instrumentation evolved.
    # Its source packs, settings and 18 comparison cells retain the same design.
    navigation.prepare(SimpleNamespace(output=str(output / 'navigation'), repeats=args.repeats, timeout=args.timeout,
        output_token_budget=getattr(args, 'output_token_budget', navigation.DEFAULT_OUTPUT_TOKENS)))
    template = json.loads((output / 'navigation/plan.json').read_text())
    baseline = seed_files(ROOT)
    for group, (name, tasks) in GROUPS.items():
        directory = output / group
        directory.mkdir()
        sources = {'baseline': baseline, name: variant(baseline, name)}
        plan = {**template, 'experiment': group, 'created': now(), 'contracts': CONTRACTS,
            'procedure': (ROOT / 'evaluations/upgrade-procedure.md').read_text(),
            'invoke_tool': (ROOT / 'evaluations/invoke_tool.py').read_text(),
            'program': (ROOT / 'evaluations/inspect_workspace.py').read_text(),
            'sources': {key: source_identity(value) for key, value in sources.items()}, 'schedule': [],
            'trusted_sha256': dict(template['trusted_sha256']),
            'primary': 'Accepted seed upgrades' if group in ('procedure', 'context') else 'Independently correct completed artifacts',
            'scope': 'Separate opt-in comparison; no combined treatment, no automatic promotion or online training.'}
        for repeat in range(1, args.repeats + 1):
            for index, task in enumerate(tasks):
                order = ('baseline', name) if (repeat + index) % 2 else (name, 'baseline')
                for treatment in order:
                    plan['schedule'].append({'id': f'{repeat}-{task}-{treatment}', 'repeat': repeat, 'task': task, 'variant': treatment})
        for key, source in sources.items():
            atomic_json(directory / (key + '-source.json'), source)
        for filename in EXTRA_TRUSTED:
            raw = (ROOT / filename).read_bytes()
            destination = directory / 'trusted-runner' / filename
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
            plan['trusted_sha256'][filename] = hashlib.sha256(raw).hexdigest()
        navigation.save_plan(directory, plan)
    (output / 'Start tests.cmd').write_text(
        f'@echo off\nsetlocal\ncd /d "{ROOT}"\n"{ROOT / ".runtime/python/python.exe"}" -X utf8 '
        f'"{ROOT / "evaluations/experience-study.py"}" menu --input "{output}"\npause\n', encoding='utf-8')
    (output / 'READY.md').write_text('Prepared opt-in comparisons. No live trials have started.\n\n'
        'Open Start tests.cmd, then select one study. All use cached Qwen3.5 9B and isolated VMs.\n'
        'Navigation 18, procedure 18, history 6, context 18 and programs 6 attempts at three repeats.\n'
        f'Navigation alone: 18 attempts at three repeats; {args.timeout}-second and {template["output_token_budget"]}-generated-token ceilings per attempt.\n'
        'Other studies are separate opt-in runs. Full costs, failures and interrupted attempts remain recorded.\n'
        'Saved app preferences and normal seed are unchanged. Run check-only before model trials.\n', encoding='utf-8')
    print('Prepared experiment menu; no model inference started:', output)


def run_group(directory, group, check_only=False):
    if group == 'navigation':
        navigation.run(SimpleNamespace(input=str(directory / group), check_only=check_only))
    else:
        navigation.run(SimpleNamespace(input=str(directory / group), check_only=check_only), Suite())


def menu(args):
    directory = navigation.private_path(args.input)
    options = ['navigation', 'procedure', 'history', 'context', 'programs']
    print('\nQwen3.5 9B experiments. Ordinary app settings are unchanged.\n')
    labels = ['Find relevant source', 'Reuse an upgrade procedure', 'Recover earlier task records',
              'Budget context using reported usage', 'Inspect files with a guest program']
    for index, name in enumerate(options, 1):
        plan = json.loads((directory / name / 'plan.json').read_text())
        hours = len(plan['schedule']) * plan['timeout'] / 3600
        recommendation = ' - recommended for tonight' if name == 'navigation' else ''
        print(f'{index}. {labels[index - 1]} ({len(plan["schedule"])} attempts; up to {hours:g} task hours + checks){recommendation}')
    print('6. Validate all with scripted VMs (no model)\n0. Exit\n')
    answer = input('Choose a study: ').strip()
    if answer == '0':
        return
    if answer == '6':
        for name in options:
            run_group(directory, name, True)
    elif answer in {'1', '2', '3', '4', '5'}:
        run_group(directory, options[int(answer) - 1])
    else:
        print('No study started. Choose a listed number next time.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('--output', required=True)
    p.add_argument('--repeats', type=int, choices=range(1, 6), default=3)
    p.add_argument('--timeout', type=int, default=navigation.DEFAULT_TASK_SECONDS)
    p.add_argument('--output-token-budget', type=int, default=navigation.DEFAULT_OUTPUT_TOKENS)
    for command in ('run', 'menu'):
        p = commands.add_parser(command)
        p.add_argument('--input', required=True)
        if command == 'run':
            p.add_argument('--group', choices=['navigation', *GROUPS], required=True)
            p.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(args)
    elif args.command == 'menu':
        menu(args)
    else:
        run_group(navigation.private_path(args.input), args.group, args.check_only)
