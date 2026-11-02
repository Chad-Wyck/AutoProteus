# Development invocation scope — preparation only

## Publication status — November 2, 2026

The sections below preserve the original preparation hold and proposed protocol;
they are historical, not a current prohibition on scripted validation. Later
authorization enabled validation and the separate receipt study, whose partial
results are saved in `.data/development-route-test-20261101-01/final-audit/REPORT.md`.
That study did not demonstrate a benefit; the resource-stopped candidate was not
silently retried. The later context-retention comparison excluded this cue.

The cue remains **opt-in**: `evaluations/development_receipts.py` constructs inert
candidate source with `variant(source)` and a matching guest fixture with
`invoker(text)`. Freeze those outputs explicitly using `--source-pack` and
`--invoke-tool-file`. The normal `seed.py` and default helper retain their original
receipts. New scripted controls check isolation; the opt-in VM test constructs
the candidate explicitly. No new live receipt study is queued by publication.

## Original preparation record

**HARD HOLD: no tests or model work have run for this change.** The user authorized
edits for the next9B test and explicitly withheld test execution. This includes
unit/regression tests, fixture/mock execution, collection, compilation, VM checks,
tokenizer/model loading, inference, benchmarks and training. No automatic queue,
commit or push is prepared. Fresh user approval is required before validation.

## One intervention

Label development-helper receipts with `execution_route=development_helper`,
`scope=invocation_only` and a short factual notice. A helper's `passed` field
describes that invocation; it does not establish independent approval, direct
supplied-tool use or explicit task completion.

The edit covers the canonical `seed.py invoke` and the evaluation fixture copied
to `experience/invoke_tool.py`. It preserves their existing check names, actual
results and exit behavior. It does not suppress calls, execute another action,
force native tool selection, auto-finish, grant activation or add an allowance.
Canonical failure receipts also carry scope; legacy helper failures retain their
existing nonzero exception path. Neither receipt metadata nor stdout is a new
source of grading authority.

**Functional use through a CLI remains valid wherever the existing grader permits
it.** The intervention distinguishes routes; it does not introduce a new direct-
route gate. No grader or acceptance criterion is changed.

The established `You are AutoProteus` system prompt, `GUIDANCE` and `USE_GUIDANCE`
remain unchanged. The unpromoted Proteus personality/guidance addition and all
experimental adapters are excluded. New candidate source changes only `seed.py`;
the guest invoker fixture is frozen separately per arm.

## Evidence and classification

The primary saved baseline case is
`.data/proteus-prompt-20261101-02/02-full-baseline-s1/trials/`:

| Saved case | Task understanding / broken tool | Activation/invocation | Completion / timeout |
|---|---|---|---|
| `qwen35-9b-q6-base_growth_01_sha256_file/attempt-002` | Correct final inventory/audit; second feature and earlier-feature retention independently passed. No broken-tool explanation supported. | Request26 onward exposed both tools with active-use system guidance. Calls34,37,40,42 used `experience/invoke_tool.py`; calls40/42 operated on final inventory. Functional capability use was credited; direct named-tool calls were absent and strict-route success was false. | No explicit completed finish; final use reached the shared600s deadline. |
| `qwen35-9b-q6-base_growth_01_format_json/attempt-001` | No independent behavior conclusion: development exhausted the deadline before grading. | No accepted second activation/final use. | Shared600s development timeout; later feature/regression/retention/use checks were unattempted. |

The development-route preference is observable even though active tools and
existing activation guidance were present. It is not itself a functional-use
failure under the existing grader. **Receipt ambiguity is a hypothesis, not an
established cause.** Existing helper output already says "invocation only";
the proposed difference makes the route/completion distinction explicit inside
the structured receipt at the moment it is returned.

Historical baseline CSV second-extension failures in
`qwen-workflow-lora-2026-10-21-findings.md` illustrate a different category: the
model retained the earlier explicit `limit=2` instead of the final default five.
That is task/default confusion, not evidence that a tool was broken. Those older
versions are background evidence, not current matched controls. Experimental
adapter outcomes are not used as the new baseline.

Classification ledger for the proposal:

- **Task misunderstanding:** historically observed in the CSV default/override
  error. Current SHA final files instead satisfy the requested outputs.
- **Broken tool:** not supported for the current baseline SHA second extension
  (feature/retention checks passed); unassessed for the baseline JSON second
  extension whose independent checks were not launched. Registration or a
  timeout alone does not establish implementation correctness or failure.
- **Activation/invocation:** current SHA activation succeeded and both native
  schemas were present, yet four later helper invocations were observed.
- **Explicit completion:** current SHA final artifacts and functional capability
  use were credited but an explicit completed finish was absent. Receipt success must not
  auto-credit it.
- **Timeout:** distinguish the SHA final-use shared600s expiry from JSON
  development shared600s expiry. The separate120s request failure under the
  unpromoted Proteus candidate is not evidence for this good-baseline hypothesis.
  GPU admission rejections before model load are infrastructure, not model
  failures.

Broken implementation, task misunderstanding, invocation route, explicit finish
and timeout must remain separate in future reporting. The proposed receipt cue
does not fix incomplete implementations, protected-source edits, defaults,
plain-prose finish behavior, history trimming or request-timeout accounting.

## Baseline isolation and harness wiring

Private inert preparation: `.data/development-route-prep-20261101-01/`.

- `baseline/source.json` copies the immutable good baseline from the closed study
  (source identity645d2222c5f7f6e92ad5f2ca964f7584e07b47ea4d410872e98a61009eb7bb0d).
- `candidate/source.json` changes only its `seed.py` bytes.
- `baseline/invoke_tool.py` is the exact historical frozen guest helper text;
  `candidate/invoke_tool.py` is the proposed helper. Both must be supplied
  explicitly when preparing their respective plans.
- `profiles/s1.json`, `profiles/s2.json`, `cases-s1.json`, `cases-s2.json` and
  `fixtures/proposed-controls.json` are data only. No study preparation or run
  command has been invoked. `HOLD.json` records the execution prohibition.
- Pre-edit source/helper and the three pre-existing dirty grader/test files are
  copied with byte hashes under `baseline/`. Original journals/verdicts and all
  previous study directories are untouched; deleted Sol traces are excluded.

`model_study.py prepare --invoke-tool-file` now permits a bounded UTF-8 helper
to be frozen as guest-only source data with its path and exact byte hash.
`model_plan.development_invoker` reads at most65537bytes, rejects empty or
oversized/non-UTF8 input and never imports or executes it. The frozen plan owns
the actual text; later changes to the original file do not alter it.

This avoids accidentally delivering the new helper to both arms just because
the checkout now contains it. Comparison wiring is common to both arms; only
the source/helper receipt intervention differs. No broker capability, credential,
VM isolation, host execution permission or scoring boundary is changed.

## Proposed matched test — not approved to run

Initial scope: one complete baseline/candidate pair at seed104729, same two
SHA-first/JSON-first families, same existing five ordinary prerequisites and
first/second activation gates. At most20owned model cells, including two
transport screens, before gates. Seed112648 and reversed family/arm order are
predeclared for a **separate confirmation pair**, not an automatic extra run.
One seed/two related families will not establish reliability or causation.

Use existing Qwen3.5-9B Q6_K, no adapter; context32768, response4096, batch128,
microbatch64, one slot, automatic GPU offload, q8 KV,2CPUthreads, temperature0.6,
top_p0.8/top_k20, thinking disabled, per-request sampling seeds. Record actual
engine/model hashes and reported allocation; configured seed equality does not
prove deterministic provider behavior. Do not reuse a historical task result
as a fresh control or overwrite an old queue.

Within each pair freeze identical task wording/fixtures, case IDs/order, tools,
graders, native-format instructions and allowances: ordinary240s/8192generated
tokens, extension600s/16384, request120s,64actions and90s startup. The proposed
initial admission window is at most3hours from actual launch, subject to user
approval; an active bounded test drains under its original allowance. A future
reviewed supervisor must enforce ownership/cleanup and the unchanged resource
guards. The generic `model_study run` command alone is **not** a staged replacement
for that supervisor.

Reserve a quiet window without competing model loads, record other workload
intervals, RAM/commit/VRAM/paging, health and actual offload. Preserve existing
4GiB RAM/commit admission,2GiB hard floor, sustained-pressure/health safeguards,
8GiB free-VRAM admission/1GiB running floor, disk safeguards and GPU-utilization
admission policy. If these reject normal desktop activity, report the scheduling
blocker and obtain a separate profile decision; do not relax guards or loop.

Report artifacts, package validity, activation, fresh functional use, direct native
use, explicit completion and full chains separately. Keep first-use CLI credit
where currently allowed, raw statuses, protected-source failures, timeouts,
infrastructure stops and gated/unadmitted cells. No score laundering or auto-
credit from the new `scope`/`execution_route` fields. Existing stdout-forgery
limitations remain disclosed.

Measure receipt/prompt overhead only after approval; no tokenizer was loaded now.
Preserve full journals and actual wire requests. Compare retained-history groups,
trim events, host role/content mismatch observations, actual response allowances,
prompt usage and tool schemas by task/stage. Mark differential history/budgets
as affected cells, not clean isolated prompt estimates. The existing late-
observer/cancellation usage uncertainty is **not fixed here**: four request
records lacked responses in the prior study while budgets reserved only three.
Do not claim exact token cost or speed gains; no repeats solely to improve
comparability. No recovery or training use of excluded Sol material.

## Pending validation commands — DO NOT EXECUTE under this hold

After fresh user approval, from repository root, proposed targeted commands are:

```powershell
& '.runtime/python-3.13.12/python.exe' -X utf8 -m unittest discover -s tests -p test_development_invocation_scope.py -v
& '.runtime/python-3.13.12/python.exe' -X utf8 -m unittest discover -s tests -p test_activation_use.py -v
& '.runtime/python-3.13.12/python.exe' -X utf8 -m unittest discover -s tests -p test_growth.py -v
& '.runtime/python-3.13.12/python.exe' -X utf8 -m unittest discover -s tests -p test_workspace_invocation.py -v
& '.runtime/python-3.13.12/python.exe' -X utf8 -m unittest discover -s tests -q

# Separate opt-in VM validation, only when explicitly approved:
$env:AUTOPROTEUS_VM_TESTS = '1'
& '.runtime/python-3.13.12/python.exe' -X utf8 -m unittest discover -s tests -p test_development_invocation_scope.py -v
Remove-Item Env:AUTOPROTEUS_VM_TESTS
```

New prepared controls cover verbatim/no-execution source freezing, UTF8/size
boundaries, original CLI functional credit, forged-route-field rejection for
direct-use attribution, missing explicit finish, real guest receipt/result
semantics, helper failure and unchanged source. These are **written, not run**.
Existing attribution/forgery controls remain required; they were not executed.

Future preparation command template, also pending fresh approval:

```powershell
# Replace ARM with baseline or candidate; use the matching invoker and source.
& '.runtime/python-3.13.12/python.exe' -X utf8 evaluations/model_study.py prepare `
  --profiles .data/development-route-prep-20261101-01/profiles/s1.json `
  --output .data/development-route-prep-20261101-01/future-ARM-s1 `
  --source-pack .data/development-route-prep-20261101-01/ARM/source.json `
  --invoke-tool-file .data/development-route-prep-20261101-01/ARM/invoke_tool.py `
  --case-pack .data/development-route-prep-20261101-01/cases-s1.json `
  --mode full --repeats 1 --timeout 600 --output-token-budget 16384 `
  --activation-reminder --sampling-seed-mode per-request
```

Even preparation/`--check-only`, syntax/compile checks and offline fixtures are
not authorized now. No live launcher/scheduler is created. Root owns follow-
through after approval: review/repair pending validations, freeze both arms and
resource supervision, and only then propose/execute the approved finite scope.
