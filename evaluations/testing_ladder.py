"""A graded testing ladder for the seed, on the completion-study protocol.

One harness, ordered rungs. Each rung is a model class run against the
project's own frozen completion study (``completion_study.py``: prepare ->
calibrate -> run, check-only before any inference):

  1. ``local-tiny``    the smallest local class — proves the loop end to end.
  2. ``local-default`` the project's own default local model.
  3. ``local-large``   the largest local class this kind of box can hold.
  4. ``hosted-top``    a rented, production-grade hosted engine — the exact
                       qualification test that has failed twice. This rung
                       is DESIGNED BUT SPEND-GATED: it is never prepared or
                       run unless a human approves the API spend out loud,
                       in advance, with the amount named.

Receipts are recorded per rung, pass or fail, in the project's evidence
style. A rung that could not run says why — endpoint unreachable, model not
downloaded, calibration blocked, spend not approved. Nothing is inferred,
estimated or filled in. Local preflight uses Ollama's model-listing call
only; listing is not inference. Study outputs stay under ``.data/``.
"""
import argparse
import json
import platform
import subprocess
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'evaluations')]
from controller.storage import atomic_json  # noqa: E402

LADDER_DIR = ROOT / '.data' / 'testing-ladder'
COMPLETION_STUDY = ROOT / 'evaluations' / 'completion_study.py'

RUNGS = [
    {'id': 'local-tiny', 'kind': 'local', 'provider': 'ollama',
     'base_url': 'http://127.0.0.1:11434', 'model': 'qwen2.5:0.5b',
     'context_tokens': 8192, 'response_tokens': 2048,
     'purpose': 'Smallest local class. Proves the growth loop works at all: '
                'prepare, calibration and three frozen tasks, end to end.'},
    {'id': 'local-default', 'kind': 'local', 'provider': 'ollama',
     'base_url': 'http://127.0.0.1:11434', 'model': 'qwen3:4b-instruct',
     'context_tokens': 32768, 'response_tokens': 8192,
     'purpose': "The project's own default local model (controller DEFAULTS). "
                'The rung a typical user machine would actually run.'},
    {'id': 'local-large', 'kind': 'local', 'provider': 'ollama',
     'base_url': 'http://127.0.0.1:11434', 'model': 'qwen2.5:14b',
     'context_tokens': 32768, 'response_tokens': 8192,
     'purpose': 'Largest local class a well-equipped home box can hold. '
                'Finds where local capability stops being the limit.'},
    {'id': 'hosted-top', 'kind': 'hosted', 'provider': 'hosted',
     'base_url': 'http://127.0.0.1:11434', 'model': None,
     'context_tokens': 32768, 'response_tokens': 8192,
     'requires_spend': True,
     'purpose': 'A rented production-grade engine, chosen and priced at '
                'approval time. Production-model qualification is the test '
                'that has failed twice; this rung is where it is answered. '
                'DESIGNED, NOT BUILT OUT: no run without explicit spend '
                'approval naming the amount beforehand.'},
]


def rung_by_id(rung_id):
    for rung in RUNGS:
        if rung['id'] == rung_id:
            return rung
    raise ValueError(f'Unknown rung: {rung_id}')


def profile_for(rung):
    """A completion_study prepare profile for this rung (no keys, ever)."""
    config = {'provider': rung['provider'], 'base_url': rung['base_url'],
              'context_tokens': rung['context_tokens'],
              'response_tokens': rung['response_tokens'],
              'internet': False}
    if rung['model']:
        config['model'] = rung['model']
    return {'config': config}


def parse_tags(payload):
    """Model names from an Ollama /api/tags payload (bytes or text)."""
    data = json.loads(payload)
    return sorted(entry['name'] for entry in data.get('models', [])
                  if isinstance(entry, dict) and entry.get('name'))


def probe_endpoint(base_url, timeout=3):
    """List models at a local Ollama endpoint. Listing is not inference."""
    try:
        with urllib.request.urlopen(base_url.rstrip('/') + '/api/tags',
                                    timeout=timeout) as response:
            return {'reachable': True, 'models': parse_tags(response.read()),
                    'error': None}
    except (urllib.error.URLError, OSError, ValueError) as error:
        return {'reachable': False, 'models': [], 'error': str(error)[:200]}


def preflight(rung, probe=probe_endpoint):
    """Check-only: can this rung run here right now? Starts no inference."""
    if rung.get('requires_spend'):
        return {'status': 'spend-gated',
                'detail': 'Hosted rung: no probe made. Running it is real API '
                          'spend and needs explicit approval, amount named, first.'}
    result = probe(rung['base_url'])
    if not result['reachable']:
        return {'status': 'endpoint-unreachable',
                'detail': f"No local inference endpoint answered at "
                          f"{rung['base_url']}: {result['error']}"}
    if rung['model'] not in result['models']:
        return {'status': 'model-not-downloaded',
                'detail': f"Endpoint is up with {len(result['models'])} model(s), "
                          f"but {rung['model']} is not among them."}
    return {'status': 'ready',
            'detail': f"Endpoint up; {rung['model']} is downloaded and listed."}


def ensure_runnable(rung, preflight_status, approve_spend=False):
    """Fail closed: name exactly why a rung may not run, or return True."""
    if rung.get('requires_spend') and not approve_spend:
        raise ValueError('hosted-top is spend-gated: it runs only after '
                         'explicit spend approval with the amount named.')
    if preflight_status != 'ready' and not rung.get('requires_spend'):
        raise ValueError(f"Rung {rung['id']} is not runnable here: {preflight_status}")
    return True


def _private(path):
    path = Path(path).resolve()
    if not path.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Ladder outputs must stay inside the project .data directory')
    return path


def _study_dir(rung):
    return LADDER_DIR / rung['id'] / 'study'


def _run_study_cli(arguments, timeout):
    completed = subprocess.run(
        [sys.executable, '-X', 'utf8', str(COMPLETION_STUDY), *arguments],
        cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    tail = (completed.stdout + completed.stderr).strip().splitlines()
    return {'exit_code': completed.returncode,
            'passed': completed.returncode == 0,
            'tail': tail[-3:] if tail else []}


def prepare_rung(rung, timeout=600):
    """Freeze a completion-study plan for this rung. Starts no inference."""
    if rung.get('requires_spend'):
        return {'status': 'spend-gated',
                'detail': 'Hosted plans are prepared only after spend approval.'}
    study = _study_dir(rung)
    if study.exists():
        return {'status': 'already-prepared',
                'detail': 'A frozen plan already exists; previous evidence is preserved.'}
    study.parent.mkdir(parents=True, exist_ok=True)
    profile_path = study.parent / 'profile.json'
    profile_path.write_text(json.dumps(profile_for(rung), indent=2),
                            encoding='utf-8')
    result = _run_study_cli(['prepare', '--profile', str(profile_path),
                             '--output', str(study.relative_to(ROOT))], timeout)
    return {'status': 'prepared' if result['passed'] else 'prepare-failed',
            'detail': '; '.join(result['tail']) or f"exit {result['exit_code']}"}


def calibrate_rung(rung, timeout=1800):
    """Run the study's check-only calibration: regressions + scripted
    grader controls against the live oracle. Starts no model inference."""
    if rung.get('requires_spend'):
        return {'status': 'spend-gated',
                'detail': 'Hosted calibration waits for spend approval.'}
    study = _study_dir(rung)
    if not study.exists():
        return {'status': 'not-prepared', 'detail': 'Prepare this rung first.'}
    receipt = study / 'calibration.json'
    if receipt.exists():
        return {'status': 'already-calibrated',
                'detail': 'calibration.json already recorded for this exact plan.'}
    result = _run_study_cli(['run', '--input', str(study.relative_to(ROOT)),
                             '--check-only'], timeout)
    if result['passed'] and receipt.exists():
        return {'status': 'calibrated',
                'detail': 'Regressions and scripted grader controls passed; '
                          'calibration.json recorded. No inference was started.'}
    failure = study / 'calibration-failure.json'
    return {'status': 'calibration-failed',
            'detail': ('; '.join(result['tail']) or f"exit {result['exit_code']}") +
                      (' Failure detail recorded in calibration-failure.json.'
                       if failure.exists() else '')}


def run_rung(rung, approve_spend=False, timeout=3600):
    """Live inference for one rung — gated, and refused out loud otherwise."""
    ensure_runnable(rung, preflight(rung)['status'], approve_spend)
    study = _study_dir(rung)
    if not (study / 'calibration.json').exists():
        raise ValueError('Calibrate the exact plan before live inference.')
    result = _run_study_cli(['run', '--input', str(study.relative_to(ROOT))], timeout)
    return {'status': 'ran' if result['passed'] else 'run-failed',
            'detail': '; '.join(result['tail']) or f"exit {result['exit_code']}"}


def receipt_for(rung, phases):
    return {'schema_version': 1, 'kind': 'testing-ladder-rung',
            'rung': rung['id'], 'kind_of_model': rung['kind'],
            'model': {'provider': rung['provider'], 'model': rung['model'],
                      'base_url': rung['base_url']},
            'purpose': rung['purpose'],
            'recorded_at_utc': datetime.now(timezone.utc).isoformat(),
            'environment': {'platform': platform.platform(),
                            'machine': platform.machine(),
                            'python': platform.python_version()},
            'phases': phases,
            'scope': ['Receipts record exactly what ran on this machine. '
                      'A phase that did not run says so, with the reason.',
                      'No hosted spend is committed by this ladder.']}


def record_rung(rung, phases):
    directory = _private(LADDER_DIR / rung['id'])
    directory.mkdir(parents=True, exist_ok=True)
    receipt = receipt_for(rung, phases)
    atomic_json(directory / 'receipt.json', receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('list')
    for name in ('preflight', 'prepare', 'calibrate', 'run'):
        sub = commands.add_parser(name)
        sub.add_argument('--rung', help='One rung id (default: all local rungs)')
        sub.add_argument('--approve-spend', action='store_true',
                         help='Required, with a named amount agreed beforehand, '
                              'before the hosted rung can do anything')
    args = parser.parse_args(argv)

    if args.command == 'list':
        for rung in RUNGS:
            gate = ' [spend-gated]' if rung.get('requires_spend') else ''
            print(f"{rung['id']:<14} {rung['kind']:<7} {rung['model'] or '(chosen at approval)'}{gate}")
            print(f"{'':<14} {rung['purpose']}")
        return 0
    selected = [rung_by_id(args.rung)] if args.rung else RUNGS
    for rung in selected:
        phases = {}
        check = preflight(rung)
        phases['preflight'] = check
        print(f"{rung['id']}: preflight = {check['status']} — {check['detail']}")
        if args.command in ('prepare', 'calibrate', 'run'):
            phases['prepare'] = prepare_rung(rung)
            print(f"{rung['id']}: prepare = {phases['prepare']['status']}")
        if args.command in ('calibrate', 'run'):
            phases['calibrate'] = calibrate_rung(rung)
            print(f"{rung['id']}: calibrate = {phases['calibrate']['status']}")
        if args.command == 'run':
            try:
                phases['run'] = run_rung(rung, approve_spend=args.approve_spend)
            except ValueError as error:
                phases['run'] = {'status': 'refused', 'detail': str(error)}
            print(f"{rung['id']}: run = {phases['run']['status']}")
        record_rung(rung, phases)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
