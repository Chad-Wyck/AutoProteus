"""Frozen study inputs and independently checked calibration; never starts inference."""
import json
import platform
from pathlib import Path
from urllib.parse import urlparse

from autoproteus.providers import tool_definitions
from controller.config import DEFAULTS
from controller.evaluation import freeze_source, source_identity
from controller.isolation import seed_files
from controller.storage import atomic_json, now
from study_support import file_identity, identity
from workflow_variants import variant
import generalization as study

ROOT = Path(__file__).resolve().parents[1]


def private(path):
    path = (ROOT / path).resolve()
    if not path.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Study outputs must stay inside .data')
    return path


def trusted_files():
    paths = list((ROOT / 'controller').glob('*.py'))
    paths += [ROOT / name for name in ('guest/worker.py', 'controller/runtime-lock.json',
        'controller/managed-runtime-lock.json', 'tests/test_seed.py', 'tests/test_text_helpers.py',
        'evaluations/model_study.py', 'evaluations/model_plan.py', 'evaluations/study_support.py', 'evaluations/generalization.py',
        'evaluations/grader_faults.py', 'evaluations/workflow_variants.py', 'evaluations/workflow_support.py',
        'evaluations/edit_context.py', 'evaluations/lessons/verified-submission.md',
        'evaluations/generalization-probe.py', 'evaluations/local-model-benchmark.py',
        'evaluations/local-feature-probe.py', 'evaluations/local-upgrade-tasks.json',
        'evaluations/observations.py', 'evaluations/run_budget.py', 'evaluations/invoke_tool.py', 'evaluations/tasks.json')]
    return {p.relative_to(ROOT).as_posix(): file_identity(p) for p in paths}


def environment():
    # Appliance.verify checks the installed bytes against this complete inventory
    # before any cached calibration can be reused.
    record = ROOT / '.runtime/isolation/installed.json'
    return {'platform': platform.platform(), 'machine': platform.machine(),
            'python': platform.python_version(), 'root': str(ROOT),
            'appliance_inventory_sha256': file_identity(record) if record.exists() else None}


def prepare(args):
    output = private(args.output)
    if output.exists():
        raise ValueError('Prepare into a new directory; existing evidence is preserved')
    profiles = json.loads(Path(args.profiles).read_text(encoding='utf-8'))
    if not isinstance(profiles, list) or not profiles:
        raise ValueError('Supply a nonempty list of profiles')
    seen = set()
    for profile in profiles:
        slug = profile['id']
        if not isinstance(slug, str) or not slug or len(slug) > 60 or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in slug) or slug in seen:
            raise ValueError('Profiles need unique lowercase IDs')
        seen.add(slug)
        config = profile['config'] = {**DEFAULTS, 'configured': True, 'terminal': True, **profile['config']}
        if config['provider'] not in ('ollama', 'hosted') or urlparse(config['base_url']).hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('This runner accepts local inference endpoints only')
        if config['response_tokens'] >= config['context_tokens']:
            raise ValueError('Response allowance must be smaller than context')
        for path, digest in profile.get('assets', {}).items():
            if file_identity(path) != digest:
                raise ValueError('Profile asset failed verification: ' + path)
    source = seed_files(ROOT)
    plan = {'created': now(), 'mode': args.mode, 'repeats': args.repeats if args.repeats is not None else (3 if args.mode == 'full' else 1),
            'source': source, 'source_sha256': source_identity(source), 'profiles': profiles,
            'trusted_sha256': trusted_files(), 'environment': environment(),
            'contracts': study.CONTRACTS, 'recipe': study.RECIPE,
            'tasks': json.loads((ROOT / 'evaluations/tasks.json').read_text(encoding='utf-8')),
            'tools': tool_definitions(True),
            'invoke_tool': (ROOT / 'evaluations/invoke_tool.py').read_text(encoding='utf-8'),
            'deadline': args.timeout, 'generated_tokens': args.output_token_budget,
            'ordinary_deadline': 240, 'ordinary_generated_tokens': 8192,
            'ordinary_tasks': ['exact-file', 'precise-edit', 'recovery', 'unicode', 'bug-fix'],
            'upgrade_tasks': (list(study.CONTRACTS) if args.mode == 'full' else
                              ['sha256_file', 'format_json'] if args.mode == 'screen' else []),
            'scope': 'Screens select profiles for qualification; incomplete screens are not model rankings. '
                     'Each accepted first upgrade receives one fresh second-extension task. '
                     'Retries, untested cells, cached checks and infrastructure failures are recorded separately.'}
    experiment = getattr(args, 'experiment', None)
    if experiment:
        if args.mode != 'full':
            raise ValueError('Paired workflow experiments require full mode')
        plan['experiment'] = experiment
        plan['mask_settings'] = {'keep': getattr(args, 'mask_keep', 8), 'threshold': getattr(args, 'mask_threshold', 512)}
        plan['variants'] = {name: variant(source, name, **plan['mask_settings']) for name in ('baseline', experiment)}
        plan['scope'] += ' Paired opt-in treatment; original default seed remains unchanged. Success and matched-success costs are separate.'
        parent_path = getattr(args, 'parent_source', None)
        parent_tool = getattr(args, 'parent_tool', None)
        if bool(parent_path) != bool(parent_tool):
            raise ValueError('Provide both --parent-source and --parent-tool')
        if parent_path:
            if experiment not in ('phases', 'staged-inputs', 'submission-feedback', 'edit-context', 'verified-lesson') or parent_tool not in study.CONTRACTS:
                raise ValueError('This comparison does not support a supplied parent')
            if experiment == 'staged-inputs' and parent_tool == 'csv_preview':
                raise ValueError('Staged inputs currently require a sha256_file or format_json parent')
            parent = json.loads(Path(parent_path).read_text(encoding='utf-8'))
            # Inert bytes only; actual regression/feature/public checks precede inference.
            source_identity(parent)
            plan['parent'] = {'source': parent, 'tool': parent_tool, 'sha256': source_identity(parent),
                              'provenance': str(Path(parent_path).resolve()), 'supplied_parent': True}
        elif experiment in ('phases', 'staged-inputs'):
            raise ValueError('This comparison requires one exact supplied parent and --parent-tool; it is independently checked before trials')
        reuse_path = getattr(args, 'reuse_task', None)
        if reuse_path:
            if experiment == 'staged-inputs':
                raise ValueError('Staged inputs measure new extensions, not reuse-only tasks')
            if not plan.get('parent'):
                raise ValueError('--reuse-task requires the phase comparison and a supplied parent')
            task = json.loads(Path(reuse_path).read_text(encoding='utf-8'))
            required = task.get('required_tools')
            if (not isinstance(required, list) or not required or any(name not in study.CONTRACTS for name in required)
                    or not isinstance(task.get('checks'), list) or not task['checks'] or not isinstance(task.get('task'), str)):
                raise ValueError('Reuse task needs a task, nonempty checks and required_tools from the known contracts')
            plan['reuse_task'] = task
    elif any(getattr(args, name, None) for name in ('parent_source', 'parent_tool', 'reuse_task')):
        raise ValueError('Parent/reuse options require a supported supplied-parent experiment')
    task_pack = getattr(args, 'task_pack', None)
    if task_pack:
        tasks = json.loads(Path(task_pack).read_text(encoding='utf-8'))
        if (not isinstance(tasks, list) or not tasks or any(not isinstance(task.get('name'), str) or
                not task.get('task') or not task.get('checks') for task in tasks) or
                len({task['name'] for task in tasks}) != len(tasks)):
            raise ValueError('Task pack needs uniquely named tasks with instructions and independent checks')
        plan['tasks'], plan['ordinary_tasks'] = tasks, [task['name'] for task in tasks]
        plan['task_pack'] = {'path': str(Path(task_pack).resolve()), 'sha256': file_identity(task_pack)}
    if plan['repeats'] < 1 or args.timeout < 1 or args.output_token_budget < 1:
        raise ValueError('Repeat and budget values must be positive')
    output.mkdir(parents=True)
    atomic_json(output / 'plan.json', plan)
    (output / 'plan.sha256').write_text(identity(plan), encoding='ascii')
    for name in plan['trusted_sha256']:
        target = output / 'trusted-runner' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    print('Prepared', args.mode, 'with', len(profiles), 'profiles and', plan['repeats'], 'repeat(s). No inference started.', flush=True)


def check(plan):
    if source_identity(seed_files(ROOT)) != plan['source_sha256'] or trusted_files() != plan['trusted_sha256']:
        raise ValueError('Seed or trusted runner changed; prepare a new plan')
    if environment() != plan['environment']:
        raise ValueError('Execution environment changed; prepare a new plan')


def growth_feature(parent):
    return 'sha256_file' if parent in ('format_json', 'csv_preview') else 'format_json'


def workflow_requirements(plan):
    """One description drives both cache identity and the checks it represents."""
    parent = plan.get('parent', {}).get('tool')
    reuse = bool(plan.get('reuse_task'))
    required = set(plan.get('reuse_task', {}).get('required_tools', []))
    if parent:
        required.add(parent)
    return {'experiment': plan['experiment'], 'mode': 'reuse' if reuse else 'growth',
            'parent_tool': parent, 'required_existing_tools': sorted(required),
            'required_absent_tool': growth_feature(parent) if parent and not reuse else None}


def calibrate(plan, output, cache, study, run_regressions):
    from controller.storage import Store
    def calibration():
        folder = output / 'grader-calibration'
        suffix = 1
        while folder.exists():
            suffix += 1
            folder = output / ('grader-calibration-%03d' % suffix)
        study.self_check(folder, plan['source'])
        return {'passed': True, 'evidence': str(folder),
                'report_sha256': file_identity(folder / 'calibration.json'),
                'report': json.loads((folder / 'calibration.json').read_text(encoding='utf-8'))}
    def valid_calibration(row):
        try:
            return row.get('passed') is True and file_identity(Path(row['evidence']) / 'calibration.json') == row['report_sha256']
        except (OSError, KeyError, TypeError):
            return False
    if plan['mode'] != 'benchmark':
        value, receipt = cache.run({'source': plan['source_sha256'], 'trusted': plan['trusted_sha256'],
                                    'environment': plan['environment'], 'kind': 'generalization-calibration'},
                                   calibration, valid_calibration)
        atomic_json(output / 'calibration-receipt.json', {'cache': receipt, 'result': value})
    if plan.get('experiment'):
        # This calibration is tied to the exact copied input, never to a model's
        # claim of readiness. A supplied parent earns no first-upgrade credit.
        requirements = workflow_requirements(plan)
        inputs = {'source': plan.get('parent', {}).get('sha256', plan['source_sha256']),
                  'variants': {key: source_identity(value) for key, value in plan['variants'].items()},
                  'trusted': plan['trusted_sha256'], 'environment': plan['environment'], 'kind': 'workflow-inputs',
                  'requirements': requirements}
        def calibrate_inputs():
            store = Store(output / 'input-calibration/sessions')
            results = {}
            for name, source in plan['variants'].items():
                source = plan['parent']['source'] if plan.get('parent') else source
                frozen = freeze_source(store, source, 'Exact workflow input ' + name)
                results[name] = {'regressions': run_regressions(ROOT, store, frozen)}
                if plan.get('parent'):
                    for feature in requirements['required_existing_tools']:
                        results[name].update({feature: study.verify_feature(store, frozen, feature),
                                             feature + '_public': study.verify_public(store, frozen, feature)})
                    added = requirements['required_absent_tool']
                    if added:
                        absent = study.verify_feature(store, frozen, added)
                        cases = absent.get('probe', {}).get('checks', {})
                        results[name]['new_tool_absent'] = {'passed': not absent['passed'] and cases.get('registered') is False,
                                                           'evidence': absent}
                atomic_json(output / 'input-calibration.json', results)
                if not all(row['passed'] for row in results[name].values()):
                    raise ValueError('Workflow input failed independent checks: ' + name)
            return {'passed': True, 'requirements': requirements, 'results': results, 'evidence': str(output / 'input-calibration.json'),
                    'report_sha256': file_identity(output / 'input-calibration.json')}
        def valid_inputs(row):
            try:
                return (row.get('passed') is True and row.get('requirements') == requirements and
                        file_identity(row['evidence']) == row['report_sha256'])
            except (OSError, TypeError, KeyError):
                return False
        value, receipt = cache.run(inputs, calibrate_inputs, valid_inputs)
        atomic_json(output / 'input-calibration-receipt.json', {'result': value, 'cache': receipt})
