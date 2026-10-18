# v0.1.0: corrected workflow qualification

This release includes the pending optional workflow features and three review
fixes. The editable seed retains its prompt, tools and message format; only its
version changes. Host limits and VM policy remain protected. No live-model
benefit is established by this preparation.

## Calibration describes the exact required checks

Workflow input cache identities now include the experiment, reuse/growth mode,
parent tool, required existing capabilities and required absent capability.
The same description drives execution of those checks and appears in the saved
receipt. Cache eligibility verifies that description as well as the evidence
hash. A reuse receipt cannot satisfy growth calibration merely because its
source bytes match. A regression reproduces reuse followed by growth with an
already-present addition and requires the growth plan to reject it.

## One deadline reaches grading workers

Development, candidate regressions, held-out feature checks, fresh-worker public
calls, retention, activation and final use share one absolute monotonic deadline.
Each grading entry checks it before cache access and again before execution.
Workers receive the remaining time and a host deadline covering VM startup and
guest execution. Once it expires, later checks are recorded as not run and
activation is withheld. Results that return late cannot earn acceptance.

Shutdown and saving evidence cannot be instantaneous. Reports preserve actual
total time, deadline overrun and final cleanup duration separately. Cleanup does
not allow another check, model call or activation. Ordinary standalone checks
retain their existing limits when no shared deadline is supplied.

The clock regression gives development 15 seconds and regressions 10 seconds
inside a 30-second trial, then exhausts the remainder in feature grading. Public
and retention workers never start. A real VM regression stops a busy guest at
the shared deadline and verifies that an expired regression check launches no VM.

## Human text stays human through the real transport

The seed still sends neutral `role`/`content` messages. Before guest state can
change them, the broker snapshots the original task, recorded human inputs and
the current host-supplied follow-up. It recovers their human provenance before
native translation. This bookkeeping never enters provider API messages and
grants no permission or authority over host policy. Caller-supplied extra fields
are still rejected by the broker's inference-frame validator.

An orphan `ACTION RESULT` message is kept as ordinary context without attempting
to parse JSON. Known human text is protected even when it contains valid JSON
and resembles an actual result. Tests exercise the seed/broker/provider path,
plus a real VM using a fake provider through pruning, Resume and concise
activation. Real tool exchanges continue to translate with matching call IDs.

## Deferred studies

Fresh plans are saved locally in `.data/v010-workflow-prepared-20261018-final/`.
They replace the earlier prepared plans, preserving historical evidence. Both
models keep their screened profiles and the same supplied parent bytes.
The shared parents are independently checked before either experimental arm;
their reuse earns no autonomous first-upgrade credit.

Run one within-model phase-growth comparison first: three repeats per arm,
alternating order, under identical 128-action, 65,536-generated-token and
30-minute allowances. Separate phase-reuse plans measure use of an unchanged
two-tool seed. Navigation, edit feedback, syntax feedback and masked history
remain alternatives, not additional default machinery. See the
[workflow guide](workflow-experiments.md) and [runner guide](model-study.md).

The [validation receipt](seed-v0.1.0-validation.json) records regression results,
source/controller identities and fresh scripted plan calibration. Qwen and
OxCoder live trials remain deferred. Directed extension, unchanged-capability
reuse and discovery of a useful capability are different claims. A future
unfamiliar task should specify its outcome checks before execution without
prescribing the new tool's name; this release does not claim that qualification.
