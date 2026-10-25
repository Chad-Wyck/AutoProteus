# Pi re-review for AutoProteus — October 24, 2026

**Assessment:** Pi remains a useful implementation reference. Since the October 21 review, AutoProteus has gained several overlapping capabilities. The strongest remaining opportunities are explicit read-only observation, storage-failure semantics, a readable evidence viewer, and design guidance for the extension library planned after v1. Pi's recent streaming changes are relevant mainly to future host/UI responsiveness.

## Scope

Reviewed upstream snapshot [`bdb151774ed6bef2b5676bbff4669f20a0c233fe`](https://github.com/earendil-works/pi/tree/bdb151774ed6bef2b5676bbff4669f20a0c233fe), the latest commit returned at review time. GitHub's comparison reports **63 commits ahead** of the previous reviewed snapshot `bd3c9b823762b7383954aa49e13ee350471015fe`, affecting 284 paths. This is a scoped review of selected changes, implementation sections and test assertions, not an audit of all changed code.

The coding-agent package manifest declares **1.4.0**; selected changelogs also contain **Unreleased** work. Source review does not verify that every described change is in a published package. The companion JSON records 22 selected upstream files and 22 local inputs.

Local context is the uncommitted AutoProteus working tree documenting v0.8.2, based on HEAD `532e36bcc9fcf7a1eb2b69015eef2558c965c13f`. Read the earlier Pi note, current storage/provider/receipt/UI code, guidance results, new activation-study notes and experiment index. Only these two dated research files were added. No dependencies were installed, external code or tests executed, model/GPU work launched, source/defaults changed, or timers enabled.

## What AutoProteus already has

| Earlier Pi idea | Current local status |
| --- | --- |
| Preserve effective prompts and tool declarations | controller/inference_history.py records source/profile-bound provider payloads and content-addressed evidence; exports include those blobs |
| Steer active work separately from later follow-ups | Existing persisted queues, delivery acknowledgements, cancellation and UI controls |
| Make interrupted operations explicit | Host-owned start/result/checkpoint/recorded receipts; Resume explains uncertain outcomes and never automatically replays operations |
| Translate tool exchanges for different model connections | Shared seed catalog/action format, protected native/JSON adapters, paired call/result handling and qualification checks |
| Keep experiment history | Frozen plans/source identities, independent graders, new compact append-only experiment index |
| Discover specialist tools only when needed | Still a possible later idea; today's small catalog does not establish a need |

These mechanisms should not be proposed again as missing features. Pi is not evidence that a particular context change, shorter prompt or extension improves AutoProteus's 9B workflows.

The latest guidance study still found schema/default/boundary defects and failure to finish after correct output. The subsequent [A16 activation comparison](D:/AI_New/AP/evaluations/vultr-a16-activation-2026-10-24-findings.md) was stopped early: both first hashing workflows passed, the baseline inventory stage failed schema/test requirements, and the treatment's inventory stage was interrupted. That incomplete comparison establishes no context-placement winner. The [activation study](D:/AI_New/AP/evaluations/activation-comparison.md) and [experiment index](D:/AI_New/AP/evaluations/experiment-index.md) already exist; another orchestration framework would duplicate current preparation.

## 1. Explicit observation that cannot recover or run a task

Pi Durable adds a logical read-only Harness mode. A viewer leaves running tasks in their committed state, refuses writes and scheduling, and does not perform the recovery reserved for the next writable open. The [tests](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/durable/test/harness-read-only.test.ts) open a viewer beside an active driver, verify the running task remains running, and check that the stored head does not advance for that existing session. They also test rejected submission, abort, resume and root creation. [Implementation guards](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/durable/src/session/session.ts#L684).

**Why this fits AP:** controller/storage.py's Store constructor intentionally marks running/stopping sessions interrupted and saves them during startup. That is appropriate for the owning controller recovering after a restart. It makes that class an unsuitable generic reader for a separate monitor attached to a live store. This review did not demonstrate that the ordinary browser UI makes this mistake.

AP already exposes revision-based session views through its existing controller and research runners already report progress on stdout. Prefer those supported observation paths. If standalone inspection or another device is added, give it an explicit viewer interface that cannot invoke startup recovery, change status, enqueue input or advance receipts. Add regression coverage with an active owner.

Pi's flag is an application-level session guard, not an OS read-only database permission. Its storage adapter can initialize metadata on open; do not infer that all filesystem activity is forbidden. On Windows, a viewer also needs a read strategy that does not block atomic replacement. The AP guidance study already recorded a possible live-reader interference problem and switched monitoring to stdout.

**Priority:** high for research helpers and future monitoring; small in scope.

## 2. Define failure semantics around the durable commit

Pi's new storage contract calls an adoption callback after the batch is durable and before the next commit begins. It publishes changes afterward. A failure before adoption discards staged memory; a failure after adoption does not pretend that the committed write can be rolled back. It fails the session. [Commit sequence](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/durable/src/session/session.ts#L653), [fault-injection tests](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/durable/test/session-adoption.test.ts).

AP already uses atomic JSON replacement, fsync, file manifests and operation receipts. Those are valuable existing protections. Individual atomic files do not by themselves define the outcome of a multi-step session/summary/journal/checkpoint update.

**Adaptation:** specify what has committed at each step and add focused failure tests around failed replacement, session-save success followed by summary-save failure, receipt-journal failure, and interruption between committed files and saved conversation state. The UI and recovery notices should follow the last committed state. Unknown outcomes should remain inspectable rather than replayed.

This is a hardening proposal, not a reproduced AP corruption finding. A database migration or importing Durable is not necessary to borrow its explicit contract and tests.

**Priority:** high before expanding automatic improvement or extensions.

## 3. Package extensions with explicit identity and activation

Pi packages bundle extensions, skills, prompts and themes. Their manifest can declare resources, consumer filters can narrow them, versioned npm sources and git refs can be pinned, and per-project versus personal scope is documented. [Package format](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/coding-agent/docs/packages.md).

Its loader tests cover visible install failures while other resources continue loading, invalid manifests, and warnings about packages bringing duplicate copies of host runtime modules. [Resource-loader tests](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/coding-agent/test/resource-loader.test.ts#L43).

**AP adaptation for the library planned after v1:**

- Identify an extension by version plus exact source hash; declare tool names, schema, compatible seed versions, examples and independent functional checks.
- Make selection and availability visible. An unavailable optional package should not prevent opening the app, but a task requiring it must not be represented as ready or completed.
- Make name collisions and replacement of existing tools explicit.
- Restore the exact selected extension/source state with a session; installing a newer package must not silently change an old experiment.
- Keep extension code in the editable guest and use existing host-controlled capabilities. Registration or a manifest must not grant new host permissions.
- Reuse independent checking and explicit activation before normal use.

These AP manifest fields and policies are proposed adaptations, not features all provided by Pi. Pi's normal process-loaded extension model has different permissions. Borrow its packaging and usability conventions while preserving AP's VM and controller boundary.

Pi's current agent-session code reconstructs tool state from transcript declarations and separately handles tools registered later. That is a useful source of restore/add/remove/replacement test cases for the future library. [Tool-state restoration](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/coding-agent/src/core/agent-session.ts#L1824). AP should preserve its own explicit activation rules.

**Priority:** high as a design reference for the post-v1 library; no package manager is needed now.

## 4. Render the evidence AP already records

Pi fixed an export problem where system instructions and tool changes existed in the export data but were not displayed. Its tests check initial prompts, section updates and added/removed tools. [Export tests](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/coding-agent/test/export-html-system-messages.test.ts).

AP's Save trace currently downloads a ZIP containing session.json, events.jsonl and inference blobs. It already preserves the actual evidence; the opportunity is a readable local viewer that links each action to:

- the active seed/source and tool schema;
- the effective model instructions and actual request;
- activation/queued-user-input boundaries;
- reported result, checkpoint state and independent verification.

This could help diagnose repeated actions or stale requirements and make manual training-data review easier. It does not prove why a model failed, and a guest-reported result must remain distinct from independent checks. Keep the viewer local by default and preserve evidence provenance.

**Priority:** medium; strong convenience and debugging value.

## 5. Bound the cost of large streamed answers and slow viewers

New Pi code parses streamed arguments incrementally, keeps parser bookkeeping off message content, and performs one final parse when a call ends. Partial values are for preview. Its parser is deliberately tolerant; importing its preview semantics as AP's action validator would be inappropriate. [Parser](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/ai/src/utils/streaming-json.ts#L447), [provider-stream test cases](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/ai/test/streaming-tool-arguments.test.ts).

Chord's PendingOps folds pending display-state changes for slow consumers and replaces an excessive backlog with the newest snapshot. [Queue](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/chord/src/delta/pending.ts), [adversarial/cap tests](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/chord/test/delta-pending.test.ts). Durable's event watcher preserves batches normally and explicitly sends a new snapshot on backlog overflow; consumers must handle that reset. [Event observation](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/durable/src/harness/events.ts#L180). A UI feed is not the audit journal.

AP already has bounded Ollama responses, completed-response action validation, revision-based UI polling and incremental feed delivery. Its current OpenAI-compatible/Prism request uses stream:false, so Pi's repeated partial-JSON parsing failure is not the current path. Do not claim AP has the same bug or transplant a 500-line parser without need.

If live argument/code previews are added, append new pieces, batch display work, cap pending updates, and test final equivalence, interruption and slow consumers. Never execute a preview or drop durable evidence to make the UI faster. Measure AP host CPU/RAM and responsiveness first. Pi's reported heap savings do not establish lower GPU VRAM or faster model generation here.

**Priority:** future-facing, after evidence of a local bottleneck.

## Additional test references

Pi's resumed-output-limit regression removes a truncated tool call together with its associated result, preventing orphaned provider history. [Regression](https://github.com/earendil-works/pi/blob/bdb151774ed6bef2b5676bbff4669f20a0c233fe/packages/coding-agent/test/suite/regressions/11227-recovery-omits-tool-results.test.ts). AP already rejects incomplete responses and tests matching IDs/orphans. Extend its compatibility fixture matrix where appropriate; retain original evidence and do not synthesize successful execution.

Deferred specialist catalogs, cross-model history cases and session branches remain useful later references from the October 21 review. Branch restoration must bind files, source and tool state, not only conversation text. No need to add parallel agents, migrate the TypeScript runtime or expand model-generated context by default.

## Recommended order

First formalize the observer boundary and commit-failure tests, using existing AP code and no model calls. Next expose a readable evidence timeline. Use Pi's package/resource design when specifying the post-v1 extension library. Treat streaming changes as a measured optimization if AP adds the relevant UI/protocol path.

All effectiveness claims require AP-specific evaluation with independently checked contracts, correct final outputs and explicit completion. This source review establishes implementation relevance, not improved autonomous performance.
