# v0.5.1: final-task accuracy comparison

Prepared for later execution. **No tests or model trials have been started.**
The starter gates below must pass before any inference. This study investigates
a known failure; it is not an unseen-capability or generalization test.

## Question and controls

Does the v0.5.1 seed complete the CSV audit more reliably than the v0.4.0 runtime
from commit `f37b1d9eb781af4defcb4c72d508f91d708096de`? The recorded failure is
copying a two-row development demonstration into the final audit, whose default
preview requires five rows.

Use the same independently checked, supplied CSV parent and the same public
task text and three saved CSV fixtures as the 22 October study. Add hashing,
preserve CSV behavior and input bytes, activate the verified source, use both
tools and finish the audit. Freeze the source snapshots and fixture bytes before
execution. A supplied parent earns no autonomous first-upgrade credit.

Both arms receive the corrected protected tests from v0.5.1. Record the original
v0.4.0 source identity and the graded identity with this shared fixture overlay;
do not label that bundle an exact byte-for-byte v0.4.0 copy. Preserve the CSV
implementation, registration and existing feature tests identically in both
arms. New model-written candidates execute only in disposable VMs.

Use base Qwen3.5 9B Q6_K, standard production connection, 131072-token context,
4096 response tokens, temperature 0.6 and thinking off. Pin and record the model
and engine hashes, full launch command, cache settings and all sampling values.
Use no LoRA, final-contract reminder, staged inputs or other experimental
treatment. A loaded-but-disabled adapter must have its disabled state verified
before admission; no adapter comparison is part of this study.

## Gates and schedule

When test execution is authorized:

1. Pass the ordinary regression suite and both runtime arms' 50-test protected
   starter suite inside the VM. Keep evidence of the corrected stable-prefix,
   action-limit, free-finish and saved-file checks.
2. Run scripted positive/negative grader controls, verify each parent retains
   CSV preview and does not already contain hashing, and qualify the actual
   inference connection. Stop on infrastructure failure; do not repair live
   candidates or choose a successful retry silently.
3. Run three paired repetitions, six extension attempts total. Give each pair
   identical task and fixture bytes. Counterbalance arm order old/current,
   current/old, old/current. Start each attempt from its frozen supplied parent.
   Record runtime cache resets and order; repeatability remains exploratory.
4. Each attempt shares 128 actions, 65536 generated tokens and 1800 seconds
   across development, independent grading, retention, activation and final
   use. Keep response/request settings identical between arms. Reserve three
   hours of trial ceilings plus setup and calibration before starting.

Source changes between preparation and execution invalidate the plan. Retain
old receipts and regenerate inputs rather than updating previous scores.

## Outcomes and interpretation

Report these stages separately for every launched attempt:

- Independent hashing behavior, candidate tests and full package verification.
- Retention of CSV behavior, required stage order and activation.
- CSV input byte preservation and each audit field: path, bytes, SHA-256, rows
  and truncation. Record the actual row count, including the known two-row error.
- Exact final artifacts, explicit completion, observed use of both capabilities
  and the full completed workflow. Report native routing separately.

Use complete workflows as the primary user-facing success measure. Report
correct final artifacts separately so coding failures, missed activation and
incorrect final use cannot hide inside a single score. An unactivated attempt
has no observed final-use result; a timeout is not automatically a behavior
defect. Preserve all failed, interrupted, skipped and infrastructure records.

Compare calls, reading actions, generated tokens and time among matched complete
successes. Also report expense for all launched attempts. Label partial usage
measurements explicitly. Do not pool these results with earlier seed versions,
LoRA training runs or ordinary tasks exposed during training.

If this narrow comparison is promising, qualify the simpler workflow on another
intended local model and unfamiliar capabilities before making a broad claim.
Adapters remain a separate, later experiment with their own matched controls.
