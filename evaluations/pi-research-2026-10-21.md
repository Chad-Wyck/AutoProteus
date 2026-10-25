# Pi and Pi Durable: relevance to AutoProteus

21 October 2026, America/Regina. Scoped source/documentation review; no installation, upstream test execution, inference, GPU activity or application changes.

**Pi is open source, and several of its mechanisms are useful references for AutoProteus.** The canonical repository is [earendil-works/pi](https://github.com/earendil-works/pi). Its [MIT license](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/LICENSE) covers the repository. The same tree contains the terminal coding agent, provider library, agent loop and [Pi Durable](https://github.com/earendil-works/pi/tree/bd3c9b823762b7383954aa49e13ee350471015fe/packages/durable). The latter deserves particular attention for recovery and recording changes during long conversations.

Reviewed upstream revision: `bd3c9b823762b7383954aa49e13ee350471015fe`, observed on main on 21 October. Coding-agent and Durable package manifests declare version 1.3.0; this is a source snapshot, not verification of a published release. The website's [Pi 1.0 announcement](https://earendil.com/posts/pi-1-0/) and [Durable introduction](https://earendil.com/posts/pi-durable/) are dated 1 October. Architecture claims below were checked against selected source and test assertions, rather than relying on those announcements.

## Current AutoProteus context

Local HEAD was `4d3c8f3707fc69754a86dbf580528798f831c718`, v0.3.0. Also read the newer, uncommitted 21 October staged-input, LoRA and checkpoint-audit findings. Those files belong to ongoing work and were left unchanged.

The latest [LoRA pilot](lora-pilot-2026-10-21-findings.md) found working formatter implementations in all twelve growth attempts; completion still depended on submission scope, activation, capability reuse and finishing. The three staged adapter attempts completed versus two fresh controls, with only three repeats per condition. [OxCoder's staged-input review](seed-v0.3.0-oxcoder-staged-input-findings.md) also separates correct artifacts from actual use of the added capability. These results make workflow state and operational clarity relevant targets; they do not establish that Pi's design improves AutoProteus.

Already present in AutoProteus: a small editable guest, protected controller, disposable VM, atomic session snapshots, append-only journals, workspace manifests, model/profile qualification, source identities, activation notices, direct/development use accounting, bounded context pruning, separate phase instructions and opt-in workflow/experience studies. Pi's minimalism supports this existing direction. Saved sessions, model adapters or activation instructions should not be reported as new missing features.

## Most relevant ideas

### 1. Record prompt and tool changes as part of conversation history

Pi persists the initial prompt sections and tool declarations, then records section changes, removals and additions at their positions in the transcript. Replay reconstructs the effective state. Tests cover replacing declarations under an existing name, reordered sections and rebuilding a complete baseline after context cuts. [Durable prompt implementation](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/durable/src/harness/prompt.ts), [prompt tests](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/durable/test/harness-prompt.test.ts), [session format](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/coding-agent/docs/session-format.md).

**AutoProteus adaptation:** extend the normal host journal with source-bound instruction/catalog events, and reference the effective state from each inference request. Reuse existing source/profile identities and explicit controller activation. The normal guest `model_request` event currently records messages/model/provider; the richer research provider traces capture the actual native schemas. Having sufficient trace context required excluding older runs from the first LoRA dataset. A standard historical tool-state record would improve reproducibility and future training-data extraction.

The broker already injects a current-activation notice and the experiment runner supplies focused phase instructions. This proposal improves historical reconstruction and diagnostics; it is not a missing activation reminder or a measured remedy for reading loops. Providers without native mid-conversation system/tool updates can continue receiving reconstructed current instructions and schemas. Cache benefits require measurement on the actual local backend. Pi's [provider tests](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/ai/test/transcript-tool-changes.test.ts) explicitly exercise different transport behaviors.

### 2. Make interrupted operations and retried submissions explicit

Pi Durable stores final arguments and replay policy before tool execution. After restart, a call reruns only when both the stored policy and the currently installed tool permit replay. Otherwise it returns an interrupted result with retained partial output. Recovery tests close and reopen storage and check execution counts. [Implementation](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/durable/src/harness/tool.ts#L168), [recovery tests](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/durable/test/harness-tools-recovery.test.ts#L109).

**AutoProteus adaptation:** add explicit operation IDs and receipts linking intent, result, saved file manifest and transcript position. Exercise interruption between those commits. The guest currently transfers the file checkpoint before its state delta, and the existing Resume instruction already warns about an action finishing without a recorded result. The useful addition is a precise, inspectable recovery state and policy. This review did not demonstrate a duplicate-action bug in AutoProteus.

Keep replay decisions in the protected controller, bound to the restored checkpoint and exact seed identity. An editable guest's declaration that a command is safe cannot authorize host behavior. Arbitrary shell commands need an uncertain-outcome path rather than automatic repetition.

An operation receipt describes observed protocol state. Guest-reported execution remains separate from independent filesystem and capability verification.

Pi also deduplicates incoming submissions by conversation/request ID. That protects submission admission, not arbitrary external side effects. Its code intentionally returns the original submission even if a reused key carries different content. An AutoProteus version should bind or validate the payload and source/model context to detect accidental key reuse. [Submission admission](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/durable/src/harness/submissions.ts#L201), [deduplication test](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/durable/test/harness-submissions.test.ts#L82).

### 3. Separate steering from queued follow-up

Pi's loop has separate queues for steering an active run and follow-up input consumed when it would otherwise stop. Delivery is governed by execution boundaries; callers must not assume a running tool is cancelled immediately. Tests cover queue delivery around tool execution and request preparation. [Loop](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/agent/src/agent-loop.ts#L289), [queue test](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/agent/test/agent-loop.test.ts#L762).

**AutoProteus adaptation:** allow a user to choose “Change direction” or “Do this afterwards” while a task runs. Currently the web composer is disabled during work, and sending a follow-up requires stopping/resuming. A persisted queue delivered at a defined inference boundary could avoid unnecessary VM restarts. Preserve human provenance, acknowledge pending delivery, retain cancellation controls and charge extra work to the existing task budget. This is a clear convenience opportunity without requiring a new reasoning model or parallel agents.

### 4. Defer tool declarations as the capability library grows

Pi Durable searches deferred tools using names, descriptions and schema text, then makes selected tools available for a subsequent request. Its default mechanism uses lexical ranking, without an embedding service or separate summarizer. [Tool-search implementation](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/durable/src/tool-search/tool-search.ts).

**AutoProteus adaptation:** preserve the small basic catalog; later expose a compact index and discover selected specialist capabilities as their number grows. Bind loaded declarations to verified source. A separate comparison could test phase-specific tool presentation after activation, while retaining access to every operation required by the user's task. Restricting an evaluation's available routes changes its conditions and must be reported explicitly.

This is lower priority with today's small catalog. The earlier navigation comparison recorded no use of `source_outline`; making another discovery tool available is not evidence that a 9B model will use it. Compare full versus selective catalogs on unfamiliar extensions, including selection mistakes, extra calls, context size and total time. Avoid growing a plugin system just to reduce a catalog of a few tools.

### 5. Treat model handoff as message translation

Pi's provider layer tracks the producing model/API/provider, normalizes tool IDs and results, removes another model's reasoning/signatures, and marks missing tool results as errors. That last behavior supplies transport-valid history; it does not establish that a tool executed. [Translation code](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/ai/src/api/transform-messages.ts#L119), [cross-model tests](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/ai/test/transform-messages-cross-model-thinking.test.ts).

**AutoProteus adaptation:** use these cases when expanding provider support or model-switching qualification. Retain original evidence, disclose transformations and requalify the complete inference profile, including adapter settings. AutoProteus already translates native versus JSON tool exchanges, keeps reasoning outside its normal action history and has repeated protocol checks. The useful contribution is a richer compatibility test matrix, not a new provider abstraction or automatic model router.

## Later ideas and boundaries

Pi's session tree keeps branches through entry IDs and parent IDs, with prompt/tool state restored along the branch. AutoProteus already records `candidate_from` for a fresh edited-seed trial. A future branch view could connect experiment, source, workspace checkpoint, profile, costs and verifier outcome. Conversation branching alone is insufficient to restore an earlier filesystem. [Session-tree format](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/coding-agent/docs/session-format.md).

Pi's extension/reload mechanisms show practical malleability. They are not evidence of independently verified improvement or transfer to AutoProteus's local models. Pi documents that tools/extensions normally inherit the process's operating-system access; preserve AutoProteus's VM, credentials boundary, independent checks and explicit activation. [Pi security model](https://github.com/earendil-works/pi/blob/bd3c9b823762b7383954aa49e13ee350471015fe/packages/coding-agent/docs/security.md). Provider-specific cache warming, a TypeScript runtime migration, automatic compaction calls, unrestricted extension execution and population/subagent machinery are not near-term recommendations.

## Recommended order

First, specify source-bound prompt/tool history and replay checks without live inference. In parallel planning, define the small human-input queue and its Stop/Resume semantics. Then add focused interruption tests and deduplicated input receipts. Selective tool discovery can wait for evidence of catalog pressure.

For a later live comparison, retain the existing staged-input baseline and evaluate one isolated context/tool-presentation change on new extension contracts. Count submission, activation, actual capability use, artifact correctness, explicit finish and cost separately. Use the same sampling, budgets and independently checked parent. Pi supplies implementation ideas; the benefit for AutoProteus remains a hypothesis.

The eight-repository watch automation was not changed. This was a specific review, not an automatic ninth watch entry. The accompanying JSON manifest records the source snapshot and scoped review inventory.
