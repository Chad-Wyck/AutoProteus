# Recorded validation

These are maintainer-recorded local test results for **v0.5.1**, tested commit
[`70a98697e4facb8a120142623439874e97fc28ac`](https://github.com/Chad-Wyck/AutoProteus/commit/70a98697e4facb8a120142623439874e97fc28ac),
recorded on **23 October 2026**. They describe that revision, not later local
harness changes, every supported platform, or the latest branch automatically.

The existing logs were copied byte for byte and checked against SHA-256 values
in the original preflight receipt. Preparing this page did not rerun tests or
start inference. This is published historical evidence, not a new CI run or an
independent security audit.

## Results

Environment: Windows 11 x86-64, Python 3.13.12, disposable Linux guests under
QEMU/WHPX.

| Suite | Discovered | Passed | Failed/errors | Skipped | Seconds | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Ordinary regressions | 323 | 277 | 0 | 46 | 42.344 | [Unmodified log](docs/validation/v0.5.1/ordinary-tests.log) |
| Selected real-VM suite | 23 | 23 | 0 | 0 | 219.997 | [Unmodified log](docs/validation/v0.5.1/real-vm-tests.log) |

The VM invocation selected `test_vm_isolation.py`; it was not every opt-in VM
test in the repository. VM cases skipped by the ordinary invocation are not
counted as ordinary passes. These are two suite invocations, not 346 distinct
passing tests. Read the named cases in the logs for the exact coverage.
Lines named `fixture` and their trial messages exercise scripted test cases;
they are not live-model outcomes.

The selected VM cases cover host-file and network denial, broker credentials,
malformed exports, damaged inputs, deadlines, Stop/recovery, checkpoints,
activation, tool invocation and functional grading. Passing these cases is
functional evidence for those checks; it does not establish immunity to
hypervisor or host vulnerabilities. The [security boundary](SECURITY.md)
describes the threat model and remaining limits.

Separate production-model qualification failed twice in this preflight. All
six planned seed-extension attempts remained unlaunched. These regression
results establish no new model capability or self-improvement success rate.

## Public receipts

- [Machine-readable summary](docs/validation/v0.5.1/results.json): tested commit,
  starter fingerprint, environment, counts, log hashes and evidence scope.
- [SHA-256 manifest](docs/validation/v0.5.1/SHA256SUMS): the two original logs
  and the public summary.
- [VM test source at the tested commit](https://github.com/Chad-Wyck/AutoProteus/blob/70a98697e4facb8a120142623439874e97fc28ac/tests/test_vm_isolation.py).

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

These commands select the corresponding suites; results, skips and timings may
differ by platform and configuration. Scripted regression suites do not call a
live model. The hardware lane is separate from ordinary hosted CI and should
run only reviewed revisions on a prepared runner.

To check the evidence hashes on systems with `sha256sum`:

```sh
cd docs/validation/v0.5.1
sha256sum -c SHA256SUMS
```
