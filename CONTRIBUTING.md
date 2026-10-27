# Contributing to AutoProteus

AutoProteus is an experimental research project: a seed agent that works inside
a disposable VM and can extend an editable copy of its own harness, while a
protected controller owns credentials, policy and recovery. Contributions are
welcome, and they are reviewed against one standard above all others:
**evidence**. Claims in this repository are expected to arrive with the
receipts that support them — test counts, logs, and an honest statement of
what was *not* run.

Please read [SECURITY.md](SECURITY.md) before proposing anything that touches
isolation, the broker, or model connections. The security boundary described
there is the project's spine; changes that weaken it need a security
discussion first, not just a patch.

## Before you start

- Open an issue before large changes. Small, focused pull requests are far
  easier to review than bundled ones, and the maintainer can tell you early
  whether a direction fits the roadmap.
- App-specific integrations are deliberately kept outside the core for now.
  An extension library is planned sometime after the v1 release; until then,
  expect integrations to be redirected there rather than merged into core.
- One change per pull request. Unrelated fixes belong in separate PRs.

## Setup

You need Python 3.13 (CI uses 3.13; the test suite is the project's own
regression harness — there is nothing else to install, because the codebase
depends only on the Python standard library).

```sh
git clone https://github.com/Chad-Wyck/AutoProteus
cd AutoProteus
python -X utf8 -m unittest discover -s tests -q
```

A healthy checkout reports every discovered test passing, with skips only
for cases that need a real VM (QEMU/KVM or WHPX) or a live model. **Skips are
not passes** — report them as skips.

## House rules

These are not style preferences; they are load-bearing properties of the
project. Pull requests that break them will be asked to change.

1. **Standard library only.** No third-party dependencies, vendored or
   otherwise. If a change seems to need one, open an issue and make the case.
2. **Fail closed.** Unknown operations, malformed input, and integrity
   failures end the run; they never fall through to a permissive default.
   New parsers, transports and checks must reject what they do not
   explicitly understand.
3. **The controller is trusted; everything the model produces is not.**
   Guest or candidate code is never imported or executed on the host.
   The evaluator may materialize exported bytes for content checks only.
4. **No secrets in files.** Provider keys belong in the
   `AUTOPROTEUS_API_KEY` environment variable — never in plans, profiles,
   fixtures, logs or evidence bundles. Check your diff for keys, host paths
   and private artifacts before submitting.
5. **Honest evidence.** Report the exact suite you ran, on the exact commit,
   with counts. Do not describe scripted/fixture results as live-model
   outcomes, preparation as a trial, or a partial suite as the full suite.
   Negative and inconclusive results are valuable and are recorded as-is.
6. **Keep the trusted core small.** `autoproteus/`, `controller/` and
   `guest/` change deliberately and with tests. Research machinery belongs
   in `evaluations/`; it must not leak into the trusted path.

## Scope map

| Area | What it is | Notes |
| --- | --- | --- |
| `autoproteus/` | The editable seed core the agent can extend | Highest review bar; every change needs regression evidence |
| `controller/` | Protected host: isolation, broker, providers, evaluation | Security-sensitive; see [SECURITY.md](SECURITY.md) |
| `guest/` | The worker that runs inside the VM | Treated as hostile-adjacent; never trust its claims on the host |
| `web/` | Browser UI served by the controller | Only trusted host assets are served |
| `evaluations/` | Study runners, graders, frozen plans and research reports | Preparation and calibration start no live-model trials |
| `tests/` | The ordinary regression suite | New behavior in core areas needs new tests here |
| `examples/` | Worked examples | Must stay runnable against the current seed |

## Running the suites

Ordinary regressions (the suite every PR must run):

```sh
python -X utf8 -m unittest discover -s tests -q
```

Selected real-VM suite (only on a prepared KVM/WHPX machine, as described in
[.github/workflows/vm-checks.yml](.github/workflows/vm-checks.yml)):

```sh
AUTOPROTEUS_VM_TESTS=1 python -X utf8 -m unittest discover -s tests -p test_vm_isolation.py -v
```

Study machinery under `evaluations/` follows its own documented discipline
(prepare → calibrate → run, check-only before any inference). Do not start
live-model trials as part of a code contribution unless the PR is explicitly
about a study, with its budget and protocol declared up front.

## What to attach to a pull request

The PR template asks for this; filling it in completely is the fastest path
to a review:

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

Use the issue templates. For bugs, a minimal reproduction plus the suite
counts from *your* checkout (see above) matters more than a long narrative.
For features, describe the problem before the solution, name the scope area
from the map above, and say what evidence would show the change works.

## Conduct of review

Review may take time — this is a small project. Expect questions about
evidence before questions about style. If a PR is closed without merging,
that is a statement about fit and timing, not about the contributor; the
usual door left open is the future extension library.
