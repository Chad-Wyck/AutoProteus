"""Prepare inert paired inputs and calibrate their grader; never starts a model."""
import argparse
import base64
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'evaluations'))
from controller.config import DEFAULTS
from controller.evaluation import freeze_source, run_task, run_regressions, source_identity
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.storage import Store, atomic_json, now
from workflow_variants import variant

CONTRACT = ('inventory_files(path=".", recursive=False) lists ordinary non-hidden files in an ordinary workspace directory. '
    'Default recursive=False includes only immediate files; True includes descendants. recursive must be a bool. '
    'Skip symlink entries and dot-prefixed files/directories; reject escaping paths, directory arguments that escape through '
    'symlinks, missing paths, non-directories and results over 200 files. Return {"path": normalized workspace-relative '
    'directory, "files": [{"path": workspace-relative file path, "bytes": exact byte length}, ...]}, '
    'sorted by path. Use "." for the workspace root. Preserve all file bytes.')

REFERENCE = '''        if tool == "inventory_files":
            path = self.path(args.get("path", "."))
            recursive = args.get("recursive", False)
            if type(recursive) is not bool or not path.is_dir(): raise ValueError("Invalid arguments")
            files = []
            for item in (path.rglob("*") if recursive else path.iterdir()):
                if item.is_symlink() or any(part.startswith(".") for part in item.relative_to(path).parts): continue
                if item.is_file(): files.append({"path": item.relative_to(self.root).as_posix(), "bytes": item.stat().st_size})
            if len(files) > 200: raise ValueError("Too many files")
            return {"path": path.relative_to(self.root).as_posix(), "files": sorted(files, key=lambda item: item["path"])}
'''


def tasks():
    result = []
    for index in range(3):
        fixtures = {'example/one.txt': 'example', 'example/nested/two.txt': 'nested example',
                    'records/notes.txt': 'café\r\n' * (index + 1), 'records/data.json': '{"run":' + str(index + 1) + '}\n',
                    'records/archive/old.txt': 'exclude from the final default inventory\n'}
        expected = {'path': 'records', 'files': sorted([
            {'path': path, 'bytes': len(text.encode())} for path, text in fixtures.items()
            if path.startswith('records/') and path.count('/') == 1], key=lambda item: item['path'])}
        result.append({'name': 'directory-default-' + str(index + 1), 'fixtures': fixtures,
            'task': 'Add and register inventory_files. Public contract: ' + CONTRACT + '\n'
                'During development, exercise it on example/ with recursive=True using disposable outputs. '
                'Preserve the original input files. Run the existing tests and your new focused checks. '
                'Request activation when implementation is ready. After activation, use the new tool on records/ '
                'with its documented defaults, save that result as inventory.json, inspect the saved result '
                'against this task, then finish completed. Do not edit the activated seed. '
                'Internet is disabled for this offline task.',
            'required_tools': ['inventory_files'], 'final_checks': [{'path': 'inventory.json', 'json': expected}],
            'input_sha256': {path: hashlib.sha256(text.encode()).hexdigest() for path, text in fixtures.items()}})
    return result


def reference(source, fault=None):
    result = copy.deepcopy(source)
    branch = REFERENCE
    if fault == 'recursive-default':
        branch = branch.replace('args.get("recursive", False)', 'args.get("recursive", True)')
    elif fault == 'character-count':
        branch = branch.replace('item.stat().st_size', 'len(item.read_text(encoding="utf-8", errors="replace"))')
    elif fault == 'follow-links':
        branch = branch.replace('item.is_symlink() or ', '')
    elif fault == 'escaping-path':
        branch = branch.replace('self.path(args.get("path", "."))', '(self.root / args.get("path", ".")).resolve()')
        # Keep the bypass observable: incidental relative_to errors must not
        # make an escaping implementation appear to enforce the boundary.
        branch = branch.replace('item.relative_to(self.root).as_posix()', '__import__("os").path.relpath(item, self.root).replace(chr(92), "/")')
        branch = branch.replace('path.relative_to(self.root).as_posix()', '__import__("os").path.relpath(path, self.root).replace(chr(92), "/")')
    elif fault == 'exact-boundary':
        branch = branch.replace('if len(files) > 200:', 'if len(files) >= 200:')
    elif fault == 'schema-required':
        pass
    elif fault not in (None, 'absent'):
        raise ValueError('Unknown fault')
    if fault == 'absent':
        return result
    specs = {'inventory_files': ('List workspace files.', {'path': {'type': 'string'}, 'recursive': {'type': 'boolean'}}, [])}
    if fault == 'schema-required':
        specs['inventory_files'][2].append('path')
    for item in result:
        if item['path'] == 'autoproteus/tools.py':
            text = base64.b64decode(item['data']).decode()
            anchor = '        if tool == "list_files":'
            if text.count(anchor) != 1:
                raise ValueError('Tool anchor changed')
            item['data'] = base64.b64encode(text.replace(anchor, branch + anchor, 1).encode()).decode()
        elif item['path'] == 'autoproteus/providers.py':
            text = base64.b64decode(item['data']).decode()
            item['data'] = base64.b64encode(text.replace('TOOL_SPECS = {', 'TOOL_SPECS = ' + repr(specs) + ' | {', 1).encode()).decode()
    return result


def inventory():
    names = [path for path in (ROOT / 'controller').glob('*.py')]
    names += [ROOT / name for name in ('guest/worker.py', 'controller/runtime-lock.json',
        'tests/test_seed.py', 'tests/test_text_helpers.py', 'evaluations/guidance_comparison.py',
        'evaluations/guidance_inventory_probe.py', 'evaluations/workflow_variants.py')]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in names}


def prepare(output):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / '.data').resolve()) or output.exists():
        raise ValueError('Use a new directory inside .data; existing evidence is preserved')
    source = seed_files(ROOT)
    guide = next(item for item in source if item['path'] == 'README.md')
    if len(base64.b64decode(guide['data']).decode('utf-8')) > 12000:
        raise ValueError('Starter guide exceeds the whole-file read limit; shorten it before comparison')
    output.mkdir(parents=True)
    arms = {}
    for name in ('baseline', 'short-guidance'):
        pack = variant(source, name)
        atomic_json(output / (name + '.json'), pack)
        arms[name] = {'file': name + '.json', 'sha256': source_identity(pack)}
    plan = {'created': now(), 'state': 'prepared_no_model_runs', 'arms': arms, 'trusted': inventory(),
        'tasks': tasks(), 'internet': False, 'model_profile': 'Freeze the selected standard connection before model calls.',
        'order': [['baseline', 'short-guidance'], ['short-guidance', 'baseline'], ['baseline', 'short-guidance']],
        'allowance': {'actions': 128, 'generated_tokens': 65536, 'wall_seconds': 1800, 'shared_across_stages': True},
        'protocol': 'Same model/profile, inputs and unchanged grader in both arms. Protected regressions and calibrated '
                    'feature checks precede activation. Preserve inputs and activated source, require the named tool, '
                    'correct final JSON and explicit completion. No extra final-use instruction or candidate repair. '
                    'Score correct artifacts, complete workflows and default-argument omission separately. '
                    'Record infrastructure failures and operator interventions separately. '
                    'The treatment changes prompt guidance and the README upgrade workflow only; scripts/plans are optional. '
                    'No live execution is performed by this preparation helper.'}
    atomic_json(output / 'plan.json', plan)
    (output / 'plan.sha256').write_text(hashlib.sha256((output / 'plan.json').read_bytes()).hexdigest())
    return plan


def calibrate(output):
    output = Path(output).resolve()
    if not output.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Comparison must stay inside .data')
    plan = json.loads((output / 'plan.json').read_text(encoding='utf-8'))
    if inventory() != plan['trusted'] or hashlib.sha256((output / 'plan.json').read_bytes()).hexdigest() != (output / 'plan.sha256').read_text(encoding='utf-8'):
        raise ValueError('Frozen inputs changed; prepare a new comparison')
    for name, arm in plan['arms'].items():
        if arm['file'] != name + '.json' or name not in ('baseline', 'short-guidance'):
            raise ValueError('Invalid frozen arm')
        if source_identity(json.loads((output / arm['file']).read_text(encoding='utf-8'))) != arm['sha256']:
            raise ValueError('Frozen arm changed; prepare a new comparison')
    settings = SimpleNamespace(values={**DEFAULTS, 'provider': 'demo', 'configured': True,
                                       'terminal': True, 'internet': False}, key=lambda: '')
    class Client:
        index = 0
        def complete(self, messages, cancel):
            self.index += 1
            return {'content': json.dumps({'action': {'tool': 'run_command', 'arguments': {
                'command': 'python3 heldout_inventory.py'}}} if self.index == 1 else {'status': 'completed'})}
    folder = output / 'calibration'
    if folder.exists():
        raise ValueError('Calibration already exists; preserve it and prepare a new comparison')
    store = Store(folder / 'sessions')
    source = json.loads((output / plan['arms']['baseline']['file']).read_text(encoding='utf-8'))
    regressions = {}
    for name, arm in plan['arms'].items():
        pack = json.loads((output / arm['file']).read_text(encoding='utf-8'))
        frozen = freeze_source(store, pack, 'Frozen ' + name)
        regressions[name] = run_regressions(ROOT, store, frozen)
        atomic_json(output / 'regressions.json', regressions)
        if not regressions[name]['passed']:
            raise RuntimeError('Protected regression failed: ' + name)
    report = {}
    for fault in (None, 'absent', 'recursive-default', 'character-count', 'follow-links', 'escaping-path',
                  'exact-boundary', 'schema-required'):
        name = fault or 'positive'
        pack = reference(source, fault)
        frozen = freeze_source(store, pack, name)
        agent = IsolatedAgent(ROOT, store, settings, lambda config: Client())
        try:
            run = run_task(agent, store, settings.values, {'name': name, 'task': 'Run independent inventory checks.',
                'fixtures': {'heldout_inventory.py': (ROOT / 'evaluations/guidance_inventory_probe.py').read_text(encoding='utf-8')},
                'checks': [{'path': 'guidance-probe-result.json'}]}, frozen, 90)
            data = json.loads(Artifacts(store, store.get(run['session'])).read('guidance-probe-result.json'))
            report[name] = {'run': run, 'probe': data}
            atomic_json(output / 'calibration.json', report)
            if not run['passed'] or data['passed'] != (fault is None):
                raise RuntimeError('Inventory grader calibration failed: ' + name)
        finally:
            agent.close()
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'calibrate'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = prepare(args.output) if args.command == 'prepare' else calibrate(args.output)
    print('Prepared frozen inputs.' if args.command == 'prepare' else 'Scripted VM calibration passed.')
    print('No model calls started.')
