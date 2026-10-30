"""Disposable-VM calibration and scripted runner controls. Never contacts inference."""
import argparse
import base64
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evaluations'))

from controller.config import DEFAULTS
from controller.evaluation import candidate_source, freeze_source, run_regressions, source_identity
from controller.isolation import Artifacts, seed_files
from controller.storage import Store, atomic_json, now
from novel_features import FEATURES, contract, expected, growth_task, items, reference, saved_outputs
import generalization as study


def scripted_chain(folder, source, parent):
    """Exercise real development, protected grading, activation and cumulative reuse."""
    import activation_use
    import model_study
    from model_plan import environment, trusted_files
    from run_budget import BudgetModelClient
    from controller.providers import model_response
    config = {**DEFAULTS, 'configured': True, 'provider': 'hosted', 'model': 'scripted VM calibration',
        'base_url': 'http://127.0.0.1:1/v1', 'protocol': 'native', 'terminal': True, 'internet': False,
        'context_tokens': 131072, 'response_tokens': 4096, 'max_steps': 32, 'action_limit': True}
    from novel_features import CONTRACTS, strict_contract
    plan = {'deadline': 300, 'generated_tokens': 8192, 'activation_reminder': True, 'extension_pack': 'pilot-6k',
        'trusted_sha256': trusted_files(), 'environment': environment(), 'recipe': study.RECIPE,
        'contracts': {**study.CONTRACTS, **CONTRACTS}}

    def run_stage(name, original, feature, task, earlier=None):
        stage = folder / name
        stage.mkdir(parents=True)
        candidate = reference(original, features=(feature,))
        actions = []
        for item in candidate:
            if item['path'] in ('autoproteus/tools.py', 'autoproteus/providers.py'):
                actions.append({'tool': 'write_file', 'arguments': {'path': 'harness/' + item['path'],
                    'content': base64.b64decode(item['data']).decode('utf-8')}})
        # A focused candidate test is part of the package, rather than a fake host verdict.
        raw = (b'[OK]\nx=1\n' if feature == 'ini_sections' else b'{"a":1}' if feature == 'format_json' else b'a\r\n')
        test = ('import unittest\nfrom autoproteus.tools import Workspace\nfrom pathlib import Path\n'
                'from tempfile import TemporaryDirectory\nclass AddedCapability(unittest.TestCase):\n'
                ' def test_added(self):\n  with TemporaryDirectory() as directory:\n'
                "   root=Path(directory); (root/'sample').write_bytes(" + repr(raw) + ')\n'
                "   result=Workspace(root).execute(" + repr(feature) + ", {'path':'sample'})\n"
                "   self.assertEqual(result['path'],'sample')\n")
        actions.append({'tool': 'write_file', 'arguments': {'path': 'harness/tests/test_added_' + feature + '.py', 'content': test}})
        actions.append({'tool': 'run_command', 'arguments': {'command': 'python3 harness/seed.py check'}})
        actions.append({'tool': 'finish', 'arguments': {'status': 'needs_input', 'reason': 'activation', 'message': 'Please activate the checked extension.'}})
        sequences = [actions, []]
        for spec in items(task['first_use']):
            _, receipt = expected(spec)
            sequences[1] += [
                {'tool': spec['feature'], 'arguments': {'path': spec['input']}},
                {'tool': 'write_file', 'arguments': {'path': spec['output'], 'content': json.dumps(receipt, ensure_ascii=False)}},
                {'tool': 'read_file', 'arguments': {'path': spec['output']}}]
        sequences[1].append({'tool': 'finish', 'arguments': {'status': 'completed', 'message': 'Saved and checked the actual task results.'}})
        constructed = []
        class Scripted(BudgetModelClient):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                if len(constructed) >= len(sequences): raise AssertionError('Unexpected extra scripted connection')
                self.actions = iter(sequences[len(constructed)])
                constructed.append(self)
            def _complete(self, messages, cancel, progress, tools=None, observe=None):
                # Exercise production message preparation and native normalization, with no HTTP transport.
                wire, adjustment = self.prepare_messages(messages, tools, observe)
                action = next(self.actions)
                if observe: observe('provider_request', {'payload': {'messages': wire, 'tools': tools}, 'scripted': True})
                calls = [{'id': 'scripted', 'type': 'function', 'function': {'name': action['tool'],
                    'arguments': json.dumps(action['arguments'], ensure_ascii=False)}}]
                return model_response('', calls, True, usage={'prompt_tokens': 1, 'completion_tokens': 1})
        # Any accidental HTTP fallback is an immediate hard failure.
        with patch.object(model_study, 'budget_client', Scripted), patch('controller.providers.request_json', side_effect=AssertionError('No inference allowed')):
            row = model_study.trial(stage, task, original, config, plan, feature, earlier)
        if not row.get('first_package_accepted') or not row.get('first_use', {}).get('passed'):
            raise AssertionError('Scripted package/activation did not qualify: ' + str(stage / 'result.json'))
        store = Store(stage / 'sessions')
        session = store.get(row['run']['session'])
        frozen = json.loads((stage / 'review/candidate-source.json').read_text(encoding='utf-8'))
        return row, store, session, frozen

    from activation_use import contract as use_contract
    spec = strict_contract(use_contract(parent, 'calibration-' + parent))
    first_task = {'name': parent, 'checks': [], 'first_use': spec,
        'task': 'Implement the requested capability, verify it, then request activation. ' + spec['instruction']}
    first, store, session, frozen = run_stage('first', source, parent, first_task)
    preserved = saved_outputs(Artifacts(store, session), spec)
    added, second_task = growth_task(parent, plan, spec, preserved)
    second, _, _, _ = run_stage('second', frozen, added, second_task, parent)
    chain = activation_use.chain_result(first, second, activation_use.PROTOCOL)
    if not chain['complete_chain_passed']: raise AssertionError('Scripted cumulative growth did not qualify')
    return {'passed': True, 'chain': chain, 'first': str(folder / 'first/result.json'),
        'second': str(folder / 'second/result.json'), 'scope': 'Scripted plumbing control, not model capability evidence.'}


def calibrate(output, source, *, integration=True):
    from model_plan import environment, trusted_files
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    store = Store(output / 'sessions')
    report = {'started': now(), 'source_sha256': source_identity(source), 'passed': False,
        'scope': 'VM-only candidate execution, scripted actions; no live models or training.',
        'controls': {}, 'integration': {}, 'trusted_sha256': trusted_files(), 'environment': environment()}
    start = time.monotonic()
    def save(): atomic_json(output / 'calibration.json', report)
    save()
    try:
        baseline = freeze_source(store, source, 'Absent novel tools')
        positive_source = reference(source)
        positive = freeze_source(store, positive_source, 'Independent reference; never a model target')
        regression = run_regressions(ROOT, store, positive)
        report['reference_regressions'] = regression
        if not regression['passed']: raise AssertionError('Reference fails the protected suite')
        for feature in FEATURES:
            absent = study.verify_feature(store, baseline, feature)
            correct = study.verify_feature(store, positive, feature)
            public = study.verify_public(store, positive, feature)
            report['controls'][feature] = {'absent': absent, 'reference': correct, 'public': public}
            save()
            if (absent['passed'] or absent.get('probe', {}).get('checks', {}).get('registered') is not False
                    or not correct['passed'] or not public['passed']):
                raise AssertionError('Reference/absence calibration failed: ' + feature)
        matrix = [('byte-limit', feature, ['exact']) for feature in FEATURES]
        matrix += [('path-bypass', feature, ['traversal-valid-input', 'escaping-symlink-valid-input']) for feature in FEATURES]
        matrix += [('sorted-sections', 'ini_sections', ['order']),
                   ('missing-write', 'normalize_newlines', ['default', 'crlf']),
                   ('wrong-default', 'normalize_newlines', ['default']),
                   ('false-changed', 'normalize_newlines', ['default']),
                   ('late-validation', 'normalize_newlines', ['overflow'])]
        for fault, feature, failed in matrix:
            frozen = freeze_source(store, reference(source, fault), fault + ' ' + feature)
            regressions = run_regressions(ROOT, store, frozen)
            negative = study.verify_feature(store, frozen, feature)
            checks = negative.get('probe', {}).get('checks', {})
            healthy = checks.get('registered') is True and checks.get('schema') is True and regressions['passed']
            detected = not negative['passed'] and all(checks.get(name) is False for name in failed)
            key = feature + ':' + fault
            report['controls'][key] = {'passed': bool(healthy and detected), 'expected_failures': failed,
                'regressions': regressions, 'feature': negative}
            save()
            if not healthy or not detected: raise AssertionError('Fault not detected cleanly: ' + key)
        if integration:
            for parent in (*FEATURES, 'csv_preview'):
                report['integration'][parent] = scripted_chain(output / ('chain-' + parent), source, parent)
                save()
        if trusted_files() != report['trusted_sha256'] or environment() != report['environment']:
            raise ValueError('Trusted runner/environment changed during calibration; prepare a new calibration')
        report.update(passed=True, finished=now(), seconds=round(time.monotonic() - start, 3), integration_run=integration)
        save()
        return report
    except Exception as error:
        report.update(error=type(error).__name__ + ': ' + str(error), finished=now(), seconds=round(time.monotonic() - start, 3))
        save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source-pack', help='Inert complete starter-source.json; candidate imports stay in VMs')
    args = parser.parse_args()
    from model_plan import private
    source = json.loads(Path(args.source_pack).read_text(encoding='utf-8')) if args.source_pack else seed_files(ROOT)
    result = calibrate(private(args.output), source)
    print(json.dumps({'passed': result['passed'], 'seconds': result['seconds'], 'report': str(private(args.output) / 'calibration.json')}))
