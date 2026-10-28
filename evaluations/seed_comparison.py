"""Freeze independent seed interventions as data. Preparation never starts inference."""
import argparse
import ast
import base64
from copy import deepcopy
import json
import re
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'evaluations')]
from controller.artifacts import seed_files
from controller.evaluation import source_identity
from controller.storage import atomic_json, now
from study_support import file_identity, identity
from activation_use import contract

EDIT_FILES = {'autoproteus/file_ops.py'}
FINISH_FILES = {'autoproteus/protocol.py', 'autoproteus/providers.py'}
SEEDS = [104729, 130363, 155921]


def git(*arguments):
    result = subprocess.run(['git', *arguments], cwd=ROOT, capture_output=True, check=True, timeout=15)
    return result.stdout


def native_text(data):
    tree = ast.parse(data)
    for item in tree.body:
        if isinstance(item, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'NATIVE' for target in item.targets):
            value = ast.literal_eval(item.value)
            if isinstance(value, str) and 1 <= len(value) <= 12000: return value
    raise ValueError('No bounded native instruction constant in the selected controller')


def prepare(output, baseline_ref='HEAD'):
    output = (ROOT/Path(output)).resolve()
    if not output.is_relative_to((ROOT/'.data').resolve()) or output.exists():
        raise ValueError('Prepare a new directory inside .data; preserve existing evidence')
    if not isinstance(baseline_ref, str) or not baseline_ref or baseline_ref.startswith('-'):
        raise ValueError('Supply a Git baseline reference')
    revision = git('rev-parse', '--verify', baseline_ref+'^{commit}').decode().strip()
    current = seed_files(ROOT)
    baseline = []
    for item in current:
        path = 'SEED.md' if item['path'] == 'README.md' else item['path']
        baseline.append({'path': item['path'], 'data': base64.b64encode(git('show', revision+':'+path)).decode('ascii')})
    git_source_sha256 = source_identity(baseline)
    before, after = ({item['path']: item['data'] for item in pack} for pack in (baseline, current))
    # Align Git-normalized line endings to each current file's convention and
    # record that normalization. No candidate module is imported or executed.
    normalized = []
    for item in baseline:
        path = item['path']
        text = base64.b64decode(item['data']).decode('utf-8').replace('\r\n', '\n')
        newline = '\r\n' if '\r\n' in base64.b64decode(after[path]).decode('utf-8') else '\n'
        normalized_data = base64.b64encode(text.replace('\n', newline).encode('utf-8')).decode('ascii')
        if normalized_data != item['data']: normalized.append(path)
        item['data'] = normalized_data
    release_metadata = []
    for item in baseline:
        if item['path'] != 'autoproteus/__init__.py': continue
        old = base64.b64decode(item['data']).decode('utf-8')
        new = base64.b64decode(after[item['path']]).decode('utf-8')
        pattern = r'^__version__ = "([0-9]+\.[0-9]+\.[0-9]+)"\r?$'
        previous = re.search(pattern, old, re.MULTILINE)
        current_version = re.search(pattern, new, re.MULTILINE)
        if previous and current_version and previous[1] != current_version[1]:
            aligned = old[:previous.start()] + current_version[0] + old[previous.end():]
            if aligned == new:
                item['data'] = after[item['path']]
                release_metadata.append({'path':item['path'], 'before':previous[1], 'after':current_version[1]})
    before = {item['path']: item['data'] for item in baseline}
    changed = {path for path in before if before[path] != after[path]}
    if changed != EDIT_FILES | FINISH_FILES:
        raise ValueError('Expected only the three targeted seed files to differ; found: '+', '.join(sorted(changed)))
    old_native = native_text(git('show', revision+':controller/action_protocol.py'))
    new_native = native_text((ROOT/'controller/action_protocol.py').read_bytes())
    sources = {'baseline': baseline, 'edit-result-only': deepcopy(baseline),
               'finish-only': deepcopy(baseline), 'combined': current}
    for arm, paths in (('edit-result-only', EDIT_FILES), ('finish-only', FINISH_FILES)):
        for item in sources[arm]:
            if item['path'] in paths: item['data'] = after[item['path']]
    output.mkdir(parents=True)
    arms = {}
    for name, source in sources.items():
        atomic_json(output/(name+'-source.json'), source)
        native = new_native if name in ('finish-only', 'combined') else old_native
        (output/(name+'-native.txt')).write_text(native, encoding='utf-8', newline='\n')
        arms[name] = {'source': name+'-source.json', 'source_sha256': source_identity(source),
            'native_instructions': name+'-native.txt', 'native_sha256': file_identity(output/(name+'-native.txt')),
            'changed_seed_files': sorted(path for path in before if before[path] != {item['path']:item['data'] for item in source}[path])}
    basic = json.loads((ROOT/'evaluations/tasks.json').read_text(encoding='utf-8'))
    names = {'exact-file', 'precise-edit', 'recovery', 'unicode', 'bug-fix'}
    basic = [task for task in basic if task['name'] in names]
    csv = {'name': 'csv_preview', 'first_use': contract('csv_preview', 'csv-repeat')}
    schedule = []
    for repeat, seed in enumerate(SEEDS, 1):
        for study, treatment, tasks in (('finishing', 'finish-only', basic), ('unchanged-edit', 'edit-result-only', [csv])):
            for task in tasks:
                order = ['baseline', treatment] if repeat % 2 else [treatment, 'baseline']
                for arm in order:
                    schedule.append({'comparison': study, 'repeat': repeat, 'seed': seed, 'arm': arm, 'task': task['name']})
    manifest = {'created': now(), 'baseline_revision': revision, 'git_source_sha256':git_source_sha256,
        'current_source_sha256': source_identity(current), 'release_metadata_normalized':release_metadata,
        'line_ending_normalized_files': normalized, 'arms': arms, 'sampling_seed_mode': 'per-request',
        'sampling_seeds': SEEDS, 'schedule': schedule, 'basic_tasks': basic, 'csv_first_use': csv,
        'budgets': {'basic': {'seconds':240, 'generated_tokens':8192},
                    'upgrade_and_first_use': {'seconds':3600, 'generated_tokens':65536, 'actions':128}},
        'initial_screen': 'First paired seed only for finishing: 10 basic tasks. Additional repeats are a separate repeatability decision.',
        'scope': 'Inert preparation manifest, not an executable/qualified study plan. No inference, VM or effectiveness result. '
                 'Use the schedule for interleaving; separately running whole arm queues is not counterbalancing. '
                 'Freeze one model/runtime/context/sampling configuration before execution. Use fresh owned services per attempt. '
                 'Finish-only varies seed/tool wording and the frozen host native instructions; edit-result-only changes file_ops only. '
                 'The combined arm is retained for later qualification, not part of either isolated comparison.'}
    atomic_json(output/'manifest.json', manifest)
    (output/'manifest.sha256').write_text(identity(manifest), encoding='ascii')
    return manifest


def load(output):
    """Validate inert receipts without opening sessions or starting services."""
    output = Path(output).resolve()
    manifest = json.loads((output/'manifest.json').read_text(encoding='utf-8'))
    if identity(manifest) != (output/'manifest.sha256').read_text().strip():
        raise ValueError('Comparison manifest changed')
    for arm in manifest['arms'].values():
        paths = [(output/arm[key]).resolve() for key in ('source', 'native_instructions')]
        if any(path.parent != output or path.stat().st_size > 2*1024*1024 for path in paths):
            raise ValueError('Invalid comparison artifact path or size')
        if source_identity(json.loads(paths[0].read_text(encoding='utf-8'))) != arm['source_sha256'] or file_identity(paths[1]) != arm['native_sha256']:
            raise ValueError('Frozen comparison arm changed')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--baseline-ref', default='HEAD')
    parser.add_argument('--check-only', action='store_true', help='Verify saved source/instruction hashes only; no VM or inference')
    args = parser.parse_args()
    value = load(args.output) if args.check_only else prepare(args.output, args.baseline_ref)
    print('Validated frozen comparison.' if args.check_only else 'Frozen baseline, isolated edits, isolated finishing and combined sources. No models or VMs started.')
