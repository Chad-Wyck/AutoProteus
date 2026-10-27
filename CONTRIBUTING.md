# Contributing to AutoProteus

AutoProteus is a small, model-agnostic seed that agents can extend when a task
needs new tools. Keep the seed simple enough for small local models to inspect
and change. A separate protected controller owns credentials, policy and recovery.

Contributions should support that goal. Evidence helps us judge a change:
report relevant checks, their results, and what was not run. Passing tests
alone does not justify unnecessary complexity in the seed.

Please read [SECURITY.md](SECURITY.md) before proposing anything that touches
isolation, the broker, or model connections. The security boundary described
there defines which components are trusted. Discuss changes to that boundary
before implementing them.

## Before you start

- Open an issue before large changes. Small, focused pull requests are far
  easier to review than bundled ones, and the maintainer can tell you early
  whether a direction fits the roadmap.
- App-specific integrations are deliberately kept outside the core for now.
  An extension library is planned sometime after the v1 release; until then,
  expect integrations to be redirected there rather than merged into core.
- One change per pull request. Unrelated fixes belong in separate PRs.

## Setup

Use Python 3.13 to match CI. The ordinary regression suite uses the Python
standard library. Real-VM checks also need the prepared environment described
below. Bug reports and documentation-only contributions do not require a full
development setup.

```sh
git clone https://github.com/Chad-Wyck/AutoProteus
cd AutoProteus
python -X utf8 -m unittest discover -s tests -q
```

A healthy checkout reports no failures or errors. Some tests are skipped
because of platform differences or because they need a prepared VM or live
service. **Skips are not passes** — report them separately.

## House rules

Use these principles to keep contributions consistent with the project's
architecture and goals.

1. **Standard library only.** No third-party dependencies, vendored or
   otherwise. If a change seems to need one, open an issue and make the case.
2. **Protect the host boundary.** Reject unauthorized broker operations,
   malformed boundary requests and integrity failures without granting extra
   access. Preserve bounded recovery for ordinary tool errors and malformed
   model replies; a failed action does not always need to end the task.
3. **Keep the trust boundary clear.** In VM mode, guest or candidate code
   is never imported or executed on the host. The evaluator may materialize
   exported bytes for content checks only. Explicit native mode has different
   guarantees and requires the external protection described in SECURITY.md.
4. **Keep secrets out of source and evidence.** Use the application's
   supported protected credential storage or `AUTOPROTEUS_API_KEY`. Never
   include keys in plans, profiles, fixtures, logs or evidence bundles.
   Redact private host paths and task data before publishing.
5. **Honest evidence.** Report the exact suite you ran, on the exact commit,
   with counts. Do not describe scripted/fixture results as live-model
   outcomes, preparation as a trial, or a partial suite as the full suite.
   Negative and inconclusive results are valuable and are recorded as-is.
6. **Keep the seed and controller small.** `autoproteus/` is the editable
   seed, not trusted host code. `controller/` owns host policy; `guest/`
   supplies the worker inside the VM. Keep optional research in
   `evaluations/` and explain any new seed code or instruction burden.

## Scope map

| Area | What it is | Notes |
| --- | --- | --- |
| `autoproteus/` | The editable seed core the agent can extend | Keep it simple for small models; behavior changes need regression evidence |
| `controller/` | Protected host: isolation, broker, providers, evaluation | Security-sensitive; see [SECURITY.md](SECURITY.md) |
| `guest/` | The worker that runs inside the VM | Its claims are untrusted at the host boundary |
| `web/` | Browser UI served by the controller | Only trusted host assets are served |
| `evaluations/` | Study runners, graders, frozen plans and research reports | Preparation and calibration start no live-model trials |
| `tests/` | The ordinary regression suite | New behavior in core areas needs new tests here |
| `examples/` | Worked examples | Must stay runnable against the current seed |

## Running the suites

Run ordinary regressions for code changes. For documentation-only changes,
check affected links and commands, and state which suites were not run:

```sh
python -X utf8 -m unittest discover -s tests -q
```

Selected real-VM suite (only on a prepared KVM/WHPX machine, as described in
[.github/workflows/vm-checks.yml](.github/workflows/vm-checks.yml)):

On Linux:

```sh
AUTOPROTEUS_VM_TESTS=1 python -X utf8 -m unittest discover -s tests -p test_vm_isolation.py -v
```

On Windows PowerShell:

```powershell
$env:AUTOPROTEUS_VM_TESTS = '1'
python -X utf8 -m unittest discover -s tests -p test_vm_isolation.py -v
```

Study machinery under `evaluations/` follows its own documented discipline
(prepare → calibrate → run, check-only before any inference). Do not start
live-model trials as part of a code contribution unless the PR is explicitly
about a study, with its budget and protocol declared up front.

## What to attach to a pull request

Keep evidence proportional to the change. For documentation-only work, describe
the links or instructions checked and state which suites were run or omitted.
For code changes, include:

- **The exact commit** your results come from, and the platform and Python
  version you ran on.
- **Suite counts:** discovered / passed / failed / errors / skipped, and the
  wall-clock seconds — for the ordinary suite, and separately for any VM or
  study runs.
- **What you did not run**, and why (no VM host, no model, platform limits).
  An honest gap beats a silent one.
- For behavior changes: the new tests that pin the behavior, and the failing
  output they produced before your change, if applicable.
- For anything touching isolation, the broker, providers or file handling:
  a short security note on what the change does to the boundary in
  [SECURITY.md](SECURITY.md).

## Reporting bugs and proposing features

Use the issue templates. For bugs, include a minimal reproduction, your app
version and operating system, and relevant error text. Suite counts are
optional; you do not need a development setup to report a problem.
For features, describe the problem before the solution, name the scope area
from the map above, and say what evidence would show the change works.

## Conduct of review

Review may take time — this is a small project. Expect questions about fit,
simplicity and evidence. A PR may be closed because of its scope, correctness
or timing. Focused follow-up proposals are welcome.
