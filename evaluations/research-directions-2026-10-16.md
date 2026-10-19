# Additional research directions for AutoProteus

Research date: 16 October 2026, America/Regina. AutoProteus HEAD at inspection: `380c96b8d32fedf4ea61449a8ff7b8a6985d0307`. The earlier research memos and other untracked notes were present. This review adds this document only; it starts no model trials, installations, schedules or application changes.

**The strongest direction is an evidence-driven improvement loop that remains usable across models and simple for the user.** The model proposes a focused change, independent checks establish what it does, useful versions remain available for future work, and the controller handles recoverable transitions under a bounded policy.

The proposals below are my adaptations of the cited research. None of the external results establishes an AutoProteus performance gain, reliable improvement on small local models, or indefinitely accelerating self-improvement.

**Current foundation.** The checkout already has network-free disposable VMs, an editable guest seed, a protected controller, native and JSON action formats, a two-request protocol diagnostic, independent feature graders, source fingerprints and staged activation tests. It also has separate prepared navigation, procedure, history, context and inspection-program comparisons. The v0.0.12 findings describe preparation and evaluation corrections, with no live trials during that preparation. Those experiments remain the appropriate baseline; this memo does not treat their proposed features as newly discovered improvements. [Current experiment plan](D:/AI_New/AP/evaluations/experience-study.md), [release findings](D:/AI_New/AP/evaluations/seed-v0.0.12-findings.md)

| Direction | Main contribution | Best time to investigate |
| --- | --- | --- |
| Failure-guided proposals | Turn observed failures into specific, testable improvements | Now, beginning with saved evidence |
| Recursive-gain evaluation | Measure whether an improved seed produces better future upgrades | Once a usable descendant exists |
| A small archive of alternative seeds | Preserve useful approaches and branch from suitable predecessors | After multiple viable versions exist |
| Portable behavioral contracts | Make new capabilities understandable and testable across models | Alongside the next tool experiments |
| Tested setup profiles | Reduce model-specific tuning and distinguish compatibility from competence | Product work after bounded calibration |
| A durable improvement workflow | Let the user request an outcome while the controller manages stages | First for independently gradeable capabilities |

**1. Turn failure evidence into focused improvement proposals.**

GEPA uses execution trajectories and textual feedback to diagnose failures and propose changes to prompts or other textual components. Its adapter interface separates evaluation outputs, scores and trajectories from reflective feedback. It does not require gradient access to the task model. [GEPA paper](https://arxiv.org/abs/2507.19457), [current adapter and optimization documentation](https://gepa-ai.github.io/gepa/)

For AutoProteus, turn a failed attempt into a compact improvement ticket: the task and source fingerprint, the observed failure, a few relevant calls/results, the proposed cause, one change to try, its predicted benefit and how to falsify that prediction. Separate measured facts from the model's explanation. Existing traces and independent results supply much of the data.

Useful categories include navigation that never reaches an edit, incorrect character/byte handling, valid code that is never activated or used, completion-format failures, context loss and inference timeouts. They call for different interventions. A passing development check followed by many extra actions is a different problem from a tool that corrupts text. Slow CPU prefill may require a runtime/profile experiment rather than a source-code rewrite.

Let the agent choose a hypothesis and propose a small editable-seed change. Initially compare one component at a time: tool description, navigation helper, stopping behavior or context policy. Host configuration changes remain separately controlled experiments. Keep untouched validation tasks and charge the entire proposal, development and checking process to the experiment's cost.

An offline first step is possible: classify saved attempts and prepare evidence packets without calling a model. The next live comparison would test a generic improvement request against one containing a bounded factual failure packet. Distinguish help from feedback from improvements authored by a human or a stronger external model.

**2. Measure improvement in the ability to improve.**

STOP explicitly studies an improver modifying its own scaffolding. SICA uses previously evaluated agents as the agents that make subsequent changes, and DGM includes a control that keeps the original modifying agent fixed. These are useful precedents for evaluating recursion at the system level. [STOP](https://arxiv.org/abs/2310.02304), [SICA methods](https://arxiv.org/html/2504.15228v1), [DGM baselines](https://arxiv.org/html/2505.22954v1#S4.SS3)

AutoProteus's existing staged growth test checks adding capabilities, preserving them and using them after activation. Add a distinct question: does a descendant seed produce independently accepted upgrades more reliably or cheaply than its ancestor?

Freeze the parent and descendant, then give both fresh copies of the same unseen upgrade tasks, identical task files, the same model/runtime and equal development budgets. Compare accepted children per launched attempt, preserved behavior, completion, total requests and fully measured cost. Use task families beyond the feature that created the descendant. Keep prior histories and supplied lessons matched unless they are the variable being tested.

A useful control keeps the original seed as the improver throughout several generations. The experimental condition uses the accepted descendant to make the next upgrade. Record source identities and independently check every generation. Report ordinary task capability, cumulative feature growth and improvement-production ability separately.

If no viable descendant is produced, the recursive experiment has not met its prerequisite. A human-written positive control can validate the test machinery, but cannot count as model-produced recursive progress. A few successful generations would be bounded empirical evidence, with repeatability still to establish.

**3. Keep a small archive of alternative seeds and choose parents deliberately.**

DGM maintains a growing archive and branches from earlier agents. Its reported successful lineages sometimes pass through ancestors with lower benchmark scores; it compares archive-based exploration with always modifying the latest viable version. Its archive-selection machinery itself remains fixed in the original paper. [DGM methods and ablations](https://arxiv.org/html/2505.22954v1#S3)

AutoProteus could retain a small set of useful seed variants: one reliable under a small model, another efficient at navigation, another stronger at staged growth. Store their behavior vectors, source hashes, model profiles and lineage. Select a parent based on the next research question. Reuse the artifact/checkpoint store rather than creating another source-control system.

Separate research retention from active use. A failed experiment can remain as inert evidence; an executable research parent must meet the chosen integrity and functionality conditions. A specialist branch with a tradeoff need not become the user's default. Recombining two changes creates a new candidate requiring fresh checks.

Start with a very small archive and serial runs on existing hardware. Keep correctness, resource use and compatibility visible separately. Avoid selecting solely on a blended score that can reward a faster wrong answer. Record both useful successful branches and why other branches failed, so future attempts can avoid repeating them.

**4. Make capability behavior portable through explicit contracts and generated edge cases.**

A new tool needs more than a name and parameter types. Give it one concise behavioral contract: units, exact bounds, return structure, mutation behavior, rejected inputs, examples and relationships that should always hold. The same semantics should drive native and JSON descriptions; a model-specific phrasing experiment should not change the tool's meaning.

Property-based testing generates inputs from a specified domain to test invariants, including unexpected edge cases. This offers a practical way to extend AutoProteus's existing independent graders and calibrated negative controls. [Hypothesis documentation](https://hypothesis.readthedocs.io/en/latest/)

Examples for future contracts include:

- A text append preserves the original prefix, and an empty append has the specified no-op behavior.
- Canonical JSON formatting is idempotent under a contract that specifies ordering and whitespace; parsing preserves the represented value.
- A CSV preview's reported column count agrees with an independent parser on the bounded accepted input domain.
- A rejected oversized or invalid input preserves the original file bytes.

Generate fixtures with trusted code and execute candidate behavior only in guests. Retain failing examples for replay. A deliberately wrong implementation should fail the grader; the current character-versus-byte negative control is a good starting pattern. Candidate-written tests remain development feedback, while protected checks remain authoritative. This approach need not add a third-party dependency to the normal seed.

There is also a recent related research direction: SpecForge refines natural-language behavioral specifications from execution failures and accounts for dependencies between program entities. The public abstract reports experiments across five backbone models and warns that local specification improvements can regress dependent entities. I reviewed its abstract and metadata, not a reproduction; its 11 October 2026 posting makes it a watchlist item rather than an established AutoProteus design choice. [SpecForge](https://arxiv.org/abs/2610.15708)

**5. Offer a tested setup profile for the selected model and computer.**

BFCL's multi-turn work distinguishes chained tool execution, follow-up handling, missing parameters, missing capabilities and long context. Its evaluation combines resulting state with necessary execution evidence. These are useful test categories for practical compatibility. [BFCL multi-turn methodology](https://gorilla.cs.berkeley.edu/blogs/13_bfcl_v3_multi_turn.html)

AutoProteus's existing diagnostic verifies a harmless tool/result/completion exchange. Extend it with an optional small practical calibration: make and edit an exact file, handle a correction, recover from a failed action and finish correctly. Add a bounded real-workload memory/latency check; merely loading model weights did not establish workload fit in the earlier local/cloud investigations.

Show the result in plain language: which protocol and limits were tested, what tasks passed, estimated response speed and any unavailable measurements. Cache it by model digest or provider identity, engine version, hardware, protocol, relevant settings and harness/tool fingerprint. Recheck when those change. A model with insufficient identity information gets a correspondingly limited claim.

Recommend a profile for the user to select; preserve explicit protocol choices and existing preferences. Keep advanced controls available. Model agnosticism is served by a stable behavioral interface and measured support across providers and sizes; it does not imply every model has equal competence.

Qualification should include at least one additional model before labeling a seed change broadly compatible. Distinguish tested-for-one-profile from portable across tested profiles. A strong model may be an optional research assistant, while the result must still be tested using the user's chosen model. The product should remain usable without an external teacher.

**6. Make the improvement lifecycle a durable user workflow.**

Anthropic's long-running-agent work uses explicit feature requirements, incremental changes and handoff artifacts to preserve progress across context windows. It also identifies premature completion and insufficient end-to-end testing as failure modes. Those mechanisms can inform a provider-neutral workflow without requiring its SDK. [Long-running harness design](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)

AutoProteus already exposes checking, continuing with edited source, trying it separately and restoring the starter. A future convenient mode could orchestrate those operations around the original outcome:

`request -> identify a missing capability -> develop -> independently check -> activate -> use -> verify the requested result`

The controller would persist the current phase, source version, passed checks, pending work and remaining allowance. After a restart it could identify the next valid step without asking the model to reconstruct controller state. Keep model-authored plans separate from host-observed completion and verification. Running a checker and passing it are separate states.

For known capability classes with independently specified checks, the user could authorize a bounded improve-and-continue run. They would see meaningful milestones, Stop, a cost/time allowance and an undo route. A new permission or changed task requirement remains explicit. Reaching a limit pauses saved work; it must not trigger unlimited automatic Resume or repeated paid retries.

For unfamiliar capabilities, generate a reviewable proposal and independent-check plan before treating the behavior as accepted. A model setting its own feature-list field to true cannot substitute for those checks. This integrates the existing boundary while reducing manual coordination.

User convenience should also be measured: completed original tasks, interventions needed, restarts, time to a usable artifact, and successful recovery after interruption. A growing tool count alone is not the outcome the user asked for.

**Keep experimentation affordable and evaluate repeatability.**

AlphaEvolve describes an evaluation cascade that reserves expensive tests for promising candidates. AutoProteus already runs protected regressions before model comparisons. Build on that order: structural/contract checks and deterministic probes in guests, then focused tasks, then broader repeated comparisons and model-transfer checks. A promising early stage is a triage result; full acceptance still requires the declared checks. [AlphaEvolve evaluation design](https://arxiv.org/html/2506.13131v1#S2.SS4)

For code changes, check actual returned values and preserved files. For prompt or context changes, pair task/repeat cells and retain all launched attempts. Report total search expense and failures alongside the winning candidate's performance. Include maintenance complexity and the extra inference caused by reflection, summaries or review.

The tau-bench paper explicitly studies consistency over repeated trials and validates the final environment state. Borrow that reliability question for AutoProteus: does a task work repeatedly, including ordinary corrections and interruption? Distinguish a best-of-many research discovery from a user's first-attempt experience. [Tau-bench](https://arxiv.org/abs/2406.12045)

Maintain separate development feedback and untouched validation sets. Repeatedly revealing every validation failure turns that set into development material. Generated task ideas can enlarge a future suite after review/calibration; they cannot redefine the existing acceptance objective. This extends AutoProteus's current independent-verifier design.

**Suggested sequence.**

1. Preserve the prepared experience comparisons and collect their bounded evidence. Independently summarize the dominant failure classes before selecting new interventions.
2. Prototype failure packets and portable capability contracts using the current graders, traces and inert artifacts. Compare one targeted change with the frozen baseline.
3. Once a viable descendant exists, run the parent-versus-descendant improvement-production test on unseen tasks. Add another model before making a portability claim.
4. Retain a small set of viable variants and test whether parent selection from that archive helps within the same total budget.
5. Expose tested setup profiles and a durable improvement workflow when the underlying checks support them. Keep the simple default path, with research controls available separately.

The immediate research focus I recommend is **failure-guided changes plus an explicit test of later improvement-production ability**. The product focus is **a measured setup profile and recoverable progress toward the user's original task**. The implementation can remain small and model-neutral while those hypotheses are tested.

Implementation anchors: [protocol diagnostic](D:/AI_New/AP/controller/compatibility.py:10), [growth scoring](D:/AI_New/AP/controller/evaluation.py:71), [protected regressions](D:/AI_New/AP/controller/evaluation.py:307), [checkpoint forking](D:/AI_New/AP/evaluations/generalization.py:171), [staged growth](D:/AI_New/AP/evaluations/generalization.py:199). The host controller, credentials, VM policy, quotas and independent evaluator remain outside the editable seed.
