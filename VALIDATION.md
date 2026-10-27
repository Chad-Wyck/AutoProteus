# Recorded validation

These are maintainer-recorded local test results for **v0.14.1**, tested commit
[`171dd399f2c052288424c8a5015d10501a9a1edb`](https://github.com/Chad-Wyck/AutoProteus/commit/171dd399f2c052288424c8a5015d10501a9a1edb),
recorded on **27 October 2026**. They describe that revision, not later local
harness changes, every supported platform, or the latest branch automatically.

This page and its bundle were produced by `evaluations/refresh-validation.py`.
Preparing it ran the ordinary suite below;
it did not start model inference. This is published recorded evidence, not a
CI run or an independent security audit.

## Results

Environment: Linux-7.0.0-39-generic-x86_64-with-glibc2.39, Python 3.12.3, VM backend: not re-run in this refresh.

| Suite | Discovered | Passed | Failed/errors | Skipped | Seconds | Evidence |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| Ordinary regressions | 487 | 438 | 0 | 49 | 129.159 | [Unmodified log](docs/validation/v0.14.1/ordinary-tests.log) |

The real-VM suite was not re-run for this refresh; it remains a
documented step on a prepared KVM/WHPX machine. The most recent VM
receipts remain the v0.5.1 bundle under `docs/validation/v0.5.1/`.

VM cases skipped by the ordinary invocation are not counted as ordinary
passes. Lines named `fixture` and their trial messages exercise scripted
test cases; they are not live-model outcomes.

No production-model qualification was attempted by this refresh, and no
seed-extension attempts were launched. These regression results establish
no new model capability or self-improvement success rate. Earlier
qualification history remains as recorded in the v0.5.1 receipts.

## Public receipts

- [Machine-readable summary](docs/validation/v0.14.1/results.json): tested commit,
  starter fingerprint, environment, counts, log hashes and evidence scope.
- [SHA-256 manifest](docs/validation/v0.14.1/SHA256SUMS): the log(s) and the public
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
cd docs/validation/v0.14.1
sha256sum -c SHA256SUMS
```
