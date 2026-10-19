# AutoProteus research round: current gaps and useful ideas

19 October 2026, America/Regina. Compared the actual working tree with eight tracked repositories, including selected implementation and test sources. Also reviewed a recent Adaptive-GEPA preprint. This round adds research notes and monitoring records only: no external code executed, installations, model trials, candidate promotion or application changes.

## Current conclusion

**Prioritize better repair feedback and evidence-linked lessons, then qualify the complete model/runtime profile.** The newest local evidence does not support adding a broad agent framework, a default outline tool, or more automatic retries.

The local baseline is Git HEAD `aed23d3b73d304c32ae86a9b247fc947c7f4e502`, with existing uncommitted **v0.2.1** changes. Reading HEAD alone would miss the protected-fixture correction. Reading only older preparation notes would also miss the completed v0.2.0 model and navigation screens. The [review manifest](D:/AI_New/AP/evaluations/research-round-2026-10-19.json) records the inspected local file hashes and upstream snapshots.

## Already present versus still experimental

| Area | Actual local status | Research implication |
| --- | --- | --- |
| Smaller source modules; edited-tool invocation independent of tests; JSON argument files | Implemented in v0.2.0 | Do not propose another invoker or source split. [Preparation](D:/AI_New/AP/evaluations/seed-v0.2.0-preparation.md) |
| Native-message context preparation and human-message preservation | Implemented at the protected provider boundary | A second generic context-overhead fix is unnecessary. [Provider preparation](D:/AI_New/AP/controller/providers.py:157) |
| Protected history fixtures accounting for larger advertised catalogs | Present in the uncommitted v0.2.1 changes, with enlarged-catalog, unbounded-output and irreducible-overflow controls | Recognize the correction already underway; it is not a new recommendation from this research. [Fixture controls](D:/AI_New/AP/tests/test_context_fixtures.py) |
| Raw provider requests/responses, cutoff classification, bounded response repair and no execution of partial actions | Implemented; research tracing remains opt in | Reuse the observations instead of building another recorder or adopting another repair loop. [Provider recording](D:/AI_New/AP/controller/providers.py:210), [seed repairs](D:/AI_New/AP/autoproteus/agent.py:73) |
| Frozen plans, trusted/source identities, calibrated checks, durable queues and explicit retries | Implemented | No need to replace the experiment runner. [Plan identities](D:/AI_New/AP/evaluations/model_plan.py:143), [queue/cache](D:/AI_New/AP/evaluations/study_support.py) |
| Agent-reported completion distinguished from scoped seed checks, including stale-source reports | Implemented in the UI/controller | Any progress display should extend these receipts, not duplicate them. [UI](D:/AI_New/AP/web/app.js:190), [verification status](D:/AI_New/AP/controller/evaluation.py:399) |
| Outline navigation | Available as a copied-seed experiment; six-attempt pilot completed | Both arms accepted 1/3; no attempt called the outline tool. This does not establish a benefit from using outlines. |
| Procedures, historical retrieval, usage anchors, edit/syntax feedback, masking, focused phases and withheld final inputs | Separate opt-in experiment preparations; some mechanics already implemented there | Availability is not demonstrated model benefit or default product behavior. [Experience comparisons](D:/AI_New/AP/evaluations/experience-study.md), [workflow comparisons](D:/AI_New/AP/evaluations/workflow-experiments.md) |
| Loaded-versus-followed procedure evidence | Already distinguished in experimental learning records | Procedure reads are tracked; following the advice remains explicitly unmeasured. [Learning records](D:/AI_New/AP/evaluations/experience.py:169) |
| Automatic transferable lesson extraction and a selectively retrieved improvement library | Not in the normal seed | A genuine remaining opportunity, initially small and bounded. |

The completed [v0.2.0 findings](D:/AI_New/AP/evaluations/seed-v0.2.0-local-findings.md) are the main evidence for prioritization. Several candidates passed direct tool checks but failed their own tests or workflow requirements. OxCoder Q6 and a separate Qwen Q6 follow-up each earned one accepted first extension. Their second candidates passed new/retained feature checks and fresh public calls, but two protected context fixtures blocked verification. Neither achieved a fully accepted growth chain in that study.

The trusted-only catalog diagnostic reproduced the fixture problem without executing a candidate implementation. The working-tree correction addresses that diagnosis. It does not retrospectively prove activation, final task use, or a complete autonomous chain.

## 1. Use failure evidence to improve test repair

GEPA's adapter explicitly separates scores, outputs and trajectories from the component-specific evidence used to propose a change. Its mutation implementation skips reflection when trajectories are absent rather than inventing a diagnosis. This is a useful design discipline for AutoProteus. [Adapter](https://github.com/gepa-ai/gepa/blob/f1cfdee2856e9dc4b5b4dc5cc2e391d0aa20d819/src/gepa/core/adapter.py), [reflection stages](https://github.com/gepa-ai/gepa/blob/f1cfdee2856e9dc4b5b4dc5cc2e391d0aa20d819/src/gepa/proposer/reflective_mutation/reflective_mutation.py#L425)

A focused AutoProteus experiment would turn an observed development failure into a bounded repair ticket:

- Exact source/profile identity and relevant action/result IDs.
- What failed: behavior, the model's own test, invocation, transport, context, or stage ordering.
- The smallest relevant traceback or output and the public contract.
- One proposed cause, one change to try and what would disprove the explanation.

This is more specific than repeating the whole task after every failed test. Recent examples include a model-written test calling an absent `Workspace.format_json` method, an undefined `Cancelled` name and faulty expectations. Those failures should not automatically trigger a rewrite of a behaviorally correct tool. Conversely, a green candidate suite cannot overrule independent contract failures.

The existing seed already tells the model to repair concrete failures, and already has a test-independent invoker. The new variable would be **structured selection of the relevant failure evidence**, not another generic instruction to test. Keep hidden validation answers outside the ticket; use public development feedback and reserve untouched tasks for qualification.

GEPA's evaluation-call budget does not itself cover proposer cost: its implementation deliberately accounts for those separately. AutoProteus should retain its whole-attempt accounting and include ticket generation/reflection in reported cost. [Budget ownership](https://github.com/gepa-ai/gepa/blob/f1cfdee2856e9dc4b5b4dc5cc2e391d0aa20d819/src/gepa/oa/budget.py)

## 2. Store a few lessons whose applicability can be checked

Harness2's reflection distinguishes effects of individual edits from the quality of the selected deliverable. It allows confounded conclusions and no durable entry when there is insufficient evidence. Its library requires usable experience before saving an adopted harness. [Reflection prompt](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/prompts.py#L1105), [library](https://github.com/google-research/harness2/blob/1cfe254e8d25b15f37048c3730134686abe60335/harness2/core/library.py#L106)

Adapt this into a few ordinary files, each with a cue, a proposed procedure, run/source references, observed outcomes and limits. Separate an extracted hypothesis from a lesson that has helped on fresh tasks. Retrieve a small relevant subset with current file tools. Do not append every failure to the permanent system prompt.

One initial hypothesis could concern repairing tests against the actual public invocation interface instead of inventing convenience methods. Another could address unnecessary reinspection after a successful check. Their usefulness still needs measurement.

The existing procedure experiment supplies a human-authored recipe and already records whether it was read. That is a useful control, but it is not autonomous lesson learning. Compare a fixed recipe with a versioned, evidence-derived lesson treatment before introducing automatic background review.

Hermes is useful for mutation provenance and recoverable learned content. Its ledger records before/after manifests; that is an audit trail, not an acceptance verifier. Preserve the same distinction in AutoProteus. [Skill ledger](https://github.com/NousResearch/hermes-agent/blob/c0015464f0f40d52c5702a84cf58e70361f4a04c/tools/skill_ledger.py)

## 3. Qualify the complete inference profile

mini-SWE-agent has focused tests ensuring malformed responses remain inspectable and output truncation is not misreported as a formatting mistake. AutoProteus already implements those broad protections. The useful next application is a replayable profile-qualification set built from actual observed failures. [Malformed-response regression](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/tests/models/test_format_error_response_persistence.py), [truncation regressions](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/tests/models/test_truncation_finish_reason.py)

llama.cpp documents native format handlers and a generic fallback, with different efficiency implications and template overrides. A model name or compatible endpoint alone therefore does not identify the behavior being qualified. [Tool-call formats](https://github.com/ggml-org/llama.cpp/blob/1b29621bacc6a446bd523fc790316a24a06e886f/docs/function-calling.md)

AutoProteus already freezes extensive model/runtime settings in research plans and has a two-request connection diagnostic. Extend qualification, rather than replacing these: repeat small tool/result exchanges, include recovery from a rejected action, then a modest growing-history case. Bind the result to weights/quantization, engine/build, chat template, protocol, reasoning/sampling settings, context and tool catalog. Preserve the user's protocol choice.

This is motivated by the LFM Q8 native preflight passing once and later failing fresh tool-format calls. Its fast generation does not resolve that transport problem. It also argues against treating the Qwen precision screens as a clean precision-quality comparison: hardware placement was incompletely observed and desktop GPU load changed.

Offline response replay can test parsing without inference; live repeated exchanges test the actual model/server combination. Keep those claims separate.

## 4. Extend existing verification into clearer capability progress

Inspect's structured evaluation records and Hermes's mutation history suggest a practical convenience improvement: connect each capability to a small, versioned progress record. [Inspect evaluation logs](https://github.com/UKGovernmentBEIS/inspect_ai/blob/4aa17c03d738a31b16cf08a63d9a953279c2f6a8/docs/eval-logs.qmd)

The current app already distinguishes reported completion and independent seed checks. A future per-capability view could additionally distinguish declaration, edited-copy check, active source version and observed use on the requested task. “Declared” must not imply callable; a checker invoking a tool must not imply the model selected it after activation. Changed source invalidates applicable checks.

This addresses both the LFM candidate advertising an unknown dispatcher tool and the two-tool candidates whose grader-scripted public calls passed without final model-driven use. Reuse existing source identities and receipts. For unfamiliar tools, display the scope actually checked rather than inventing a universal certification.

## 5. Keep alternative variants as a later, measured step

ShinkaEvolve separates verified program populations and sampling strategies, and has optional embedding/model-based novelty filtering. The archive idea is useful; the filtering and ensemble machinery would add cost and dependencies before AutoProteus has enough independently accepted variants to justify them. Existing exact-identity caching already solves part of duplicate work. [Island selection](https://github.com/SakanaAI/ShinkaEvolve/blob/8adc053a2ce4511ad2ac310e004c530a73fb974a/shinka/database/island_sampler.py), [novelty filtering](https://github.com/SakanaAI/ShinkaEvolve/blob/8adc053a2ce4511ad2ac310e004c530a73fb974a/shinka/core/novelty_judge.py)

A new paper reference, **Adaptive-GEPA** (30 September), studies routed specialist programs with a Qwen3-8B executor. It uses GPT-5.5 for reflection, a fixed four-family mixture and one main seed; test curves were visible during method development, and scored-call counts do not equate total compute. Its description/program pairing and behavior-based branch alignment are useful ideas for future reuse. It also reports identical serialized candidates receiving different scores: a higher score alone need not mean a new capability. Treat this as a paper-level lead, not proof of local-model autonomous improvement; no associated implementation was validated here. [Paper and limitations](https://arxiv.org/html/2609.38762v1)

Start with a few explicitly chosen, independently checked variants and preserve the selected model. A router, parallel population or stronger teacher is not a prerequisite for the first lesson experiment.

## Evaluation choices to preserve

FineEnvs retains graded wrong answers and reports ungraded coverage separately. Inspect documents repeated samples, metrics and retry policies. Those are useful references, but their retry defaults should not replace AutoProteus's explicit retained-attempt policy. Recovered results are not fresh repetitions; a best-of-many success is not first-attempt reliability. [FineEnvs evaluation](https://github.com/adithya-s-k/FineEnvs/blob/410fb3454a903646f814bb752513c56fed3eae78/05-multi-harness-rl/eval/README.md), [Inspect metrics](https://github.com/UKGovernmentBEIS/inspect_ai/blob/4aa17c03d738a31b16cf08a63d9a953279c2f6a8/docs/metrics.qmd), [retry defaults](https://github.com/UKGovernmentBEIS/inspect_ai/blob/4aa17c03d738a31b16cf08a63d9a953279c2f6a8/docs/eval-sets.qmd#L110)

All eight watched default-branch heads and latest visible release identifiers matched the starting watchlist. These findings are from deeper inspection and updated local evidence, not newly shipped upstream releases. This was a scoped static review, not a full diff/security audit or an executed test of those projects.

## Recommended next comparison

1. Finish validation of the existing fixture correction. Recheck unchanged saved candidate bytes under a separately identified grader. Preserve original verdicts. A later final-use trial is a new reuse experiment, not retroactive proof that the original attempt completed within its original allowance.
2. On a corrected frozen baseline, compare ordinary upgrade guidance with one bounded failure ticket/lesson treatment, keeping the selected local profile and allowances matched. Measure accepted upgrades and test-repair work. Use repeated balanced cells and unfamiliar contracts; changing both feedback and a new runtime would prevent attribution.
3. Promote a useful lesson only after success beyond the case that produced it. Then test whether a descendant creates later accepted upgrades more reliably than its ancestor. Adding a tool and improving future improvement ability remain separate outcomes.
4. Reuse the existing phase, procedure and supplied-parent machinery wherever it already answers the question. These are research recommendations; this round launched none of them.
