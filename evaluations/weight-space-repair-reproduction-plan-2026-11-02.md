# Qwen 0.8B weight repair reproduction plan

Prepared November 2, 2026 for the AutoProteus development branch.

**Implement an optional, resumable research runner that applies the published Qwen3.5-0.8B repair and compares it with the original model on this Windows/GTX 1080 Ti machine. Start by reproducing the patch and its behavioral effect. Rediscovering the repair with an editing agent is a separate later experiment.**

Original research: [Sparks of Weight-Space Programming](https://rikiyat.github.io/blog/weight-space-programming/).

The initial development scope is preparation and implementation. Downloads, model loading, GPU inference, an editing-agent session and benchmarks are later execution stages. Preserve existing development changes and running work. No application default, production model, existing LoRA or seed change is part of this experiment.

## 1. Reproduction target and source material

Use the published **p50c** edit from Experiment 8, pinned to logs repository revision **4d09ba6d6a7e891dd8063974dfe81b3d78e3494f**. The website source reviewed was RikiyaT/RikiyaT.github.io revision e93997d3ce6a975e866c1dd1bc7f96b6bd392a11.

- [Experiment protocol and caveats](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/README.md).
- [Final edit explanation](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/runs/p50c/final_answer.md).
- [Exact edit manifest](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/runs/p50c/edit/manifest.json) and the adjacent edit.npz.
- [Patch reconstruction script](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/code/apply_edit.py) and its required [st_numpy.py helper](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/code/st_numpy.py).
- [Evaluation code](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/code/evaluate.py), [profiles](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/code/profiles.py) and [answer extraction/checking](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/code/mathqa.py).
- [Published baseline scores](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/eval/unedited/merged.json) and [edited scores](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/eval/p50c/merged.json).
- [Text-only model configuration](https://github.com/RikiyaT/lm_understand-logs/blob/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math/base_model/Qwen3.5-0.8B-text/config.json).

Base checkpoint: **Qwen/Qwen3.5-0.8B**, Hugging Face revision **2fc06364715b967f1860aea9cf38778875588b17**. Keep the original BF16 checkpoint immutable. Do not substitute another revision, instruction variant, GGUF, quantization or our Qwen3.5 9B model.

Published reference results, averaged across samples:

| MATH-500 measure | Base | p50c |
| --- | ---: | ---: |
| Accuracy | 7.9% | 48.1% |
| Responses reaching 32,768 generated tokens | 93.0% | 33.05% |
| Mean generated tokens | 30,868.4345 | 22,037.1475 |

Treat these as reference values, not local acceptance thresholds. The original evaluation used BF16/vLLM. Our proposed FP32/Pascal implementation is a runtime and precision port: checkpoint equality can be exact while output sequences and scores differ.

There are two distinct goals:

1. **Published-patch reproduction:** reconstruct the exact evaluated tensors, then test whether they reduce looping and improve accuracy locally.
2. **Discovery reproduction:** give an editing agent access to weights and controlled practice feedback, and see whether it discovers a useful repair. This is not achieved by applying the published patch.

## 2. Hardware and execution path

Recorded hardware: GTX 1080 Ti, 11 GiB VRAM, SM 6.1; i5-11600K, 6 cores/12 threads; approximately 31.8 GiB usable physical RAM; Windows 11; recorded NVIDIA driver 581.29. Refresh these observations before a live run.

The prior local LoRA environment recorded Torch 2.6.0+cu124 and Transformers 5.20.2. These are candidate versions to inspect, not a proven 0.8B inference lock. Read the actual installed versions, device support and available space before choosing a separate experiment environment. Do not upgrade the production or LoRA environment in place.

Recommended first inference route:

- Native Windows PyTorch CUDA with the installed Transformers implementation of Qwen3.5; explicitly use the text-only causal model.
- Preserve upstream model.language_model.* tensor identities in the canonical artifact. Use a checked, documented name mapping if the runtime expects model.*. Audit tied embeddings and the output head.
- Load BF16-stored values as **FP32 for computation**, batch size one, one model loaded at a time, evaluation mode and inference/no-grad context.
- Use a supported ordinary attention path; do not require FlashAttention, BF16 CUDA kernels, tensor cores, Triton or a new custom kernel. Verify the Qwen linear-attention fallback too. Prefer the existing efficient SDPA path if numerically qualified; use eager only when its memory use fits.
- Generate incrementally using KV/recurrent caches. Bound prompt processing and output projection memory; do not retain full-vocabulary logits or hidden states at every prompt position. Any chunking must have a short numerical control.
- No optimizer, backward pass, bitsandbytes/NF4, LoRA or MTP/speculative decoding.

The original evaluator constructs a BF16 vLLM model and imports private weightenv helpers. It is not a standalone Windows reproduction command. Its top-level docstring also describes an older Qwen3 experiment. Follow Experiment 8 and the **think35** protocol, not that historical default.

The 0.8B model's FP32 parameter storage is roughly 3.2 GB by parameter count; caches, activations, the vocabulary and Windows desktop allocations add overhead. Qualify fit at the actual generation length. Do not claim that 32K is proven to fit because short generation works.

## 3. Deliverables for the development branch

Keep public code and synthetic controls under evaluations/ and tests/. Proposed entry point: evaluations/weight_repair.py. Names and commands below are an interface specification, not an implemented runner.

| Operation | Contract |
| --- | --- |
| prepare | Build a manifest and frozen sample order using local metadata; no network, ML import, GPU/model loading or inference |
| verify | Check available files, tensor headers, configuration, source/dependency identities and manifest consistency without inference |
| acquire | Explicit download step for pinned public model, patch and benchmark assets |
| rebuild | CPU-only application of the published patch to a separate artifact, with full tensor audit |
| preflight | Explicit live-model numerical, memory, sampling and generation readiness checks |
| run / resume | Execute one explicitly selected frozen phase under cumulative resource allowances |
| report | Read saved records only; recompute scores, coverage, intervals, timing and limitations |

Use a private run directory such as .data/weight-repair-20261102/run-001/. Retain sources, dependency lock, asset hashes, rendered prompts, token IDs, raw responses, scores, runtime statistics and interruption records there. Public reports should contain aggregate results and source links, not downloaded benchmark text or weights.

At implementation time record the actual branch, HEAD and hashes of all dirty runner/controller files used. The checkout reviewed for this plan was HEAD **2a7176599813a219002a3695b8887f905d112124**, with concurrent changes to seed and evaluation/accounting code. Do not reset, stage or fold those changes into this research patch.

## 4. Rebuild and validate the exact repair

Acquire only the pinned model assets and required upstream files. Review scripts as data before execution. Record download lengths and SHA-256, including edit.npz; reject a moving revision or incomplete file.

Run the upstream CPU-only reconstruction logic using apply_edit.py plus st_numpy.py. Write a new checkpoint; never target the base file. The helper can consume the public release's single safetensors file, which also contains non-text tensors. For the local text-only model, copy only required text tensors through an explicit audited mapping, using the released text configuration and tokenizer/template.

The two edited tensors are:

| Tensor suffix under model.language_model. | Shape | Expected edited BF16 tensor SHA-256 |
| --- | --- | --- |
| layers.15.mlp.down_proj.weight | 1024 × 3584 | 82e2d733ea64feaeb4af93a1e065641d3df98b494a8b7576ef2f52e90fe2ee53 |
| layers.19.mlp.down_proj.weight | 1024 × 3584 | 8ef3c61bc36af113ad58e89dbb0a4a14dcba5a45cb750c15ab515c82ddd12eb2 |

Check both base hashes against the upstream manifest before applying the patch. After reconstruction require:

- Both canonical edited tensor hashes match exactly.
- Exactly two tensors differ; every other tensor, shape and dtype matches the base.
- The patch targets 64 columns in each tensor. The BF16 bit differences total **130,188 entries**, distinct from the 131,072 touched entries quoted in the article.
- All values are finite; embeddings, output head and final norm remain unchanged.
- FP32 runtime values equal the canonical BF16 values promoted to FP32; hash them separately without confusing their bytes with BF16 hashes.
- Loading the original again restores its identity and a fixed-input numerical control after loading the edit. Clear all inference caches between arms.

The complete safetensors file need not have an identical whole-file hash to an upstream export with different header ordering. Compare canonical tensor bytes, not serialization order alone.

## 5. Match the evaluation protocol

Freeze these settings in both arms:

| Setting | Value |
| --- | --- |
| Thinking | Enabled through the pinned chat template |
| User text | Problem, newline, then: Please reason step by step, and put your final answer within \boxed{}. |
| Temperature / top_p / top_k | 0.6 / 0.95 / 20 |
| Presence penalty | 1.5 |
| Maximum new tokens | 32,768, including thinking and answer |
| MATH-500 final evaluation | All 500 problems, four independently sampled responses per problem per arm |
| Score | Mean correctness across all samples; not best-of-four or pass@4 |
| Context | Full rendered prompt plus the entire output allowance; upstream used 34,816 total capacity |
| Reasoning cleanup / stop | Preserve raw text and actual EOS/length status; no repetition-triggered early exit |

Presence penalty is not the multiplicative repetition_penalty setting. Transformers may require a custom logits processor. Match the original runtime's treatment of generated-token presence, penalty ordering, temperature and filters. Pin or test any interpretation that is not verified against upstream. Prompt-only tokens must not acquire a generated-token presence penalty. Test positive and negative logits, repeated tokens, prompt-only tokens, EOS and tokenizer special IDs.

Use the pinned tokenizer, chat template and generation configuration; freeze whether special tokens are skipped in the grader's decoded view. Save both raw token IDs and the exact decoded grading text. Never truncate the input to fit, silently disable thinking, lower max_new_tokens or add a finishing reminder.

Port the upstream extraction rule: final boxed answer with matched braces and the same handling of reasoning text; no final answer means incorrect. Use pinned math-verify **0.9.0** and its compatible dependencies if they resolve on this environment. Verify an alternative dependency version before changing the lock. Include equivalence cases for fractions, algebra, sets/intervals, nested boxes and malformed/no-box answers.

Match the original scoring rule for length-limited generations; record correctness and cutoff independently rather than inventing an extra penalty. A timeout or killed worker is an incomplete infrastructure observation, not an EOS, token-limit result or ordinary wrong answer.

Pin dataset revision and hashes during acquisition. Preserve MATH-500 unique IDs and all 500 rows. Any practice set used for implementation must come from train data and exclude final test overlap. The published patch is fixed: do not adjust it after looking at local benchmark answers.

Use stable per-problem/sample RNG identities, isolate RNG state for each request, and record the derivation. Same seeds do not imply matching draws across FP32/Transformers and BF16/vLLM. Counterbalance base/edited order in fixed blocks; reload and clear caches at arm changes. Do not reuse a result from a different model, prompt, dtype, engine, sampler or source hash.

## 6. Staged execution and cost limits

**Stage A — CPU artifact checks.** Reconstruct and audit the patch. Test parsers, sampling, checkpoint mapping, resume and resource supervisor using synthetic inputs. No live editing agent or benchmark generation.

**Stage B — hardware readiness.** After explicit live-run authorization and when other GPU work is idle, load one model and check finite logits, a short deterministic response, a fixed teacher-forced probe and original → edited → original restoration. Then test two preselected training-split math prompts per arm at the full 32,768-token allowance, batch one. This establishes observed memory and speed; it is not a benchmark result. Start with a two-hour cumulative readiness allowance and a 45-minute request watchdog. If a guard prevents completion, retain partial evidence and stop; do not change scientific settings to fit.

**Stage C — exploratory behavioral comparison.** Use a fixed random sample of **16 MATH-500 problems**, chosen and saved before any generation, one response per arm. Use the unchanged published patch and full protocol. Record all 32 request slots and missing observations. This can show a local signal, not reproduce the full 7.9%/48.1% scores. Use an eight-hour cumulative allowance and the readiness-qualified request watchdog. Do not select the examples that happened to improve.

**Stage D — fuller replication.** Prepare a separate manifest for all 500 problems × four samples × two arms, only after reviewing readiness, pilot evidence and the projected duration. Reuse pilot records only if every identity and sample rule matches; otherwise keep them separate. A new run budget is required; no automatic escalation from eight hours to an unlimited run. Optional GSM8K and IFEval come later, with separate plans matching their original sample counts and graders.

Runtime planning matters. The published MATH-500 mean lengths imply approximately **105,811,164 generated tokens** for the full paired comparison. At a hypothetical sustained 100 tokens/s that is about **294 hours**; at 30 tokens/s, about **980 hours**, before loading and grading. These are arithmetic illustrations, not measured speed predictions. The 16-problem pilot implies roughly 846,489 tokens at the same means, about 2.35 hours at 100 tokens/s or 7.84 hours at 30 tokens/s. The original model's looping is the phenomenon under test, so it cannot be shortened silently.

After Stage B, replace illustrations with measured tokens/time, memory and a conservative full-run projection. A useful outcome may be a faithfully reconstructed patch plus a bounded local pilot, with the full benchmark deferred for cost. Label that scope accurately.

## 7. Resource ownership, stopping and recovery

Proposed local limits, to freeze before running:

- Begin with at least 8 GiB free dedicated VRAM, 8 GiB available host RAM and 20 GiB free experiment-disk space, plus three idle GPU observations. Recheck actual owners; Windows may not report every owner.
- During execution retain at least 6 GiB free RAM, 4 GiB commit headroom and 5 GiB free disk. Start with a 512 MiB shared-GPU allowance. A trip stops the run; do not silently inherit the LoRA pilot's larger allowance.
- Sample resources externally at least every five seconds and retain peaks/minima as sampled observations. Per-request and phase cumulative time limits include model loading and cleanup; paused downtime is separate.
- Use the existing owned Windows Job Object/cleanup patterns where suitable. Do not blindly reuse a training-update watchdog or the VM's memory quota for this inference worker.
- Stop only this experiment's owned process tree. Never kill unrelated model engines, VMs, browsers or development tests, change drivers, power policy or system-wide CUDA settings.
- Resume only committed, checksummed records with matching model, patch, sampler, dataset, source and environment. Do not count the same request twice. Preserve interrupted requests; replaying an unfinished request must be declared and use its frozen identity, not a fresh favorable sample.
- Save a durable terminal receipt showing stopped owned processes and final resource status. No background timer or unattended scheduler is created by this plan.

## 8. Required controls and interpretation

Implement meaningful offline controls for corrupt/wrong-base patches, an extra edited tensor, NaNs, tied-weight mapping, wrong thinking template, missing presence penalty, strict answer extraction, truncated outputs, request duplication, source mismatch, interrupted commits and cleanup ownership.

For local findings report accuracy, paired gains/regressions, cutoff share, answer omissions, tokens, time to first token, generation rate, full wall time and memory. Keep all scheduled failures and missing records visible. Use confidence intervals with problems as clusters when there are multiple samples per problem; token samples are not independent problem replications.

Decision language:

- **Exact patch reproduced:** both edited canonical hashes and unchanged-tensor audit pass.
- **Local behavior supported:** the fixed pilot shows higher accuracy and fewer cutoffs, with uncertainty reported. Mixed or imprecise results remain inconclusive.
- **Full local replication measured:** all final request slots and scores exist under the frozen protocol, with FP32/runtime deviations disclosed.
- **Not an AP qualification:** even strong math results do not establish tool use, explicit finish behavior, seed extension or cumulative capability retention. Those require a later AP study.
- **Not discovery reproduced:** no claim about agent-led repair follows from replaying the published patch.

Before any quantized deployment, separately compare both models converted through the same GGUF tool/quantization and actual inference backend. First establish the unquantized result. Do not transplant layer numbers or directions into Qwen 9B.

## 9. Optional later discovery experiment

Only after the patch/evaluation path works, consider a separately scoped editor experiment. The published p50c run used 50 batched forward-pass requests, 158 agent turns, 80 Python runs and about 20.3 wall hours including an outage. A single "pass" could generate hundreds of long responses; it is not one cheap model call.

A local editor would be an adaptation, because the original editor was gpt-6-astra. A remote editor entails a distinct provider/cost decision. Do not silently invoke one.

Use independent practice development/confirmation splits; keep benchmark prompts, answers and the published solution out of an editor's visible workspace if testing discovery. Since a developer or assistant may already know the solution, describe this as a solution-withheld experiment rather than a claim of no prior knowledge. Expose only bounded CPU tensor operations and a supervised forward-pass tool. Keep gradients, optimizers, internet and unrestricted host execution unavailable. Count generated tokens, forward calls, agent calls and all wall time, freeze the candidate before final evaluation and retain failed proposals.

The appropriate deliverable from the first development pass is the prepared runner, immutable asset/protocol manifest, offline test evidence and an explicit readiness command. Start live work only when the user subsequently requests it.
