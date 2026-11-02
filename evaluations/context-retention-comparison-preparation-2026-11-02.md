# Opt-in context retention: prepared, no live tests started

The candidate uses provider-reported prompt usage at **both** history-selection
boundaries. The normal seed, application settings, concise activation handoff,
tool catalog, response formats, verification rules and resource limits are not
changed by selecting this research experiment. No model, tokenizer or VM was
loaded during preparation. No background runner or monitor is queued.

## The intervention

`--experiment context-retention` freezes two inert source variants and chooses
the matching protected client separately for each feature trial:

- **Baseline:** established source
  `645d2222c5f7f6e92ad5f2ca964f7584e07b47ea4d410872e98a61009eb7bb0d`,
  with the existing conservative two-byte estimate at both boundaries.
- **Candidate:** the same source, changing only estimation wiring in
  `autoproteus/agent.py` and adding a shared `autoproteus/context_retention.py`.
  The host uses `RetentionModelClient` only for that explicitly selected arm.
  The model receives no new instructions or tools.

Both arms explicitly freeze the original development helper and baseline
`seed.py`, excluding the unpromoted receipt-scope cue and all adapters. These
sources are separate from the current working checkout. Common trusted grader
and cancellation-accounting changes apply to both arms.

The shared estimator retains an observed prompt-token anchor only while system
text, tool definitions, provider/model/connection settings, response allowance
and source binding match. The anchored history prefix must match exactly.
Newly appended messages are priced at the old conservative byte rate plus a
256-token margin. Missing, invalid or mismatched usage falls back to the current
estimate. This remains an estimator, not a mathematical tokenizer bound.

Changing trailing todo/runtime metadata would otherwise break every append-only
anchor. The helper excludes only those known optional tail entries from prefix
matching. Their old cost stays inside the observed anchor and the current tail
is charged again. It never subtracts old content, removes instructions, adds a
summary or changes the actual request. Rewritten history elsewhere uses fallback.

The host anchors the **actual accepted native wire**. Its response includes a
request-identity receipt. The guest uses that usage only if the receipt matches
its exact role/content request and no host wire trimming occurred. A concise
handoff or host-added activation notice can change that identity; the larger
guest view then falls back rather than borrowing the smaller prompt's usage.
The existing concise handoff stays fixed for both arms, so this experiment
does not independently test activation-history placement.

Each host transport uses a private estimator snapshot. Cancellation invalidates
the caller's anchor; a detached late worker cannot overwrite the next call's
accepted wire or anchor. The existing token reservations and byte/message limits
still apply. The host records `context_estimate` events, and guest model-response
journals retain the exact-request usage receipt. No receipt confers task approval.

Qualification is intentionally limited to local native chat transport. The
estimator's shared logic uses generic provider usage fields; effectiveness and
compatibility with other models/backends are not established. No Responses or
JSON-protocol treatment is silently substituted.

## Frozen matched comparison

Private folder: `.data/context-retention-prep-20261102/`.

| Setting | Both arms |
| --- | --- |
| Model | Existing Qwen3.5 9B Q6_K, no adapter |
| Context / response | 32,768 / 4,096 tokens |
| Sampling | Temperature 0.6, top_p 0.8, top_k 20, thinking off |
| Request seeds | 104729 and 112648, paired; determinism not assumed |
| Runtime | Existing pinned llama-server; one slot, automatic GPU offload |
| Batch / microbatch / CPU threads | 128 / 64 / 2 |
| KV cache | q8_0 |
| Actions / request timeout | 64 / 120 seconds |
| Feature-stage allowance | 600 shared seconds and 16,384 generated tokens |
| Ordinary-task allowance | 240 seconds and 8,192 generated tokens |
| Activation | Same verbatim final-task reminder and concise handoff |
| Corrections | No public feedback or human candidate repairs |

Test two families, **hashing then formatting** and **formatting then hashing**,
at both seeds. Each family/seed has baseline and candidate first extensions,
fresh first use, then a second extension and cumulative use if eligible.
There are **eight scheduled first-extension chains** and at most **sixteen
feature stages**. The common baseline transport screen and five ordinary tasks
add six cells, for at most **22 owned model cells**. The ordinary prerequisites
are shared baseline admission checks, not candidate ordinary-task qualification.

Arm order is explicitly frozen per feature and reversed at the second seed,
independently of rotating family order. Tasks, fixture IDs, contracts, schemas,
hidden checks and budgets match within every pair. Both variants preserve all
common protected seed tests. Failed ordinary admission leaves the extension
cells untested. A second extension requires an accepted first package **and**
successful fresh first use; failed first use does not trigger extra diagnostics.

The feature-task ceilings alone total at most 2 hours 40 minutes, plus ordinary
checks, startup and scripted calibration. This is a ceiling calculation, not an
ETA or permission to extend the task limits. No total live window has been
authorized. Fresh owned runtimes and actual context/empty-adapter attestations
are required; no running app service is reused or stopped by preparation.

## Qualification and launch hold

`study/plan.json`, `plan.sha256` and the trusted-runner snapshot are frozen.
`HOLD.json` explicitly records that live execution is not authorized. There is
no queue or launch receipt. Preparation reads pinned local assets but does not
contact an inference endpoint, query a tokenizer, start an engine or recover
session stores. Old studies and their verdicts remain unchanged.

Before future live execution, obtain the user's go-ahead, run both variants'
scripted VM/input calibration, qualify the actual metadata/usage receipt path,
and review the resource-owning supervisor. Keep the previous 4-GiB RAM/commit
admission, 2-GiB hard floors and sustained pressure guard. GPU admission remains
8 GiB free VRAM with at most 15% background utilization, plus the 1-GiB running
free-VRAM floor; these extra GPU checks require the reviewed outer supervisor,
not just a bare `model_study run`. No guard relaxation, automatic retry, extra
seed or test-window extension is prepared.

Report accepted first packages, first use, second packages, retained capability,
cumulative use, native route and explicit finish separately. Preserve all
failed, resource-stopped and skipped denominators. Compare cost only on matched
verified successes, keeping measured tokens, reservations and incomplete usage
distinct. Record anchor/fallback selection, both history boundaries, handoff,
reported prompt usage and actual source/schema identities. Extra retained
context can increase prefill cost; no speed or effectiveness benefit is assumed.

## Offline controls

Controls cover first-call parity with production transport, generic usage and
scope invalidation, exact-request receipts, wire-trim/handoff rejection, changing
optional metadata, preserved human corrections/activation state, intact recent
tool pairs, greater synthetic-history retention, cancelled-worker isolation,
inert variant construction, frozen pair order and first-use gating. Mock provider
usage tests mechanisms, not Qwen capability. Real VM and model qualification
remain pending under the launch hold.

Final ordinary validation: **605 tests ran: 536 passed and 69 skipped**, with VM
opt-in disabled. Eleven new retention controls passed. An earlier run retained
the old generic test expectation that every new treatment used
`workflow_support.py`; its failure is preserved, the assertion now recognizes
this treatment's separate helper, and the complete final suite passed.
The final log is `.data/context-retention-prep-20261102/regression-final.log`.

The frozen plan identity is
`41552a6cd4b8a49aafc3d29b95380cd4ea78104d0d3cb4e9b56e9dcb169e790d`.
The candidate source identity is
`4e18702388e2b10c9fdb1d5a14f511a1ced3f96e1ebea95a3cf477473dd92f3a`.
Its source-pack size increases by 4,387 bytes, including the shared helper and
agent wiring. These are prepared-source identities, not model qualification.
At preparation completion, all changes remained local and no commit or push had
been made. The subsequent authorized comparison is closed; see
[the findings](context-retention-qwen9b-2026-11-02-findings.md). Publication preserves
the opt-in variant and historical source identities without promoting it.
