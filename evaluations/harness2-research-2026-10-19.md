# Harness2: ideas for AutoProteus

Research date: 19 October 2026. Static review of Google Research's [Harness2 repository](https://github.com/google-research/harness2) at commit `1cfe254e8d25b15f37048c3730134686abe60335`, its paper and experiment documentation. Compared with local AutoProteus commit `aed23d3b73d304c32ae86a9b247fc947c7f4e502` (v0.2.0 preparation). No third-party code was executed, dependencies installed or model trials launched. Repository tests were inspected, not run.

## Assessment

**Highly relevant research; adapt a small part through controlled experiments.** The best contribution is a way to improve the process that proposes improvements: retain specific lessons about edits, their observed effects and when to reuse them. This fits AutoProteus's model-agnostic self-improvement goal without requiring weight training.

The approach also supplies a disciplined alternative to repeatedly asking an agent to improve itself: run the current harness, propose changes with different scopes, try them, compose supported parts and execute the composition. This is implemented in the [recursion engine](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/recursion.py). A successful composition remains a hypothesis until independently checked.

## What is distinctive

Harness2 has two learning timescales. Within a task it edits and probes the execution harness. Across tasks it accumulates an improvement library. Importantly, each subsequent task starts from the common initial execution harness; earlier harnesses are selectively reused through the library rather than automatically installed wholesale. Model weights, stage instructions and the decision rule stay fixed. This is experience-driven harness improvement, not unrestricted rewriting of the trusted improvement algorithm. [Paper, sections 2.2–2.3](https://arxiv.org/html/2610.14224v1#S2)

The code separates general workflow proposals from domain-specific proposals. Their executions, source differences and composition decisions become evidence for the next stage. The editor must produce a usable harness tree; structural validation of that tree is distinct from proving the task or proposed improvement correct. [Proposal stages and validation](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/recursion.py#L135)

## Most useful adaptations

### 1. A small, evidence-linked improvement library

The reflection prompt asks what each edit changed in execution, including changes in rejected candidates. It permits uncertain or confounded conclusions and no new lesson when evidence is inadequate. A durable lesson records an applicability cue, an operation to try, supporting evidence and confidence. Choosing the best deliverable does not establish that every edit in its harness helped. [Reflection prompt](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/prompts.py#L1105)

The library implementation saves the adopted harness alongside that experience and builds an index containing relevance cues. It declines to save an entry without experience. [Library storage and index](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/library.py#L106)

For AutoProteus, begin with bounded lesson files retrieved through existing file tools. Add source/model fingerprints, run IDs, applicability, contrary examples and a distinction between model interpretation and independently observed results. Retrieve relevant entries rather than injecting the whole archive into every prompt. A useful initial hypothesis concerns premature final-input edits during development; do not record a proposed remedy as proven before testing it.

AutoProteus already has a fixed procedure experiment and bounded historical retrieval, but neither establishes automatic extraction of transferable improvement lessons. The new idea is learning which interventions to try from their recorded consequences. [Existing experience experiments](D:/AI_New/AP/evaluations/experience-study.md)

### 2. Test competing explanations before combining changes

Adapt the two proposal scopes to AutoProteus: one candidate addresses workflow, while another addresses the requested tool's contract or implementation. Execute each separately. Combine only supported changes, then execute and check the combined candidate; two individually useful edits can interact badly. Preserve a current-seed option throughout.

This targets a concrete local gap. In the latest completed 9B screen, both Qwen3.5 and OxCoder produced verified second extensions, but only one of the four completed extensions followed the full activation/use order. Three had correct saved outputs before activation. These were single exploratory attempts per contract on an earlier frozen starter, not results for v0.2.0. [Local findings](D:/AI_New/AP/evaluations/seed-v0.0.16-local-findings.md)

The phase-focused and staged-input comparisons already prepared in AutoProteus address this gap. Harness2 adds a mechanism for proposing and comparing remedies; it does not make those existing preparations demonstrated improvements. [Current workflow comparisons](D:/AI_New/AP/evaluations/workflow-experiments.md)

### 3. Give the improver an inspectable evidence package

Harness2 assembles task materials, trajectories, deliverables, current harnesses, candidate differences and decisions into a file tree. Missing trajectory evidence is reported, and a stage fails if no rollout trajectory can be rendered. Individual observations may be clipped, so a complete trajectory listing is not necessarily complete observation content. [Evidence builder](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/context.py#L105)

AutoProteus can build a bounded package from its saved journals and snapshots, with exact call IDs, hashes, errors and explicit omissions. Keep hidden grader fixtures and answers outside model access. Use the package for improvement proposals while retaining the complete protected record. This can reduce reliance on a vague self-summary without expanding the ordinary solver prompt.

### 4. Keep the user experience simple

The useful product outcome would be an optional improvement run with a clear limit, visible progress, Stop, a short account of what changed and a recoverable accepted seed. The component taxonomy need not become a settings page. Keep the selected model by default; a stronger proposer should be a separately chosen and measured configuration. Test the benefit before adding automatic reflection to normal sessions.

## Important limits and differences

**The evidence is encouraging, but not local-small-model evidence.** Main experiments use Gemini 3.5 Flash and GLM-5 executors, with Claude Opus 4.8 as the default editor. The paper reports an 11.5-point WorkBuddy improvement in one configuration and also includes same-model editor/executor experiments. That supports testing the mechanism; it does not establish reliable 4B/9B self-improvement or transfer between AutoProteus profiles. [Paper, experiments and analysis](https://arxiv.org/html/2610.14224v1#S3)

**Selection does not guarantee improvement over the original.** The final selection pool explicitly excludes reference executions; at `k=1`, the sole composed candidate bypasses comparative selection. The composer can nevertheless return `KEEP_BASE`, so it would be inaccurate to say the system always changes the harness. AutoProteus should retain an explicit independently evaluated baseline and decline promotion when evidence is insufficient. [Selection pool](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/selection.py#L93), [single-final handling](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/schedule.py#L513), [composition options](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/prompts.py#L932)

**A small recursion setting still costs several runs.** At `k=1` the ledger expects four task executions: baseline, two candidates and composition, plus three editing stages. These are not seven single model calls: each stage can be agentic. Retries, selection and reflection have additional accounting. On the local GPU, run serially and charge every stage against a declared overall allowance. [Budget ledger](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/ledger.py#L15)

**Preserve AutoProteus's execution boundary.** The release documentation says network access is unrestricted and records a validation rollout downloading a public task rubric without being asked. It also states that its Codex executor disables the sandbox. This is a specific release-validation concern, not proof that all published scores are contaminated. AutoProteus should keep candidate execution in its network-free disposable VMs, with protected checks, credentials and policy outside editable code. [Release experiment documentation](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/docs/EXPERIMENTS.md#L93)

## Recommended sequence

1. Complete the existing balanced workflow comparison first. v0.2.0 already separates edited-tool invocation from testing and makes source modules easier to read; its live model trials remain deferred. These changes may alter the failures a future improver should address. [Current preparation](D:/AI_New/AP/evaluations/seed-v0.2.0-preparation.md)
2. Start with a narrow library-only pilot: baseline versus a few bounded lessons derived from earlier traces. Freeze the library before evaluating unfamiliar extensions. Use the same local model for execution and any automatic lesson extraction initially, recording extraction costs separately and in total.
3. If that helps, add one contrastive proposal/probe/composition round. Compare against unchanged-harness retries with the same overall budget and output-selection opportunity, so extra sampling is not mistaken for better improvement. Use repeated balanced trials, not one winning example.
4. Record independently accepted functionality, retained earlier capabilities, ordered activation/use, exact final artifacts, inference/time costs and incomplete attempts separately. Keep strict visible-input and withheld-input protocols distinct. Only accepted candidate bytes can become a persistent seed; lesson confidence alone cannot authorize promotion.

AutoProteus already supplies frozen plans, durable queues, provenance-aware caching, saved candidate bytes and independent checks. Extend that machinery rather than adopt Harness2 as a new runtime dependency. The immediate research priority is **an evidence-linked lesson library, followed by a tightly budgeted comparison of alternative edits**.
