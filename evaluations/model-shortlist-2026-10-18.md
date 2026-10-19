# Model shortlist for the October 18 overnight screen

Planning shortlist only. No downloads, frozen queues, schedules or model runs were started.

| Priority | Model | Role and reason | Readiness |
| --- | --- | --- | --- |
| Control | Qwen3.5 9B, existing verified Q4_K_M checkpoint | Repeatable comparison point against the current starter; historical results cannot substitute for a run on a changed seed. | Existing profile/assets; prepare a fresh plan. |
| 1 | Liquid LFM2.5-8B-A1B | New near-9B candidate focused on local tool use. Different from the FineEnvs LFM2.5 2.6B checkpoint already studied. | [Ollama entry](https://ollama.com/library/lfm2.5); verify exact assets, runtime, template and workload memory before admission. |
| 2 | Ornith 1.5 9B | Current GPU retest of an agent-oriented Qwen-family derivative. Earlier October 12 evidence used CPU inference and an older seed. | [Ollama Q4_K_M entry](https://ollama.com/library/ornith-1.5:9b); compare digests with any existing local copy. |
| Reserve | NVIDIA Nemotron Nano 9B v2, post-trained model | Additional architectural diversity through its hybrid Transformer-Mamba design. | [Official model listing](https://build.nvidia.com/nvidia/nvidia-nemotron-nano-9b-v2/deploy). Conditional on a verified quantized build, Pascal-compatible inference and correct tool parsing. Do not spend the night resolving runtime support. |

Recommended core queue: Qwen control, LFM2.5 8B, Ornith 9B. Admit Nemotron only if its preflight is ready in advance; otherwise leave it for another session. OxCoder/Qwen workflow comparisons are already a separate deferred line of work; do not mix workflow treatments into this model screen.

Use the existing runner's **screen** mode with one exploratory repeat: bounded inference/protocol checks, three basic tasks, hashing and JSON-formatting upgrades, and second extensions only from fully accepted first parents. This does not test CSV and does not establish repeatability. Existing screen gates are two of three basic passes; keep failures and skipped dependent cells visible.

Retain 128 actions, 4,096 response tokens, 30 minutes and 65,536 generated tokens per upgrade attempt. Development/activation share the second-pass allowance. Use one GPU model at a time. Verify memory with realistic prompts, not only model loading. Record publisher sampling, thinking behavior, actual offload and any profile differences; do not force unsupported settings or attribute differences solely to model weights.

The three core profiles have up to 6 hours 36 minutes of basic/upgrade task ceilings if all first parents qualify for growth, plus inference benchmarks, independent grading, model loading and preparation. This is not an elapsed-time guarantee. Reserve time by deferring Nemotron, not by silently truncating attempts or changing acceptance rules.

Freeze the same current starter for all three profiles after ongoing edits are finalized. Prepare new queues under the current runner/source identities; old plans and results remain historical. Do not run navigation, masking, staged-input or other workflow treatments in this screening queue. Rank verified upgrades and completed cumulative workflows before speed.

Sources checked October 18: [Liquid AI release](https://www.liquid.ai/blog/lfm2-5-8b-a1b), [NVIDIA evaluation recipe](https://github.com/NVIDIA-NeMo/Skills/blob/main/docs/tutorials/posts/nemotron-nano-v2-evals.md), [earlier Ornith test](D:/AI_New/AP/evaluations/first-patch-findings.md), [current runner guide](D:/AI_New/AP/evaluations/model-study.md), [current preparation note](D:/AI_New/AP/evaluations/seed-v0.2.0-preparation.md).
