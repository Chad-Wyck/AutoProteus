# v0.0.17: native context budgeting and deferred phase comparisons

Historical preparation record. [v0.1.0](seed-v0.1.0-preparation.md) supersedes
these plans and fixes incomplete calibration identity, grading deadline
propagation and human provenance recovery across the actual broker path. The
receipts below record the checks performed then, not qualification of the
corrected workflow or a live-model improvement.

The host now checks the actual provider messages and, only when they exceed the
configured estimate, removes the oldest complete native tool exchanges until
the request fits. It keeps system/user messages, tool schemas and the newest
complete exchange. Remaining call IDs stay unchanged. An irreducible request
still fails before transport; context limits, action limits and request quotas
are unchanged. JSON fallback retains its existing budgeting behavior.

This is a transport correction in the protected controller. The editable seed
keeps its existing interface, prompt, reading tools and neutral-history budget.
The host does not import edited seed code to estimate context. The complete
journal stays on disk; optional call traces record `context_trimmed`, and a
successful response includes its adjustment receipt. Admissible requests keep
their existing provider messages.

The opt-in usage-anchor client now anchors reported usage to the actual
shortened provider input. Anchoring against the longer neutral transcript would
misattribute the measurement. This remains an experiment, not a default change.

## Evidence without live inference

[Saved-request replay](seed-v0.0.17-context-replay.json) reproduces both v0.0.16
context rejections, then prepares admissible requests with the corrected host:

| Saved request | Original wire bytes | Allowance | Prepared wire bytes | Old exchanges removed |
| --- | ---: | ---: | ---: | ---: |
| Qwen3.5 4B CSV | 254,066 | 253,696 | 247,010 | 1 |
| OxCoder 9B CSV | 257,834 | 253,696 | 247,332 | 1 |

These are offline data replays: zero model calls and no candidate execution.
System/user messages and the newest exchange are preserved byte for byte. Old
trial evidence and verdicts are unchanged. Removing this infrastructure blocker
does not establish that those candidates would finish successfully.

Provider regression tests cover both native formats, Unicode, schema costs,
multiple removals across human corrections, unchanged admissible histories,
matching call/result IDs, the irreducible-input error, a single transport call
and anchoring to the input actually sent. Phase tests cover both completed and
waiting submissions: modifying real inputs during development still prevents
activation in either experimental arm. Reports explicitly record
`activated: false` when that stage was never reached.

The [validation receipt](seed-v0.0.17-validation.json) records the ordinary
regressions, targeted real-VM regressions, source/controller fingerprints and
scripted calibration of all eight prepared plans. These checks establish
implementation and preparation correctness; they do not measure model success.

## Prepared for later

Fresh local plans live in `.data/v0017-workflow-prepared-20261018/`. No Qwen or
OxCoder trial is started by preparation or `--check-only`. The local
`prepared.json` records supplied parent identities; each `plan.json` freezes the
current starter, trusted controller/graders, settings and verified local assets.
Historical v0.0.16 plans are preserved and cannot be resumed against changed
trusted code.

Start with **one within-model phase-growth comparison**. Separate plans retain
the previously screened Qwen3.5 9B Q4_K_M and OxCoder 9B Q6_K profiles: 128K
context, 4K responses, native calls and thinking disabled. Both use the same
supplied, previously accepted hashing parent. Three repeats alternate arm order:
six growth attempts per model. Each attempt shares 128 actions, 65,536 generated
tokens and 30 minutes across development, checking and final use. Grading uses
the remaining wall allowance. Each arm must independently qualify and activate
its submitted source before final-use credit is possible.

The treatment adds the existing focused development/check/submission and use
instructions. It now explicitly says to keep real task inputs unchanged until
verification and activation, while checking disposable examples. The baseline
retains the original staged task, which already contains that requirement.
Both arms use the same concise activation and resource limits. The treatment
remains outside the default seed; any benefit is unmeasured.

Separate phase-reuse plans isolate final use of one unchanged, supplied,
previously verified two-tool seed. They earn no new-upgrade credit. The model
must format a file, hash its final bytes, save a matching receipt, inspect both
outputs and preserve the seed. Keep reuse results separate from fresh extensions.

The supplied parent packs are historical model-written bytes, not modifications
to the default starter. They are independently rechecked inside disposable VMs
before model trials. They receive no autonomous first-pass credit in this new
comparison. Different quantizations and limited task families prevent a causal
model ranking or a general claim of repeatable self-improvement.

The navigation, edit-feedback, syntax-feedback and masked-history plans were
also refreshed as alternatives. Run one balanced comparison at a time. Their
preparation is not evidence that the treatments help, and navigation retains its
separate 64K profile. Before promoting a treatment, repeat it on another model
and unfamiliar extensions. Third cumulative extensions need new task contracts
and independent checks; this preparation does not claim that coverage.

Use the existing [runner](model-study.md) with the matching local server when
testing is requested. `run --input PLAN --check-only` validates frozen inputs
and scripted VM graders without contacting an inference service. `run --input
PLAN` starts live trials. The ordinary first-launch model selection is unchanged.
