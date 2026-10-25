# v0.6.0: paired final-task comparison

Freeze the current v0.6.0 seed from commit
`532e36bcc9fcf7a1eb2b69015eef2558c965c13f` against the v0.4.0 runtime control
from `f37b1d9eb781af4defcb4c72d508f91d708096de`. Both run through the same
current protected controller and production native ModelClient connection.
This compares complete seed bundles, not one isolated implementation change.

Reuse the three public CSV tasks and exact fixture bytes from the earlier
prepared study. Each arm starts with the same supplied human-reference CSV
implementation, registration and tests. Add hashing, preserve CSV and all input
bytes, request verification and activation, use both tools, write a correct
audit with the default five-row preview, inspect it and explicitly finish.
The supplied parent earns no autonomous first-upgrade credit. These tasks
replay known failures; they are not unseen generalization.

Use base Qwen3.5 9B Q6_K, 131072 context tokens, 4096 response tokens,
temperature 0.6, thinking off and the previously pinned PrismML engine. Keep
all engine/sampling flags fixed, load no LoRA, and erase slot state before
each attempt. Record actual model/engine hashes, context, adapters and runtime
settings. No final-contract reminder, staged input or extra support treatment.

## Shared regression fixture overlay

Both frozen bundles receive the same 50-case protected regression fixtures.
They retain the current behavior checks while making only two compatibility
adjustments in the copied test file:

- Budget-test helpers count separately supplied declarations for the shared
  prompt, and account for the older JSON prompt's embedded catalog. The helper
  recognizes the existing `NATIVE_PROMPT = PROTOCOL` alias; this changes test
  accounting, not either runtime or its action/context policy.
- The registration test checks one catalog entry's description, required fields
  and terminal filtering without requiring both runtime prompts to be identical.
  Native/JSON delivery of new declarations is separately covered by the current
  real-VM gateway checks.

All 50 test cases remain. No action-limit, free-finish, human-message,
checkpoint, file or rejection check is removed. The copied test files are
root-owned during protected grading. The regular repository tests and source
remain unchanged. Hash the exact overlay and use it in both embedded development
tests and protected grading. These are explicitly overlaid bundles, not exact
copies of either released source snapshot.

## Admission and schedule

Reuse the already passed v0.6.0 ordinary and real-VM receipts only after checking
their implementation and source identities against the current tree. Recheck
each supplied parent and its protected suite in a VM, then run the scripted
positive/absent/semantic-fault grader calibration. Check actual model assets and
require the revised three-round production qualification, including rejection
recovery, exact `diagnostic_confirm.receipt` arguments and explicit completion.
Do not pick a successful qualification retry silently.

Run six attempts in order: old/current, current/old, old/current, with one
identical task/fixture set per pair. Each attempt shares 128 actions, 65536
generated tokens and 1800 seconds across development, independent grading,
retention, activation and final use. Use a four-hour batch bound and preserve
10% free disk plus 3 GiB. Stop on source/runner/input drift or infrastructure
failure; retain every failed/interrupted/skipped record. No operator repairs of
model candidates and no automatic trial retries.

Report independently verified new behavior, package verification, CSV retention,
activation, input preservation, each audit field and actual row count, explicit
finish, observed tool use and complete workflow separately. Report functional
use and native routing separately. Compare efficiency primarily among matched
complete successes; preserve all-attempt costs and label missing measurements.
No new model performance claim is made until trials actually complete.

## Authorized continuation

After the first control completed, the disk percentage guard interrupted the
first current-seed attempt during independent grading. The user explicitly
instructed: "Sorry you can ignore the disk-reserve!" The percentage/free-space
reservation stop is therefore removed for the continuation. Retain the original
attempt as an infrastructure interruption, repeat that cell once from its frozen
parent, and preserve the completed control. All model/task/source/grader settings
remain fixed. Report seven launched attempts (including the interruption) if all
six scored attempts complete; include the interrupted costs separately. Retain
the original four-hour batch deadline across the restart.
