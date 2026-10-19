# AutoProteus repository watchlist

Established 19 October 2026, America/Regina. Eight repositories: three from the user's earlier research links and five additional candidates. This is an ideas watchlist, not a dependency or installation plan. New additions received an initial source/documentation screen, not a full audit or reproduced benchmark.

## Shortlist

| Repository | Origin | What is worth watching for AutoProteus |
| --- | --- | --- |
| [Harness2](https://github.com/google-research/harness2) | User link | Lessons tied to observed edits; contrasting workflow/domain proposals; execution evidence; retaining or rejecting composed changes. |
| [Hermes Agent](https://github.com/NousResearch/hermes-agent) | User link | Reusable procedures, exact history retrieval, context accounting, recoverable sessions and provenance of learned content. |
| [FineEnvs](https://github.com/adithya-s-k/FineEnvs/tree/main/05-multi-harness-rl) | Code behind the user's multi-harness RL article | Model/harness portability, fixed held-out tasks, faithful inference traces and correctness-gated efficiency. |
| [GEPA](https://github.com/gepa-ai/gepa) | Additional repo; related paper discussed previously | Failure-guided proposals, evaluation adapters, bounded search and retaining candidates that work on different task subsets. |
| [mini-SWE-agent](https://github.com/SWE-agent/mini-swe-agent) | Additional repo; appeared in earlier harness research | A small readable agent loop, model-specific message handling, trajectory inspection and simpler operating procedures. |
| [ShinkaEvolve](https://github.com/SakanaAI/ShinkaEvolve) | Additional repo | Archives of alternatives, deliberate parent selection, diverse proposals and efficient verifier-backed code search. |
| [Inspect AI](https://github.com/UKGovernmentBEIS/inspect_ai) | Additional repo | Comparable model profiles, evaluation records, sample-level diagnosis and accessible result inspection. |
| [llama.cpp](https://github.com/ggml-org/llama.cpp) | Additional upstream watch; complements the user's inference-engine video | Native tool compatibility, context/cache behavior, model support and measured improvements relevant to Windows/Pascal/local 9B use. |

The FineEnvs article directly links to the repository above. Its companion [chapter README](https://github.com/adithya-s-k/FineEnvs/blob/410fb3454a903646f814bb752513c56fed3eae78/05-multi-harness-rl/README.md) identifies the training/evaluation code and distinguishes historical results from newer interfaces. Keep the [original article](https://huggingface.co/spaces/FineEnvs/multi-harness-rl) as supporting context. Training model weights is a separate possible future direction from AutoProteus's present harness editing.

The earlier YouTube link remains a discovery source in the [video review](D:/AI_New/AP/evaluations/inference-engines-video-research-2026-10-17.md). Its many hardware-specific projects are not all added to this short recurring list. Revisit a specialist fork when it has concrete evidence for the current machine and workload.

## Most useful ideas from the additional repos

**GEPA — diagnose a failure before proposing a change.** Its adapter separates evaluation outputs/scores from the trajectory evidence used for reflection. Its current scope includes code and other textual artifacts, not only prompts. For AutoProteus, try one bounded ticket containing the observed failure, relevant calls, a proposed cause and a falsifiable change. Keep correctness and cost distinct, and preserve untouched validation tasks. This builds on existing failure packets and graders rather than requiring DSPy or GEPA as a runtime dependency. [Adapter contract](https://github.com/gepa-ai/gepa/blob/f1cfdee2856e9dc4b5b4dc5cc2e391d0aa20d819/src/gepa/core/adapter.py), [overview](https://github.com/gepa-ai/gepa/blob/f1cfdee2856e9dc4b5b4dc5cc2e391d0aa20d819/README.md)

**mini-SWE-agent — keep the core easy to inspect and improve.** The loop delegates message formatting and observation formatting to the model adapter, executes actions through the environment and persists the trajectory. It also records format errors and limits. Study whether clearer feedback and fewer procedural steps help AutoProteus's small models. Its shell-centric interface is an experimental comparison, not a reason to remove the current structured tools or VM boundary. [Core loop](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py)

**ShinkaEvolve — preserve useful alternatives.** It keeps a population/archive and exposes parent-selection and island strategies, with local-model guidance. For AutoProteus, a small archive could preserve a reliable general seed and a useful specialist instead of overwriting every predecessor. Initially select parents explicitly and run serially. Evolving a scored scientific program is not itself evidence of improving the agent's future improvement ability; that needs a separate ancestor/descendant test. [Overview and configuration](https://github.com/SakanaAI/ShinkaEvolve/blob/8adc053a2ce4511ad2ac310e004c530a73fb974a/README.md)

**Inspect AI — make results easier to understand.** It supports multiple model configurations and structured evaluation logs with an interactive viewer. Borrow ways to connect a failed score to the exact sample, model configuration and transcript. AutoProteus already has frozen plans, queues and independent feature checks; improve the presentation and interoperability before replacing its evaluator. Model-graded judgments cannot substitute for the existing deterministic acceptance checks. [Model configuration](https://github.com/UKGovernmentBEIS/inspect_ai/blob/4aa17c03d738a31b16cf08a63d9a953279c2f6a8/docs/models.qmd), [evaluation logs](https://github.com/UKGovernmentBEIS/inspect_ai/blob/4aa17c03d738a31b16cf08a63d9a953279c2f6a8/docs/eval-logs.qmd)

**llama.cpp — watch the practical cost of the whole tool loop.** Its server documents compatible model endpoints, tool calling, constrained output and speculative decoding. A runtime change is useful only when the selected quantization, prompt lengths and actual tool exchanges remain correct and faster on the relevant hardware. Check prompt processing and total task time as well as generation speed. AutoProteus's current research runtime is a separately pinned PrismML build; an upstream release is not an instruction to replace it. [Server documentation](https://github.com/ggml-org/llama.cpp/blob/1b29621bacc6a446bd523fc790316a24a06e886f/tools/server/README.md)

Near-term priority: Harness2/Hermes/GEPA for improvement lessons and feedback; mini-SWE-agent for simplicity. Inspect supports diagnosis, llama.cpp supports affordability and compatibility, and ShinkaEvolve becomes more useful when several viable seed variants exist. These priorities are assessments of fit, not measured AutoProteus performance gains.

## Recurring review

Default cadence: Mondays at 09:00 America/Regina. The accompanying chat automation owns the schedule; the JSON file below is a comparison baseline, not a scheduler.

- Read the current AutoProteus README and newest local findings before judging relevance. Other chats may be updating the project; preserve their work.
- Check releases, default-branch changes and relevant merged fixes against the recorded baseline. Inspect source/tests behind important claims. Prefer demonstrated behavior to announcement language.
- Look for portable self-improvement, small-model workflow completion, capability retention, honest evaluation/costs, context correctness, recoverability and simpler user interaction.
- Ignore routine dependency churn, unrelated integrations, star counts and performance numbers from incompatible hardware. Use bounded investigation; a full code audit or benchmark reproduction is separate work.
- Report only a meaningful new idea, relevant fix/regression, or access failure that requires action. For each finding, give the source, what changed, why it matters, limitations and the smallest useful next comparison. Deduplicate previously reported findings.
- Update only this watchlist, its state file and dated research notes when needed. Do not install, run external code, start inference trials, change application defaults, push commits or contact maintainers.
- Retain the last successfully reviewed baseline when access or review is incomplete; record the gap. Do not label an unchecked revision fully reviewed.

## Recorded state

Latest completed research round: [19 October review against the v0.2.1 working tree](D:/AI_New/AP/evaluations/research-round-2026-10-19.md). It recognizes the fixture correction already in progress and the completed v0.2.0 model/navigation screens. Priority is structured test-repair feedback, evidence-linked lessons and full-profile qualification. All eight heads and latest visible release identifiers were unchanged; this was a deeper scoped source review. The [manifest](D:/AI_New/AP/evaluations/research-round-2026-10-19.json) records source scope and local file hashes. Adaptive-GEPA is a paper-level follow-up, not an added repository.

[Machine-readable comparison baseline](D:/AI_New/AP/evaluations/repository-watch-state.json) records default-branch commits and latest visible release metadata observed on 19 October 2026. A recorded head means identified for future comparisons, not a comprehensive review of every change leading to that head.

Earlier detailed reviews: [Harness2](D:/AI_New/AP/evaluations/harness2-research-2026-10-19.md), [Hermes](D:/AI_New/AP/evaluations/hermes-agent-research-2026-10-15.md), [multi-harness RL](D:/AI_New/AP/evaluations/multi-harness-rl-research-2026-10-15.md), [broader research](D:/AI_New/AP/evaluations/research-directions-2026-10-16.md).

Local scheduled work requires the computer to be on and the desktop app running. [Official scheduling documentation](https://learn.chatgpt.com/docs/automations?surface=app)
