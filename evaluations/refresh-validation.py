"""Regenerate the public VALIDATION evidence bundle at the current commit.

One command re-runs the ordinary regression suite (or ingests an existing
log it is handed) and writes a bundle in exactly the published v0.5.1 format:

    docs/validation/v<version>/
        ordinary-tests.log   unmodified unittest output
        real-vm-tests.log    only when a VM log is supplied with --vm-log
        results.json         machine-readable summary (schema_version 1)
        SHA256SUMS           sha256sum-compatible manifest of the above

With --update-page it also rewrites VALIDATION.md to describe the new
bundle. The real-VM suite is never started by this script: it stays a
documented step on a prepared KVM/WHPX machine, and its log can be bundled
afterwards with --vm-log. No model inference is started, ever. Refuses to
overwrite an existing bundle directory — published evidence is preserved.
"""
import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ORDINARY_COMMAND = [sys.executable, '-X', 'utf8', '-m', 'unittest',
                    'discover', '-s', 'tests', '-q']
REPO_URL = 'https://github.com/Chad-Wyck/AutoProteus'


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def summarize_unittest_log(text):
    """Parse the tail of a `unittest discover` log into suite counts.

    passed is derived: ran - failures - errors - skipped. Skips are never
    counted as passes. Raises ValueError when the summary is missing, so a
    truncated or crashed run can never be bundled as evidence.
    """
    ran = re.search(r'^Ran (\d+) tests? in ([0-9.]+)s', text, re.MULTILINE)
    if not ran:
        raise ValueError('Log has no "Ran N tests" summary; refusing to bundle it.')
    status = re.search(r'^(OK|FAILED)(?: \(([^)]*)\))?\s*$', text, re.MULTILINE)
    if not status:
        raise ValueError('Log has no OK/FAILED status line; refusing to bundle it.')
    counts = {'failures': 0, 'errors': 0, 'skipped': 0}
    if status.group(2):
        for key, value in re.findall(r'(failures|errors|skipped)=(\d+)', status.group(2)):
            counts[key] = int(value)
    if status.group(1) == 'OK' and (counts['failures'] or counts['errors']):
        raise ValueError('Log status is OK but lists failures/errors; refusing to bundle it.')
    discovered = int(ran.group(1))
    passed = discovered - counts['failures'] - counts['errors'] - counts['skipped']
    if passed < 0:
        raise ValueError('Log counts are inconsistent (negative passes); refusing to bundle it.')
    return {'discovered': discovered, 'passed': passed,
            'failed': counts['failures'], 'errors': counts['errors'],
            'skipped': counts['skipped'], 'seconds': float(ran.group(2))}


def starter_fingerprint(root=ROOT):
    """SHA-256 identity of the seed starter source, as in the v0.5.1 receipt."""
    from controller.evaluation import source_identity
    from controller.isolation import seed_files
    return source_identity(seed_files(root))


def current_commit(root=ROOT):
    out = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root,
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def current_version(root=ROOT):
    text = (root / 'autoproteus' / '__init__.py').read_text(encoding='utf-8')
    match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not match:
        raise ValueError('Could not read __version__ from autoproteus/__init__.py')
    return match.group(1)


def build_results(version, commit, ordinary, ordinary_log_sha, vm=None,
                  vm_log_sha=None, new_execution=True, recorded_at=None):
    """Assemble the results.json document in the published v0.5.1 shape."""
    results = {
        'schema_version': 1,
        'release': 'v' + version,
        'tested_commit': commit,
        'starter_source_sha256': starter_fingerprint(),
        'recorded_at_utc': recorded_at or datetime.now(timezone.utc).isoformat(),
        'evidence_type': ('maintainer-recorded local validation refresh; '
                          'not a CI run or independent security audit'),
        'environment': {
            'platform': platform.platform(),
            'machine': platform.machine(),
            'python': platform.python_version(),
            'vm_backend': 'QEMU/KVM or WHPX (prepared host)' if vm else 'not run',
            'guest': 'disposable Linux VM' if vm else 'not run',
        },
        'ordinary': {**ordinary, 'log': 'ordinary-tests.log',
                     'log_sha256': ordinary_log_sha},
        'real_vm': ({'selection': 'tests/test_vm_isolation.py', **vm,
                     'log': 'real-vm-tests.log', 'log_sha256': vm_log_sha}
                    if vm else None),
        'model_trials': {
            'qualification_attempts': 0,
            'qualification_passed': None,
            'scheduled_extensions': 0,
            'launched_extensions': 0,
            'extension_outcomes': None,
            'note': ('No model trials were run by this refresh. Earlier '
                     'qualification history is unchanged; see the v0.5.1 '
                     'receipts in docs/validation/v0.5.1/.'),
        },
        'provenance': {
            'generator': 'evaluations/refresh-validation.py',
            'new_test_execution': bool(new_execution),
            'logs': 'Exact bytes produced by the suite invocation (or the '
                    'log supplied for ingestion); hashes computed at bundle time.',
        },
        'scope': [
            'Results apply to the tested commit and named suite invocations only.',
            'Skipped tests are not passes; the selected VM suite is not all optional VM coverage.',
            'These checks do not prove isolation security or model self-improvement.',
        ],
    }
    return results


def write_bundle(output_dir, ordinary_log, results, vm_log=None):
    """Write logs, results.json and SHA256SUMS. Refuses an existing dir."""
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise ValueError(f'Bundle directory already exists: {output_dir}. '
                         'Published evidence is never overwritten.')
    output_dir.mkdir(parents=True)
    files = [('ordinary-tests.log', ordinary_log)]
    if vm_log is not None:
        files.append(('real-vm-tests.log', vm_log))
    for name, data in files:
        (output_dir / name).write_bytes(data)
    results_bytes = (json.dumps(results, indent=2) + '\n').encode('utf-8')
    (output_dir / 'results.json').write_bytes(results_bytes)
    manifest_lines = [f'{sha256_bytes(data)}  {name}' for name, data in files]
    manifest_lines.append(f'{sha256_bytes(results_bytes)}  results.json')
    (output_dir / 'SHA256SUMS').write_text('\n'.join(manifest_lines) + '\n',
                                           encoding='utf-8')
    return output_dir


def render_page(version, commit, recorded_date, results, bundle_rel):
    """Render the refreshed VALIDATION.md in the published page's shape."""
    ordinary = results['ordinary']
    vm = results['real_vm']
    env = results['environment']
    backend = env['vm_backend'] if vm else 'not re-run in this refresh'
    rows = [f"| Ordinary regressions | {ordinary['discovered']} | {ordinary['passed']} | "
            f"{ordinary['failed'] + ordinary['errors']} | {ordinary['skipped']} | "
            f"{ordinary['seconds']} | [Unmodified log]({bundle_rel}/ordinary-tests.log) |"]
    if vm:
        rows.append(f"| Selected real-VM suite | {vm['discovered']} | {vm['passed']} | "
                    f"{vm['failed'] + vm['errors']} | {vm['skipped']} | {vm['seconds']} | "
                    f"[Unmodified log]({bundle_rel}/real-vm-tests.log) |")
    vm_note = ('' if vm else
               '\nThe real-VM suite was not re-run for this refresh; it remains a\n'
               'documented step on a prepared KVM/WHPX machine. The most recent VM\n'
               'receipts remain the v0.5.1 bundle under `docs/validation/v0.5.1/`.\n')
    return f"""# Recorded validation

These are maintainer-recorded local test results for **v{version}**, tested commit
[`{commit}`]({REPO_URL}/commit/{commit}),
recorded on **{recorded_date}**. They describe that revision, not later local
harness changes, every supported platform, or the latest branch automatically.

This page and its bundle were produced by `evaluations/refresh-validation.py`.
Preparing it ran the ordinary suite below{" and bundled the supplied VM log" if vm else ""};
it did not start model inference. This is published recorded evidence, not a
CI run or an independent security audit.

## Results

Environment: {env['platform']}, Python {env['python']}, VM backend: {backend}.

| Suite | Discovered | Passed | Failed/errors | Skipped | Seconds | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
{chr(10).join(rows)}
{vm_note}
VM cases skipped by the ordinary invocation are not counted as ordinary
passes. Lines named `fixture` and their trial messages exercise scripted
test cases; they are not live-model outcomes.

No production-model qualification was attempted by this refresh, and no
seed-extension attempts were launched. These regression results establish
no new model capability or self-improvement success rate. Earlier
qualification history remains as recorded in the v0.5.1 receipts.

## Public receipts

- [Machine-readable summary]({bundle_rel}/results.json): tested commit,
  starter fingerprint, environment, counts, log hashes and evidence scope.
- [SHA-256 manifest]({bundle_rel}/SHA256SUMS): the log(s) and the public
  summary in this bundle.

Only test logs and a minimal summary are included. Raw task conversations,
provider payloads, credentials, host paths and private model-study artifacts
are not copied into this public evidence bundle.

## Run the corresponding suites

Check out the tested commit in a separate directory for a historical replay.
From that checkout, with Python 3.13 available:

```sh
python -X utf8 -m unittest discover -s tests -q
```

For the selected VM suite, first prepare WHPX/KVM and the pinned appliance as
described in the [hardware VM workflow](.github/workflows/vm-checks.yml).
Then, on Windows PowerShell:

```powershell
$env:AUTOPROTEUS_VM_TESTS = '1'
python -X utf8 -m unittest discover -s tests -p test_vm_isolation.py -v
```

On Linux:

```sh
AUTOPROTEUS_VM_TESTS=1 python -X utf8 -m unittest discover -s tests -p test_vm_isolation.py -v
```

To check the evidence hashes on systems with `sha256sum`:

```sh
cd {bundle_rel}
sha256sum -c SHA256SUMS
```
"""


def run_suite(root=ROOT):
    completed = subprocess.run(ORDINARY_COMMAND, cwd=root,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return completed.stdout


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', help='Version to record (default: package __version__)')
    parser.add_argument('--output-dir', help='Bundle directory (default: docs/validation/v<version>)')
    parser.add_argument('--ingest-ordinary', help='Bundle this existing ordinary-suite log instead of running the suite')
    parser.add_argument('--vm-log', help='Also bundle this existing real-VM suite log (never runs the VM suite)')
    parser.add_argument('--update-page', action='store_true',
                        help='Also rewrite VALIDATION.md to describe the new bundle')
    args = parser.parse_args(argv)

    version = args.version or current_version()
    commit = current_commit()
    bundle_dir = Path(args.output_dir) if args.output_dir else ROOT / 'docs' / 'validation' / ('v' + version)
    if bundle_dir.exists():
        parser.error(f'Bundle directory already exists: {bundle_dir}')

    if args.ingest_ordinary:
        ordinary_log = Path(args.ingest_ordinary).read_bytes()
        new_execution = False
    else:
        ordinary_log = run_suite()
        new_execution = True
    ordinary = summarize_unittest_log(ordinary_log.decode('utf-8', errors='replace'))
    vm = vm_log = None
    if args.vm_log:
        vm_log = Path(args.vm_log).read_bytes()
        vm = summarize_unittest_log(vm_log.decode('utf-8', errors='replace'))
    results = build_results(version, commit, ordinary, sha256_bytes(ordinary_log),
                            vm=vm,
                            vm_log_sha=sha256_bytes(vm_log) if vm_log else None,
                            new_execution=new_execution)
    write_bundle(bundle_dir, ordinary_log, results, vm_log=vm_log)
    print(f'Bundled {bundle_dir.relative_to(ROOT)}: ordinary '
          f"{ordinary['discovered']} discovered, {ordinary['passed']} passed, "
          f"{ordinary['skipped']} skipped.")
    if args.update_page:
        recorded = datetime.now(timezone.utc).strftime('%d %B %Y')
        page = render_page(version, commit, recorded, results,
                           bundle_dir.relative_to(ROOT).as_posix())
        (ROOT / 'VALIDATION.md').write_text(page, encoding='utf-8')
        print('VALIDATION.md refreshed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
