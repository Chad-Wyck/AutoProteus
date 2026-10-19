# Hermes Agent: ideas for AutoProteus

Reviewed 15 October 2026, America/Regina. Hermes source snapshot: [`3b2f971133e4e011022ccf33dc6dc1c9050563d8`](https://github.com/NousResearch/hermes-agent/commit/3b2f971133e4e011022ccf33dc6dc1c9050563d8). AutoProteus HEAD at inspection: `23f073a499cb76c79bceedd1287e1835b126d001`, with existing uncommitted changes. This is a selective architecture/source/test review, not an execution benchmark or a comprehensive security audit.

**The best fit is a small layer of reusable, evidence-backed procedures, paired with retrieval of exact past work.** AutoProteus can learn how to perform an upgrade as well as learning a new capability through source edits. These are complementary forms of growth. This review found no basis for predicting a numerical improvement in AutoProteus's acceptance rate.

Hermes describes learning through persistent memory, agent-authored skills and background review. The implementation exposes skill listing/loading and mutation tools, and its turn finalizer conditionally starts a separate review after delivery. This is experience stored in content; those mechanisms do not themselves update model weights. [Repository overview](https://github.com/NousResearch/hermes-agent), [review trigger](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/agent/turn_finalizer.py#L762), [background review implementation](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/agent/background_review.py)

**1. Reusable procedures from verified experience — highest priority.**

Hermes separates short durable facts from longer procedures. Skills have a small discoverable description; full instructions and supporting references load on demand. The model can create and patch skills. [Skills documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills), [skill loader](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/tools/skills_tool.py#L570)

For AutoProteus, a useful first procedure would cover the class of seed-tool upgrades: locating the implementation and schema, handling text boundaries, adding meaningful tests, exercising the edited copy in a fresh process, completing activation when required, and verifying the actual task result. Extend the existing recipe with specific lessons from independently checked attempts. Avoid duplicating guidance that already lives in the seed or its tool descriptions.

The initial implementation could use ordinary bounded files copied into the task workspace. A short index would identify relevant procedures; the model would read only the selected one with existing tools. Dynamic tool registration and a new broker capability are unnecessary for this first experiment.

A model-written procedure should enter the same evidence workflow as other generated artifacts: preserve its source session, content hash, relevant seed version, observed checks and known limits. Host-owned acceptance evidence should remain separate from its prose. Supporting scripts execute inside a guest. The controller need not import generated modules or mount a host skill directory.

Start with a few useful procedures and measure later task performance. Saving more documents is not evidence of learning. An entry should describe a reusable method rather than accumulating a transcript of each incident.

**2. Recover exact details after context trimming — highest priority.**

Hermes's current session search implementation supports discovery, anchored message windows and browsing/reading sessions. It returns stored messages without a summarization call, deduplicates compression lineage and bounds individual message content. This source is more specific than the overview's broad description of session search. [Search implementation](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/tools/session_search_tool.py#L1), [search tests](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/tests/tools/test_session_search.py)

AutoProteus preserves the complete journal but trims inference history. Its normal tools search workspace files, and its interface can search session titles. Those features do not currently provide the model with bounded retrieval over omitted journal entries. [Context selection](D:/AI_New/AP/autoproteus/agent.py:159), [host session browsing](D:/AI_New/AP/controller/storage.py:137)

The smallest useful addition would retrieve the current task's omitted history using stable event IDs and bounded windows. An omitted tool result could retain a compact reference naming its action, status and recovery ID. Retrieve the original test result or instruction when needed rather than guessing from a summary. Add selected previous sessions later, with explicit task/project scope. A whole-history database migration is unnecessary for an initial prototype over existing journals.

Keep human instructions, activation state and independent verification evidence distinguishable from model claims and generated notices. When code has changed, identify which source fingerprint a recovered test result applies to. Restoring a past passing result must not imply that the current version passes.

**3. Use observed token counts to improve context decisions — high priority, after measurement.**

Hermes has a usage anchor: provider-reported prompt/completion counts plus an estimate of newly appended messages. Its inspected source fingerprints the priced transcript prefix and rejects a stale anchor. [Usage accounting source](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/agent/usage_anchor.py#L46)

AutoProteus currently budgets serialized UTF-8 bytes using a conservative conversion. The provider already records usage, and the prepared navigation study adds opt-in host traces and omission metrics. Use those existing measurements to determine how much usable history the estimate leaves out on each tested model. [Seed estimate](D:/AI_New/AP/autoproteus/agent.py:200), [provider validation](D:/AI_New/AP/controller/providers.py:31), [prepared observations](D:/AI_New/AP/evaluations/observations.py:128)

An experimental policy could anchor to a validated full request identity, including model/runtime configuration, system prompt, tools and retained history. Estimate only the added material, reserve output space and invalidate on edits, activation or model changes. Retain conservative fallback behavior when usage is missing. Provider prompt counts measure context occupancy; they do not by themselves measure uncached computation or saved wall time.

This should be a separate comparison from navigation and procedure reuse. Changing all three together would prevent attribution. Hard host limits and bounded request validation remain independent of the estimate.

**4. Compact selectively and preserve recovery pointers — high priority as a design principle.**

Hermes's compression documentation includes a deterministic pass over old tool results, protection for recent results the model has not processed, and explicit reload notices when skill content leaves context. Its optional micro-compaction makes a real summary-model call and rewrites history; it is disabled by default because repeated rewrites can disrupt prefix caching. [Compression design](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching), [micro-compaction tradeoffs](https://hermes-agent.nousresearch.com/docs/developer-guide/micro-compaction)

For AutoProteus, test compact references to old bulky tool outputs before adding continuous LLM summaries. Preserve exact original instructions and necessary corrections, recent tool-call/result pairs, current capability versions and a route to recover details. A bounded structured handoff can record changed files, outstanding checks and the active seed, while the complete journal remains authoritative.

This fits local inference constraints: an extra summarization request has a measurable cost, and rewriting history may increase prefill work. Count summary calls and their latency in the experiment. Neither smaller prompts nor smoother pauses alone establish a net improvement.

Hermes includes tests for user-message preservation, resume behavior, summarizer failures and bounded search responses. Those are useful verification targets for an AutoProteus prototype; this review inspected test source and did not run the Hermes suite. [Compaction tests](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/tests/agent/test_micro_compaction.py)

**5. Track the history and demonstrated value of learned content — medium priority.**

Hermes records skill mutations with actor information and before/after file manifests backed by content-addressed blobs. Its curator tracks usage and supports recoverable archival; LLM consolidation is opt-in. The ledger source explicitly treats ordinary recording as telemetry rather than an acceptance gate. [Mutation ledger](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/tools/skill_ledger.py), [curator documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/curator)

AutoProteus already has artifact hashes, frozen source comparisons and rollback to the starter. Extend these into a visible history connecting a capability or procedure to its creator session, parent version, independent checks and subsequent successful use. Reuse the current storage rather than adding a parallel versioning system.

Distinguish created, loaded, actually used and independently successful. A loaded procedure can be ignored; a created tool may never be invoked after activation. A new tool passing known checks is evidence about those checks, not a claim of general correctness. Start with simple usage records and recoverable retirement. Automated consolidation can wait until library size creates a measured problem.

**6. Programmatic tool chains — potentially useful later.**

Hermes's code-execution tool lets a Python program call an enabled subset of tools through RPC and returns its output to the model, reducing inference round trips. Its source has explicit call, duration and output bounds. [Programmatic calling implementation](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/tools/code_execution_tool.py#L1)

This could help repetitive local work such as inspecting many files and returning one concise table. AutoProteus already supports Python commands in the guest when terminal access is enabled and has an edited-tool development checker. First test a short guest-side script through that route. A new RPC runtime is unnecessary until a workload needs it.

Count actual work, outputs, failures and elapsed time alongside model requests. A single large script can contain many operations. Any future brokered capabilities must preserve their own authorization and host resource limits through inner calls, and Stop must cover the whole operation.

Hermes also has tool discovery and a central registry. AutoProteus already shares native/JSON descriptions through `TOOL_SPECS`; its current catalog is small. On-demand schema loading and a more elaborate registry become more interesting after accepted tools grow the catalog. Any generated registration code would still execute in the guest, with the host receiving schemas as data. [Tool search](https://hermes-agent.nousresearch.com/docs/user-guide/features/tool-search), [registry source](https://github.com/NousResearch/hermes-agent/blob/3b2f971133e4e011022ccf33dc6dc1c9050563d8/tools/registry.py), [current AutoProteus descriptions](D:/AI_New/AP/autoproteus/providers.py:14)

**Fit to the current project and next experiment.**

The local checkout already contains the prepared eighteen-attempt navigation comparison, overlapping-read metrics and host inference recording. These are useful foundations, not new recommendations from this review. Preserve that frozen experiment. [Current study](D:/AI_New/AP/evaluations/navigation-study.md:1)

After its results, run a separate comparison of the same fixed model/harness with and without one concise upgrade procedure distilled from verified prior work. Start by supplying a plain text artifact; keep model settings, task contracts and budgets equal, and charge its full token/reading cost. Use tasks not used to author the procedure, retain ordinary regressions and independently grade upgrade acceptance. Measure repeated reads, time to first edit, calls after the last passing development check and total cost, using the existing telemetry.

If that improves acceptance or matched-success cost, add a small discoverable library and measure whether the model chooses and follows the right procedure. Only then evaluate automatic extraction after successful tasks. Keep extraction cost, unsuccessful drafts and unrelated-task regressions visible. A fixed human-authored recipe tests knowledge assistance; autonomous skill creation and useful later reuse require their own subsequent test.

A separate interrupted/resumed task can test bounded journal retrieval: require an exact earlier decision to be recovered, verify that obsolete results stay labeled with their old version, and compare against current trimming under the same budget.

Hermes's messaging gateways, schedules, broad backend support and delegation serve a larger assistant product. They are useful reference material for future integrations, with lower immediate relevance to the observed seed-upgrade failures. Its local execution, skill preprocessing, automatic dependency setup and credential-passthrough behavior should be adapted deliberately to AutoProteus's host/guest separation. Retain the network-free VM, protected controller/verifier and inert artifact transfer. [Hermes security architecture](https://hermes-agent.nousresearch.com/docs/user-guide/security), [AutoProteus boundary](D:/AI_New/AP/README.md:64)

No Hermes installation, model trial, automation or application-source change was performed for this review. Only this memo was added.
