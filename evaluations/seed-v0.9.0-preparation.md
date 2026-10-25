# v0.9.0 preparation and bounded follow-up

The editable seed receives a version update, with no new default tools or model
instructions. New reliability, observation, indexing and experiment code stays
outside the guest seed. Existing isolation, independent grading, credentials and
saved user preferences remain under the protected controller.

Implemented:

- 2,048-message inference envelope, still bounded by serialized bytes, actual
  context accounting, request quotas, actions and VM limits. Oversized histories
  receive a specific diagnostic. A real-VM test carries over 400 human messages.
- Snapshot-versus-summary failure semantics and explicit uncertain journal writes.
  Committed snapshots survive post-commit failures; rejected replacements restore
  the last committed snapshot in memory. Generated lifecycle schedules combine
  writes, deletion, checkpointing, failed saves, receipts and restart recovery.
- An owner-bound read-only observer and local Evidence screen. Observation holds
  the owning store lock and cannot trigger startup recovery or schedule work.
  Original inference blobs are identity checked; previews and pages are bounded.
- Historical findings backfill and keyword search over an append-only index.
  Original reports, hypotheses, costs and scope remain authoritative; indexing
  creates neither new trials nor pooled success claims.
- A separate outcome-first discovery study where the model chooses a tool name
  and interface for a stock-reconciliation task. Caller-selected paths, held-out
  duplicate/Unicode/empty-input cases, protected regressions, the candidate suite,
  independent activation and actual final use remain required.
- Explicit first-install versus experimental profile checking. Connection
  qualification is distinct from seed-editing qualification, and terminal access
  is never silently granted to the fresh default profile.

Initial ordinary validation: 385 tests ran, 48 skipped, no failures. The final
suite includes two subsequently added tests and is recorded separately. Real VM
validation: 26 tests ran, 25 passed and the live-public-web probe was skipped.
Discovery calibration passed the positive reference and rejected both the absent
capability and duplicate-overwrite negative control. An earlier demo-driver
configuration error is retained as setup evidence, with no live model calls.

The default Qwen3 4B Instruct model was missing its 2,497,280,480-byte weight blob
following earlier authorized cache cleanup. A dedicated first-install check
restores it, preserves app preferences and measures the actual default settings.
Its evidence lives under `.data/default-profile-v090-20261024/`.

The historical replay is frozen under `.data/refinement-v090-20261024/`:
three old/current pairs on the exact earlier CSV-to-hashing fixtures, followed
by one balanced exploratory edit-feedback pair. Both runtime parents receive
the same supplied CSV implementation/test and portable 50-case protected overlay.
These are controlled overlaid bundles, not byte-for-byte shipping releases, and
the supplied capability earns no autonomous first-upgrade credit. Each attempt
shares 60 minutes, 128 actions and 65,536 generated tokens across development,
grading, activation and use. Normal app settings and the default seed are not
promoted from exploratory results.

Concurrent admission work caused a VM-lease timeout in one scripted negative
control before any tool action or model request. All original records remain;
that case requires a successful sequential scripted recheck before inference.
Model trials are not automatically retried or repaired.

Prepared variants such as retrieval, usage anchors, observation masking, source
outlines and curated lessons remain optional. Automatic extraction, a package
library, variant search, additional training, inference-engine replacement and
Mac support remain deferred. A single discovery task or familiar replay cannot
establish broad self-improvement or a supported setup profile.

No model-written candidate is adopted by these changes. Live results, complete
measurement coverage and final cleanup are reported in separate dated findings.


Completed follow-up:

- Final ordinary suite: 388 run, 339 passed, 49 skipped. JavaScript syntax and
  whitespace checks passed. No frozen seed/controller/grader/environment drift.
- Historical replay: current runtime 3/3 independently verified packages, old
  runtime 2/3; both 0/3 complete workflows. All six hashing implementations
  passed behavior checks. Activated audits retained the earlier two-row override.
- Edit-feedback pilot: both packages verified, neither workflow completed. The
  treatment repeated the same preview 107 times and exhausted 128 actions.
- One stock discovery attempt wrote a useful tool but submitted an invalid
  handoff. Original grading/activation did not run. A separately labelled
  unchanged-code diagnostic passed three held-out cases with an operator-selected
  invocation template; no original workflow credit was granted.
- The research runner now reports invalid handoffs as explicit unverified
  submission outcomes. Original runner bytes/results remain archived.

See the dated default-profile, refinement and discovery findings/results. No
model-written seed was promoted and no model trial was silently retried.
