# AutoProteus: current-state review and additional research

Research date: 2026-10-17, America/Regina. Inspected HEAD: `7142f0d` (v0.0.15). Earlier untracked research notes were preserved. This review adds only this document; no source changes, model trials, engine installations or candidate promotions were performed.

## Main conclusion

AutoProteus has a substantial foundation for bounded, independently checked experiments. Its immediate opportunity is to help the selected model spend fewer interactions on navigation, repeated implementation and coordination. More context, another model or a larger framework should be experimental variables, rather than assumed solutions.

The recent evidence distinguishes three problems: writing correct capabilities, finishing the development/activation workflow, and using an already working capability. Those need separate measurements and interventions. The research below supports focused experiments; it does not establish gains on our small local models or reliable recursive self-improvement.

## Current state and fresh validation

- The protected controller owns inference, credentials, VM policy, recovery and independent evaluation. The editable seed runs in disposable, network-free VMs by default. Linux native mode is explicitly selected and has materially different guarantees. See [README](D:/AI_New/AP/README.md).
- Native calls and JSON fallback share tool descriptions. Source edits are exact, bounded and recoverable; incomplete model replies do not execute actions. The default toolset remains small.
- The latest model-study runner freezes inputs and identities, reuses matching calibration, resumes completed queue cells, retains interrupted attempts, and distinguishes partial timing/usage coverage from complete cost. See [runner guide](D:/AI_New/AP/evaluations/model-study.md).
- Qwen3.5 9B's latest exploratory batch accepted 2/3 first upgrades and completed 1/2 staged-growth workflows. CSV defaults and an exact truncation boundary remained defects. One continuation used both tools and produced correct artifacts but exhausted its action allowance instead of finishing. See [Qwen findings](D:/AI_New/AP/evaluations/seed-v0.0.14-qwen9b-findings.md).
- Bonsai's main batch accepted 0/3 first upgrades. A separately labelled diagnostic verified an additional tool while preserving an existing formatting capability, but development still paused. The exact unchanged combined seed later passed a fresh-use task in 71.22 seconds using seven actions. This is evidence of usable cumulative capabilities, not an accepted autonomous two-generation chain. See [Bonsai findings](D:/AI_New/AP/evaluations/seed-v0.0.15-bonsai-findings.md).
- These profiles used different models, runtime settings and attempts; they do not establish a model ranking or causal effect of context, cache precision or timeout changes. Bonsai's longer-timeout diagnostic had no successful call exceeding the original request limit.

I reran the ordinary suite with the project Python: **234 tests, 194 passed, 40 skipped**, 25.364 seconds. Hardware VM tests were explicitly disabled and were not revalidated. The first restricted run had 18 errors and three failures because loopback test connections were denied with WinError 10013; the same suite passed after permission to use its temporary local servers. This is not a newly discovered application regression. The earlier report's hardware results remain historical evidence.

## Recommended directions

### 1. Mask old tool-output bodies while retaining a useful action history

JetBrains' [The Complexity Trap](https://kairos.jetbrains.com/research/articles/the-complexity-trap) compares observation masking with model-generated summaries. Masking older observation bodies was competitive with summarization in its coding-agent experiments, with lower overhead. Crucially, the useful retention window depended on the scaffold; copying its numerical settings between agents could degrade results. Its evaluated models were substantially larger than our local 4B/9B profiles.

Our [context builder](D:/AI_New/AP/autoproteus/agent.py:160) already preserves original/latest human instructions and trims older action/result groups when its conservative estimate fills. The new treatment would preserve a compact record of earlier actions while replacing large old result bodies with explicit omission markers. Keep the full journal, recent exact results and activation state. Preserve valid call/result grouping through native conversion, and never present an omitted result as complete.

Use the existing history experiment to test retrieval of omitted facts. Observation masking is separate from the prepared usage-anchor estimator: one changes retained content, the other estimates its size. Test them separately before combining them. Stable-prefix cache effects, repeated reads and lost-result errors belong in the measurements.

### 2. Improve feedback after edits before adding another editing format

[SWE-agent](https://arxiv.org/html/2405.15793v1) studies the interface seen by the model: efficient actions, concise feedback and immediate visibility of edit results. [Aider](https://aider.chat/docs/more/edit-formats.html) documents model-dependent editing formats and the extra output required by full-file replacement; its [lint/test workflow](https://aider.chat/docs/usage/lint-test.html) provides immediate error feedback.

AutoProteus already has exact replacement, conflict locations and useful error hints. A narrow additional experiment is to return the changed span plus bounded surrounding text after a successful edit. That may avoid a separate verification read without weakening exact matching. A separate Python-only treatment could return syntax diagnostics, executed in the guest, with the edit's acceptance/rollback behavior explicitly specified. Syntax checking cannot establish functionality.

Measure extra output and tool latency against avoided model requests. Do not run an entire test suite after every partial edit, silently apply approximate patches or assume a format that suits one model suits all models. Diagnose actual edit failures before adding another tool.

### 3. Let a task create temporary helpers, then earn persistence through reuse

[Live-SWE-agent](https://arxiv.org/html/2511.13646v1) uses task-specific executable scripts as custom tools while solving issues. Its reported improvements concern software benchmarks and much stronger models; runtime tool synthesis there is not proof of indefinite recursive improvement.

A separate [2026 tool-making study](https://arxiv.org/html/2607.08010v2) compiles repeated procedures into validated, versioned tools with compact outputs. It reports a deployed alarm-triage application, but explicitly retains human decisions about the action space and promotion. Generalization beyond that application remains unestablished.

For AutoProteus, distinguish a temporary task helper from a persistent seed capability. A guest script can inspect a repository or process data through existing commands without first modifying the running tool registry. Keep terminal permission explicit. Compare a supplied helper, model-authored helper and existing-tool baseline separately: supplied code is assistance, not autonomous tool invention.

The existing `programs` study already supplies an inspection helper. Extend that line of evaluation before inventing a plugin system. A persistent candidate should demonstrate repeated utility, correct behavior and lower total cost including construction and checks. Temporary script use alone does not count as a seed upgrade.

[Recursive Language Models](https://arxiv.org/html/2512.24601v1) provide another reason to inspect large material programmatically rather than repeatedly place it all in context. Their experiments use frontier models, show long cost tails, and do not make recursive inference equivalent to self-improvement. Start with bounded inspection programs. Recursive model calls would require separately designed broker controls and aggregate budgets; they are not available merely because guest Python can run.

### 4. Strengthen the tests that judge new tools and recovery sequences

[EvalPlus](https://arxiv.org/html/2305.01210v1) expands test inputs under explicit contracts and also finds faulty reference solutions. [MuTAP](https://arxiv.org/html/2308.16557v1) uses surviving implementation mutants to expose weak tests. These are different techniques: mutating inputs exercises more cases; mutating implementations asks whether a test suite detects a particular defect.

The current calibrated controls for byte/character limits, path escape and one-extra-row truncation are a good base. Add a small explicit fault matrix: missing default, boolean accepted as integer, exactly-limit versus limit-plus-one, failed writes changing input, and a stub reporting success without changing output. Confirm which independent case rejects each fault. Equivalent or irrelevant mutants should not inflate a score. Use reviewed oracles; candidate code and generated faulty variants execute only in guests. Never redefine the contract from a candidate's own schema.

[Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html) generates sequences of actions and reduces failing examples. This extends the earlier property-testing suggestion to lifecycle behavior: edit, checkpoint, stop, resume, activate, retry and recover. Compare against a small state model and assert that committed files and source identities remain consistent, incomplete actions are not credited, and interrupted study cells are not silently rerun. Existing deterministic tests remain; generate cheap scripted sequences first and replay selected cases in VMs. No production dependency is required.

### 5. Make phase completion easier, while retaining independent acceptance

This is a refinement of the previous durable-workflow recommendation, prompted by new local evidence. The current controller already supplies active-source state; concise activation is implemented, tested, and used by the model-study growth path. Recommending concise handoff alone would therefore repeat existing work.

The next question is whether a narrowly scoped stage objective helps the model stop development once it has a checkable submission. Experiment with an explicit implementation/check/submission phase followed by a use-only phase, retaining the original user requirements and shared allowance. The host freezes the submitted source, checks it independently and owns activation. A model's ready message does not approve itself.

Use the same frozen source and task to compare context variants; fresh-use success versus a long paused development run is not a controlled estimate. Record readiness, verified functionality, requested activation, actual activation, correct use, explicit finish and human interventions separately. Do not rescore paused trials as completed, relax focused-test requirements or silently grant fresh budgets.

For the normal interface, consider displaying the existing distinction between model-reported completion and independently checked results beside the status/artifacts. [Session rendering](D:/AI_New/AP/web/app.js:174) currently uses a general Finished label, while check results are in a separate panel. This is a product proposal, not evidence that ordinary completed tasks have been independently verified.

### 6. Broaden evaluation toward useful original tasks

The current sixteen ordinary tasks cover several useful behaviors; upgrade studies remain concentrated on a few file capabilities. Add a small offline set where the final user artifact matters: reconcile several local data files, produce a source-grounded report with exact totals, or recover an interrupted multi-file transformation. Include corrections and preserved inputs. Score outputs independently and track required user interventions.

[Terminal-Bench](https://www.tbench.ai/) is a useful precedent for independently checking end-to-end environment work. Borrow task-packaging ideas rather than claiming compatibility with its complete suite. AutoProteus's 2 GiB guest, bounded artifacts and network-free operation exclude many external benchmark environments. New local tasks are adaptations, not official benchmark scores. Reserve unseen task families for validation rather than repeatedly selecting changes on the same contracts.

## Suggested order

| Step | Work | Decision it supports |
| --- | --- | --- |
| 1 | Classify saved failures by code correctness, tests, editing, context, inference and phase completion; expand targeted grader controls offline. | Select a treatment for an observed bottleneck. |
| 2 | Run the already prepared navigation comparison, or a separately frozen edit-feedback pilot if redundant post-edit reads dominate. | Reduce costly interactions without new permissions. |
| 3 | Compare ordinary trimming with observation masking; reuse the omitted-fact retrieval check. | Determine whether leaner context preserves capability. |
| 4 | Evaluate phase-focused completion using unchanged verified source, then fresh upgrades. | Separate using good tools from producing and activating them. |
| 5 | Repeat promising changes on a second model and unseen task families. | Establish tested portability and practical value. |

Choose one treatment at a time, preserve failed/interrupted attempts and total search expense, and report matched-success costs with coverage. These proposed experiments were not run for this review. The highest-priority new research lead is observation masking; the highest-priority existing line to execute is reducing navigation/coordination overhead. Larger-scale recursive search becomes more informative once those basic workflows finish reliably.
