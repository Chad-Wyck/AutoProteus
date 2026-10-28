# Fixed repeatability and outcome-choice studies

These opt-in studies run outside the editable seed. Preparation and `--check-only`
use no live model. Run on the faster test machine when ready; no downloaded
checkpoint or frozen Windows plan is required from the original PC.

## Prepare the machine and one profile

Use the [local model handoff](local-model-test-handoff.md) for launcher-installed
Python, the VM appliance, endpoint setup and profile fields. Copy
`model-test-profile.example.json` to root `profiles.json`, then enter the exact
model ID and endpoint. Its 9B research starting settings are 128K context, 4K
responses, temperature .6 and terminal access. These are research settings, not
a claim that the everyday default profile is qualified.

For comparison with the GTX 1080 Ti results, use the same Qwen3.5 9B Q6_K weights,
model revision, runtime version, thinking mode and sampling/KV settings. Record
the checkpoint SHA-256, engine command, top-p/top-k, penalties, cache policy,
offload, GPU/VRAM/RAM and OS. Keep the service unchanged during a frozen run.
The hosted adapter cannot verify all engine settings from a model alias. Record
requested versus independently verified settings. Compare complete successful
tasks first, then calls, measured tokens and time; preserve partial measurements.

By default, fixed-case studies request a seed on **each model call**. This is a different sampling
protocol from earlier private runs that initialized a fresh server RNG once per
attempt. The optional field maps to Ollama `options.seed` or the compatible chat
API's `seed`. Normal app requests omit it unless explicitly supplied. See the
[Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md) and
[llama.cpp server reference](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md).
An endpoint may reject or ignore it; support and deterministic output are not
assumed. An endpoint that rejects seeded requests fails the preflight; this runner
does not silently drop the field. An endpoint that ignores it may remain undetectable.
Check recorded provider payloads and engine evidence. Seed control
does not control cache warmth or guarantee identical hardware trajectories.
An unseeded ordinary `--mode full` study remains available for incompatible
endpoints; label its sampling separately from this seeded case pack.

`--sampling-seed-mode server-initialized` instead **omits the request seed** and
records the scheduled seed as `server_initial_seed`. It does not start, restart,
or seed the external service. The runtime owner must initialize a fresh service
with that seed before **each attempt**, preserve its command/configuration and
restart evidence, and avoid unrelated calls consuming the RNG stream. A plain
long-lived endpoint is not a controlled server-initialized comparison. The runner
labels server initialization unverified; matching declarations alone are not proof.
Both native API transports are checked for omission of request seeds in this mode.

Prepare separate environment-bound plans on each host. Compare Git revision,
source fingerprint, profile and `repeatability.portable_case_sha256`; do not copy
an old plan and change its environment fields. Different models/configurations
need separate, explicitly labelled comparisons.

## 1. Repeat two fixed growth workflows

The committed `repeatability-cases.json` selects formatting→hashing and
CSV→hashing, with three predeclared seeds. **The same user wording and fixture
bytes recur across repeats.** Fresh workspaces prevent stale-file reuse. Both
first activation/use and second extension/use are independently scored. Invalid
parents cannot grow; first-use failures permit labelled diagnostics only.

This schedules six first attempts and up to six second attempts, plus ordinary
and inference checks. Each edit/use task shares 128 actions, 3,600 seconds and
65,536 generated tokens. These are ceilings, not time estimates. Do not extend
an allowance or repair a candidate mid-comparison.

Choose the platform's Python once:

```powershell
# Windows PowerShell, after launcher setup
$testPin = Get-Content .\controller\managed-runtime-lock.json -Raw | ConvertFrom-Json
$testPython = Join-Path (Get-Location).Path ".runtime\python-$($testPin.python_windows.version)\python.exe"
```

```sh
# Linux shell, after launcher setup
test_python=.runtime/python-linux/bin/python3
```

Then prepare, calibrate, and only later start inference. In PowerShell replace
`python` below with `& $testPython`; in Linux replace it with `"$test_python"`.
Run the next command only if the previous one succeeds.

```text
python -X utf8 evaluations/model_study.py prepare --profiles profiles.json --output .data/fixed-growth --mode full --case-pack evaluations/repeatability-cases.json --timeout 3600 --output-token-budget 65536
python -X utf8 evaluations/model_study.py run --input .data/fixed-growth --check-only
python -X utf8 evaluations/model_study.py run --input .data/fixed-growth
```

The case pack fixes the repeat count; a conflicting `--repeats` is rejected.
Provider traces and per-attempt results record the requested sampling seed.
Actual tool actions and finishing remain subject to the same protected limits.

### Focused sampling comparison, prepared for later

Use `sampling-csv-cases.json` for three paired CSV trials (six first attempts,
plus qualification/basic checks), with first activation/use but no second
extension. Keep the same frozen source, model, settings and resource limits in
both plans. Prepare the following two plans; **do not run them while the PC is
busy with another workload**:

```text
python -X utf8 evaluations/model_study.py prepare --profiles profiles.json --output .data/csv-per-request --mode full --first-only --case-pack evaluations/sampling-csv-cases.json --sampling-seed-mode per-request --timeout 3600 --output-token-budget 65536
python -X utf8 evaluations/model_study.py prepare --profiles profiles.json --output .data/csv-server-initialized --mode full --first-only --case-pack evaluations/sampling-csv-cases.json --sampling-seed-mode server-initialized --timeout 3600 --output-token-budget 65536
```

Use the [optional owned-runtime profile](model-study.md#optional-owned-inference-service)
to arrange fresh services with startup/seed receipts, or retain an external
runtime owner with equivalent evidence. The generic runner groups an arm's work;
it does not interleave separate queues. Alternate arm order across matched seeds
as specified by the comparison schedule. Do not run two whole queues sequentially
and describe them as counterbalanced.

Portable case hashes include the sampling mode and therefore differ across
these arms; compare the frozen contracts, fixtures, seed schedule and budgets
directly as well. This tests sampling policy on the current seed, not a regression
against an older seed. No effectiveness result follows from preparation.

### Read the results in stages

`study_report.py` reads only closed exports and does not recover sessions:

```text
python -X utf8 evaluations/study_report.py --input .data/csv-per-request --output .data/csv-per-request-report
```

Its basic-task table separates checked artifacts/behavior, explicit completion,
and strict task passes. Extension acceptance, actual use and complete chains
remain separate. Not-run cells retain their gate reason and are **untested**;
missing observations are unmeasured. A prose completion reply does not become
verified completion, and correct files do not establish that a new tool was used.
Historical results are read without changing their verdicts.

### Isolate edit-result feedback from finishing guidance

Freeze the previous Git seed, the two independent interventions, and their
combined source without starting any service:

```text
python -X utf8 evaluations/seed_comparison.py --output .data/pretest-comparisons --baseline-ref c2c7d13501b165130bcc13994ba0be0344cb58a1
python -X utf8 evaluations/seed_comparison.py --output .data/pretest-comparisons --check-only
```

This produces source packs, native-format instruction files and a hashed
preparation manifest. It rejects unrelated seed differences and preserves the
same starter checks in every arm. Line endings are aligned to the current files
and that normalization is recorded. A version-only release metadata change is
also aligned across arms and recorded alongside the original Git source hash;
unrelated code changes are rejected. These are inert bundles, not calibrated or
executable study plans. Fix the model/runtime/context settings before execution.

- **Finishing:** baseline versus `finish-only`, initially the first paired seed
  on five basic tasks (10 tasks). The treatment changes the seed/tool wording
  and host native instructions; it adds no reminder after a failed attempt.
- **Unchanged edits:** baseline versus `edit-result-only`, three paired CSV
  first-extension/use trials (six first attempts). Only `file_ops.py` changes.
  Both arms use the baseline finishing wording and the same sampling policy.
- **Combined:** retained for subsequent qualification, not included in those
  isolated comparisons. Do not add its attempts to either treatment's score.

The manifest records per-task paired order; extra finishing repeats require a
separate repeatability decision. For environment-bound preparation, the normal
runner accepts `--source-pack` and `--native-instructions-file`. For example:

```text
python -X utf8 evaluations/model_study.py prepare --profiles profiles.json --output .data/finishing-baseline --mode basic --repeats 1 --source-pack .data/pretest-comparisons/baseline-source.json --native-instructions-file .data/pretest-comparisons/baseline-native.txt
```

Prepare the matching treatment with its own files and new output directory.
Use `--mode full --first-only --case-pack evaluations/sampling-csv-cases.json`
for the CSV arms. Do not combine the sampling-policy study with this intervention
study: keep per-request policy, seeds and initial runtime settings matched.
Separate whole-arm runs are labelled exploratory, not balanced interleaving.
The first basic screen uses profile seed 104729; later finishing pairs use the
manifest's seeds through separately prepared profiles/plans. The per-request
seed and per-attempt startup receipts make the actual execution auditable.

Common controller code is current in all arms except the explicitly frozen
native instructions. Live checks still use protected guests. Read source bundles
as data; never import candidate modules into the host to inspect a catalog.

## 2. Outcome-only choice and later reuse

This uses `outcome-choice-v1`, a separate scoring protocol from named-feature
`activation-use-v2` qualification and its first-use reassessment tool.

This separate study gives four practical goals: an exact copy, a JSON settings
copy, a multi-file CSV index and JSONL log summaries with malformed-record reports.
Each has a later batch with different paths **and bytes**, delivered in a fresh
session using the last checked source. Prompts prescribe output requirements,
not tool names, source edits or an extension recipe. No extension is required.
All cases are starter-solvable; simple/repeated-processing labels are opportunities,
not an assertion that a permanent tool is necessary.

```text
python -X utf8 evaluations/model_study.py prepare --profiles profiles.json --output .data/outcome-choice --mode outcomes --repeats 1 --timeout 3600 --output-token-budget 65536
python -X utf8 evaluations/model_study.py run --input .data/outcome-choice --check-only
python -X utf8 evaluations/model_study.py run --input .data/outcome-choice
```

One repeat schedules four first tasks and four later tasks, after a protocol
preflight. Each task gets the declared shared allowance, including any checking
and activation. Another repeat uses a different predeclared per-request seed.

Correct artifacts, preserved inputs, explicit completion and allowances determine
task success. A no-edit solution receives full task credit. Record source edits,
temporary scripts, package checks, activation and observed reuse separately.
Completed first tasks can leave a checked extension for the later session even
if they needed no activation to finish. Invalid edits are never adopted; later
tasks use the last checked source. No hidden answers or repair coaching are sent
back to the model.

Chosen extensions face the published submission scope, preserved tests, a full
candidate suite, protected regressions and catalog checks in separate VMs.
That is **package checking, not independent qualification of every arbitrary new
feature**. Actual task outcomes and later use supply separate evidence. Feature
semantics and the necessity/optimality of extending remain unmeasured. Dynamic
calling routes outside the bounded observer can remain unobserved.

The later task is a fresh session: source capabilities carry across, while old
scratch scripts, fixtures and conversation do not. This specifically measures
seed reuse, not persistent-workspace script reuse. A successful later diagnostic
does not erase a first-task failure. Use this runner's `summary.json` and
`outcome-results.json`; ordinary named-feature upgrade reports do not apply.
The summary separates scheduled/attempted work from recorded outcomes. A failed
preflight leaves task passes null (unmeasured), rather than reporting zero successes
as tested failures. Provider failures remain labelled separately in case records.

## Resources and handoff

v0.14.1 idle VM caches yield to foreground evaluation work. The model remains
loaded. An adopted active VM is never preempted; retained idle sessions can be
restored from their committed files after yielding. Background warm-up cannot
reclaim an occupied slot. Old in-memory controllers need a restart after upgrade.
Avoid simultaneous workloads for interpretable speed measurements.

Return the Git revision, profile/engine evidence, plan/checksum, calibration,
summary, queue and trials, including all failures and interruptions. Completed
work is retained. Explicit `--retry CELL_ID` preserves the original attempt;
never silently rerun a poor result. Prepare fresh plans after source/grader changes.

## Preparation validation

v0.14.1 was checked with 416 passing ordinary tests (62 platform/opt-in skips)
and four scripted Windows/WHPX integration checks: unassigned-cache yielding,
retained-checkpoint recovery after yielding, arbitrary-tool activation and later
reuse, and normal prewarming/reuse. Process-lock tests also check that adopted
active work is not preempted, requests expire cleanly, and warm-up can be cancelled.
This is software validation, not model capability evidence. No local weights
were loaded for this preparation. Linux/KVM integration needs a Linux test host.
