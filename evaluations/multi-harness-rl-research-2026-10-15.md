# Multi-harness RL: implications for AutoProteus

Research date: 15 October 2026, America/Regina. This assessment reads the linked article, its published model and dataset cards, the current OpenEnv Harbor documentation and merged integration, and the local AutoProteus source and findings. It proposes experiments; no model runs, installations or application changes were made.

AutoProteus checkout: HEAD `c60920b11e042d308db73fe826c4e1ca5d2dd03e`, with existing uncommitted changes. Local observations below concern the files as read, rather than an assertion that they all belong to that commit.

**Recommendation: make harness variation and independently verified efficiency part of AutoProteus's experiments first. Add better observation at the existing host inference boundary. Consider model training after those experiments identify a repeatable bottleneck.**

The central distinction is what changes. AutoProteus currently lets an agent edit its harness while model weights stay fixed. Multi-harness RL changes model weights while exposing the model to several harnesses. The latter offers a possible future training method and useful experimental principles; it does not establish reliable autonomous harness improvement.

The article reports that the same base LFM model scored about 62% under Mini-SWE-Agent and 33% under Claude Code. Its final multi-harness and single-harness RL averages were 54.2% and 52.3%; the authors consider that gap within noise. Training used one seed per condition and unequal exposure: 451M versus 162M processed tokens. Each run used two H100s for roughly 46 or 32 hours, excluding evaluation and other overhead. An earlier Qwen experiment suffered a training/evaluation output-cap mismatch. These findings support testing interface fit and deployment constraints, with limited evidence for a general advantage from adding harnesses. [Original experiment](https://fineenvs-multi-harness-rl.hf.space/#conclusions)

The released model card independently documents a 31.1% reduction in tool calls over 356 task/harness pairs solved by both the checkpoint and base model. That is a comparison among shared successes. The reward gives an efficiency bonus only for correct answers; no isolated ablation establishes that the bonus caused the savings. [Released checkpoint and evaluation](https://huggingface.co/FineEnvs/LFM2.5-2.6B-multiharness-RL)

**1. Compare harness configurations with a fixed model. Highest immediate value.**

AutoProteus already compares frozen starter and candidate sources on sixteen ordinary tasks and has independent feature graders. Extend that structure to answer which harness choices help a small model complete an upgrade. Hold model identity, quantization, hardware, sampling, execution policy and budgets constant, and vary one harness choice at a time.

Good questions include native tools versus the existing JSON protocol; current source navigation versus a bounded code-location summary; and current history retention versus a concise continuation from the same accepted checkpoint. These are separate experiments. The generalization runner already contains a matched full-history/concise-context branch design, so that work should be reused.

There is concrete local motivation. The historical v0.6 study records Qwen passing 16/16 ordinary tasks while accepting 0/4 upgrades. Read/search actions consumed 64% of Qwen's and 80% of K2's upgrade actions. The optional role diagnostic also found models that completed a file task but failed to use the required completion protocol. These are specific tested conditions, rather than a current universal verdict on those models. [Upgrade findings](D:/AI_New/AP/evaluations/seed-v0.6-local-findings.md:7), [read costs](D:/AI_New/AP/evaluations/seed-v0.6-local-findings.md:35), [completion diagnostic](D:/AI_New/AP/evaluations/role-check-findings.md:1)

The current seed already supplies reading guidance and progress hints, and it already keeps the opening prompt stable. Those features should be part of the baseline. Repeating those suggestions would overlook changes already present. [Agent instructions](D:/AI_New/AP/autoproteus/agent.py:14), [read hints](D:/AI_New/AP/autoproteus/agent.py:333)

**2. Measure efficiency after independently verified success. Highest immediate value.**

Keep acceptance and correctness explicit. For harness selection, compare accepted-upgrade rates first and resource use second. Track time to first source edit, time to first successful independent check, model requests, input/output tokens where available, tool actions, source bytes returned, context removals and timeouts. Measure calls and tokens on matched successful tasks, and also publish totals over all launched attempts so expensive failures remain visible.

A faster unfinished upgrade should not beat a correct one. Existing protected regressions, independent feature checks, preserved earlier behavior and successful use after activation remain the acceptance evidence. Distinguish a functionally correct implementation from a fully accepted submission, as the project already does.

Treat a crashed VM, inference outage, memory failure or operator stop as its own outcome. Report verified successes per launched attempt as well as accuracy among gradeable attempts. This keeps infrastructure reliability visible while avoiding a false claim that an ungraded output was semantically wrong. The Vultr comparison demonstrates why these distinctions matter. [Recorded infrastructure and task outcomes](D:/AI_New/AP/evaluations/vultr-seed-comparison-2026-10-14.md:66)

If RL is introduced later, use a correctness-gated efficiency term and host-observed costs. Tool count alone can favor packing work into a large script, so retain runtime and token measurements too. This is a proposed AutoProteus objective, not an empirically established fix for its reading loops.

**3. Record model calls at the protected host boundary. High value for diagnosis; a prerequisite for this RL approach.**

OpenEnv's implementation places a recording proxy between harness and model. It validates whether the endpoint supplies exact token IDs and sampling log probabilities; its typed training export also carries loss masks. Unsupported endpoints can still produce evaluation traces. The integration is merged, and current documentation describes TRL 1.15 or later for the experimental worker, superseding the article's older installation note. [Current Harbor documentation](https://huggingface.co/docs/openenv/environments/harbor), [merged integration](https://github.com/huggingface/OpenEnv/pull/1036)

AutoProteus has a useful observation point already: the host provider adapter, after provider message conversion and before response normalization. A host-owned collector could record actual requests and returned responses, timings, finish reasons, source fingerprint, activation lineage and context-policy events. Reconcile calls with journaled action outcomes, including repair requests and cutoffs. Existing reports already retain several identity and usage fields; the addition is a consistent, complete call record and the missing measurements.

The default local adapter uses Ollama's `/api/chat`; pointing that URL at a chat-completions proxy is not a direct substitution. A separate host-side integration or the compatible hosted-adapter route would need validation. Keep the current network-free guest and broker: guest -> existing broker -> host collector/proxy -> model endpoint. The guest needs no new network capability. [Provider implementation](D:/AI_New/AP/controller/providers.py:153), [existing boundary](D:/AI_New/AP/README.md:64)

Current provider code returns text, structured tool calls and usage counters, rather than exact training token traces. A saved journal is useful for diagnosis and curated supervised examples. It cannot reconstruct the original sampled token sequence or behavior probabilities needed for faithful on-policy RL. Parsing and re-encoding can change tokens; the training system must preserve the original IDs and mask tool/context tokens appropriately. [Token-In, Token-Out explanation](https://huggingface.co/blog/huggingface/tito)

**4. Treat accepted AutoProteus versions as a family of training environments. Promising longer-term direction.**

If a model is trained only against the starter interface, its behavior may become brittle when an edited seed changes tools, descriptions or context construction. My inference is that accepted AutoProteus versions could supply useful variation: starter plus accepted historical versions, with a separate unseen version used to measure transfer.

Freeze one harness fingerprint for each rollout. Record the version active after every controller-managed restart; treat an activation as a new segment. Keep gradients and training outside the editable seed. Choose a task and harness before generating a comparison group, so outcomes within that group refer to the same conditions. Evaluate on unseen feature contracts and unseen harness versions, alongside ordinary regressions and staged growth tasks.

Initially vary one dimension, such as tool naming or history policy, rather than changing the model, tools, prompts and budgets together. Preserve interface diversity only when it reflects a useful deployment condition. The goal is reliable use of evolving AutoProteus capabilities, not an arbitrary count of supported frameworks. This is a proposed extension of the research to AutoProteus; the linked experiment did not test self-editing agents.

**5. Reuse released models, traces and task conventions selectively. Medium value.**

The published LFM2.5-2.6B checkpoint is a reasonable candidate for a bounded transfer test, paired with its base and OpenCode-only counterparts under comparable serving conditions. It was trained for data-analysis tasks; AutoProteus seed editing remains untested. The release contains full weights and a saved chat template and uses the LFM Open License v1.0. A small parameter count is not a verified runtime, memory or licensing fit for AutoProteus distribution. [Checkpoint details](https://huggingface.co/FineEnvs/LFM2.5-2.6B-multiharness-RL)

The public SFT dataset preserves prompt, completion, tools, harness/version and teacher provenance. Its structure is useful for designing an AutoProteus trajectory export. [Dataset card](https://huggingface.co/datasets/FineEnvs/SmolDataEnvs-multiharness-sft)

For a future training dataset, prioritize independently verified AutoProteus runs covering exact edits, recovery, boundary cases, new-tool registration and actual use after activation. Successful external trajectories can be studied for navigation patterns, but they exercise different tools. Any transfer benefit requires measurement. The article's mixed SFT results also argue for retaining regression evaluation after fine-tuning. [SFT comparison](https://fineenvs-multi-harness-rl.hf.space/#sft-vs-rl)

Harbor's separation of task, harness and execution backend is useful as an experimental design. AutoProteus can adopt a similar task manifest and outcome schema while retaining its protected VM verifier. A full Harbor/OpenEnv adapter is a later interoperability project: existing benchmark environments and dependencies are not automatically compatible with the diskless, network-free guest.

**Proposed first pilot, without training weights.**

1. Freeze the current baseline and one navigation variant that returns a compact, bounded map of relevant definitions and locations. Validate its ordinary behavior before model trials. Keep context retention and action policy unchanged for this comparison.
2. Use one fixed model/runtime profile and equal context, response, action and time limits. Record the exact configuration. Do not combine the historical 48-action settings with the current 128-action default when assessing improvements.
3. Run two harnesses x three existing independently graded feature contracts x three repeats: eighteen upgrade attempts. Use the existing binary-hash, CSV-preview and JSON-format contracts for development comparison. Alternate harness order and retain every launched attempt.
4. Keep protected tests and graders outside the candidate. Report functional implementations and accepted submissions separately. Check preserved behavior and use through the activated interface where the task requires it.
5. Select by acceptance evidence, then matched-success cost. Eighteen attempts provide a pilot, not a strong reliability estimate. If the result is promising, freeze the variant and evaluate fresh feature contracts that were not used for tuning, then test staged growth from the same saved checkpoint.

This pilot tests whether source navigation is a bottleneck that a harness change can relieve. A failed pilot would still distinguish prolonged reading from output cutoffs, protocol failures, context loss and slow inference. It makes no advance claim that the proposed navigation feature will help.

Source and design anchors: [current comparison service](D:/AI_New/AP/controller/evaluation.py:344), [current result metrics](D:/AI_New/AP/controller/evaluation.py:232), [frozen generalization study](D:/AI_New/AP/evaluations/generalization.py:276), [study findings and qualification limits](D:/AI_New/AP/evaluations/seed-v0.0.11-findings.md:23).
