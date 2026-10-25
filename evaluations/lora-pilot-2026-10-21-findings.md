# First AutoProteus LoRA pilot — 21 October 2026

The three-pass training run and fresh matched base-versus-adapter comparison completed. The selected adapter achieved **3/3 complete staged-input growth workflows**, compared with **2/3 for the fresh base control**. Both scored **0/3 complete visible-input workflows**. This is an encouraging pilot result, with too few trials to establish a repeatable benefit.

Importantly, **all 12 formatter implementations passed the independent feature checks**, protected seed regressions and hashing-retention checks. The difference in clean verified extensions came from two base candidates including disallowed files in their submitted source packages. The remaining gap concerns completing the requested workflow, rather than writing a working formatter.

Machine-readable evidence: [results](lora-pilot-2026-10-21-results.json). No application source, default settings or active seed changed. Nothing was committed or pushed.

## Training and checkpoint selection

- Model: official instruction/post-trained **Qwen/Qwen3.5-9B**, revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`. This was not the raw `Qwen3.5-9B-Base` checkpoint.
- Data: **98 training examples, 18 validation examples**, with full tool context. All 98 training examples were used exactly three times, in the frozen order: **294 updates**, without truncation, interruptions, numerical failures or operator corrections.
- Training examples came from verified ordinary file tasks. Source-upgrade/growth examples were excluded from training targets. The five ordinary evaluation task families overlap training or validation; their results are regression checks, not held-out generalization evidence.
- Fresh rank-8, alpha-16 LoRA across all 32 text decoder layers: **21,639,168 trainable parameters**. Base weights were frozen; NF4 with FP32 computation, batch one, gradient checkpointing, peak learning rate `5e-5`, ten warmup updates and linear decay. The frozen input embedding stayed on CPU to preserve GPU headroom.
- Full training worker time, including loading, evaluation and saves: **4,604 seconds / 76.7 minutes** on the GTX 1080 Ti. Mean update: **14.46 seconds**. CUDA update peak allocated: **8,352 MiB**. Ten-second monitoring sampled a peak of **8.68 GiB dedicated GPU memory**, 66 MiB shared GPU memory and a minimum of 11.58 GiB available host RAM. Sampled peaks are not instantaneous maxima.

| Checkpoint | Token-weighted validation loss | Teacher-forced token accuracy |
| --- | ---: | ---: |
| Untrained model | 0.22114 | 92.73% |
| Pass 1 | 0.18344 | 93.43% |
| **Pass 2 — selected** | **0.17731** | **93.60%** |
| Pass 3 | 0.18103 | 93.77% |

Selection followed the rule fixed before training: lowest token-weighted validation loss. Pass 2 reduced that loss by **19.82%**. This is a teacher-forced loss measurement on 18 historical Unicode examples, not a 19.82% increase in task success. Pass 3 had higher token accuracy but worse loss, so it was not selected. No real-task outcomes were used to select the checkpoint.

The selected adapter is saved at:

`E:\AutoProteus-training\lora-pilot-20261020\training\20261021T094702Z\epoch-2`

Its inference export is:

`E:\AutoProteus-training\lora-pilot-20261020\training\20261021T094702Z\selected-adapter-f32.gguf`

The export is **86,591,264 bytes** (about 82.6 MiB), SHA-256 `630294da6ec5bec2b0e78a1e3ce5ccdf60d59d2a29211838b73d917ad3bd1444`. **No full model merge was required.** All three adapter checkpoints and recovery states remain available.

## Fresh matched comparison

Both arms used the same published **Qwen3.5 9B Q6_K**, PrismML runtime, 128K context, 4K responses, temperature 0.6, thinking disabled and standard native host adapter. The private server loaded the selected adapter once; its verified scale was zero for the control and one for the treatment. Slot caches were explicitly erased when switching arms. Deterministic raw and production-chat probability probes confirmed an adapter effect and exact restoration of the disabled control.

Each arm received three repeats of each protocol, starting from the same supplied hashing-capable parent. The model had to add `format_json`, retain hashing, request activation, use both capabilities after activation, write the correct audit files, and finish. This measures a **directed second extension from a supplied parent**, not autonomous discovery or a complete model-written first-to-second growth chain.

The visible-input protocol supplied `inventory.json` immediately and required preserving it during development. The staged-input protocol withheld that final input until activation. These are different instruction conditions and are reported separately.

Each attempt had 128 actions, 65,536 generated tokens and one 30-minute deadline shared across development, independent grading, retention and final use. Model and treatment order were alternated. All 24 scheduled cells completed once: two benchmarks, ten ordinary tasks and twelve growth attempts. There were no candidate repairs by the operator or task-infrastructure failures. No growth attempt reached its time deadline.

| Independent outcome | Base: visible | LoRA: visible | Base: staged | LoRA: staged |
| --- | ---: | ---: | ---: | ---: |
| Formatter feature checks passed | 3/3 | 3/3 | 3/3 | 3/3 |
| Existing hashing retained | 3/3 | 3/3 | 3/3 | 3/3 |
| Clean verified source package | 1/3 | 3/3 | 3/3 | 3/3 |
| Input protocol respected | 1/3 | 1/3 | 3/3 | 3/3 |
| Activated | 0/3 | 1/3 | 2/3 | 3/3 |
| Correct final files, regardless of route/stage | 2/3 | 2/3 | 2/3 | 3/3 |
| **Complete extension-and-use workflow** | **0/3** | **0/3** | **2/3** | **3/3** |

All five complete workflows used both required tools directly. A secondary static inspection of saved command strings found no additional complete workflow missed by the frozen invocation detector. Model-written code was never imported or executed on the host during this audit; artifact checks read saved bytes.

### Individual attempts

| Model | Input protocol | Repeat | Clean extension | Complete workflow | Minutes | Main remaining issue |
| --- | --- | ---: | --- | --- | ---: | --- |
| Base | Visible | 1 | Yes | No | 8.37 | Changed final input before activation; did not request activation |
| Base | Visible | 2 | No | No | 7.63 | Included `development/test_input.json` in candidate; changed final input early |
| Base | Visible | 3 | No | No | 11.71 | Included `inventory.json` in candidate; did not request activation |
| LoRA | Visible | 1 | Yes | No | 15.05 | Activated and produced correct files, but used generic Python instead of the required capabilities |
| LoRA | Visible | 2 | Yes | No | 20.38 | Changed final input before activation; did not request activation |
| LoRA | Visible | 3 | Yes | No | 7.10 | Changed final input before activation; did not request activation |
| Base | Staged | 1 | Yes | No | 13.10 | Exhausted the action allowance before requesting activation |
| Base | Staged | 2 | Yes | **Yes** | 10.19 | — |
| Base | Staged | 3 | Yes | **Yes** | 7.28 | — |
| LoRA | Staged | 1 | Yes | **Yes** | 12.59 | — |
| LoRA | Staged | 2 | Yes | **Yes** | 9.11 | — |
| LoRA | Staged | 3 | Yes | **Yes** | 13.01 | — |

The two rejected base source packages still passed all 20 independent formatter checks, all 50 protected seed regressions and the earlier-capability checks. Their disallowed files explain the **4/6 versus 6/6 clean-extension** aggregate; that difference should not be presented as a formatter coding advantage.

Both arms passed the inference benchmark and all five ordinary tasks. The additional app protocol diagnostic was advisory under the frozen admission rule: the base failed that diagnostic; the adapter passed with one format repair and two response retries, not on its first pass. These results do not establish a reliably supported first-launch app profile. The standard host connection was nevertheless used throughout the growth trials without tool-ID rewriting or JSON fallback.

## Efficiency

These totals cover growth attempts only, including failed workflows, grading wall time and final use. All 795 model calls have complete input-token, output-token and call-time measurements and complete traces. Qualification, preflight and benchmark overhead are outside these totals. Logical prompt-token sums include cached prefixes and do not measure uncached compute or money.

| Growth cost | Base: visible | LoRA: visible | Base: staged | LoRA: staged |
| --- | ---: | ---: | ---: | ---: |
| Model calls | 138 | 218 | 236 | 203 |
| Reported input tokens | 2,093,799 | 4,760,606 | 3,878,803 | 3,320,059 |
| Reported output tokens | 27,331 | 33,904 | 29,719 | 31,194 |
| Total wall minutes | 27.71 | 42.54 | 30.57 | 34.71 |

The adapter did not demonstrate a speed improvement. It used fewer calls across all staged attempts but took more wall time. Among the two matched successful staged repeats, it was faster with fewer calls once, then slower with more calls once. Reading loops remained: the adapter's third staged success used 83 development read actions. The small sample does not support an efficiency claim.

## Reproducibility, limits and next use

- Frozen application commit: `4d3c8f3707fc69754a86dbf580528798f831c718` (v0.3.0). Starter fingerprint: `870a6b523a5d771cc931eca8b7a343e35d27a92aa35943cfcccf6a0d4f6dc304`; supplied hashing-parent fingerprint: `ad5fbe47ceede347406880a6378ee008d970e92b5481ab5ca5e17078c62fde33`.
- The final audit verified unchanged starter, trusted checks, runtime assets, base GGUF and selected adapter/export hashes. Every activated candidate retained its submitted source during final use.
- An initial pre-task deployment attempt failed because this runtime requires `--slot-save-path` before accepting cache-erasure actions. No task cells ran in that attempt. A recorded amendment enabled cache actions and added the production-chat adapter preflight before launching the completed comparison. Tasks, seed, sampling, budgets, checkpoint selection and graders were unchanged. Failed infrastructure evidence remains saved separately.
- Fresh scale-zero controls share the loaded adapter's memory footprint and runtime. Historical controls did not have that exact setup and remain separate. Training used official HF NF4 weights; deployment used the existing published Q6 GGUF plus an F32 adapter. Upstream ancestry metadata in the GGUF does not prove exact identity with the original HF checkpoint.
- This is one familiar prescribed extension, one parent and three repeats per condition. Ordinary tasks overlap the small training pool. There is no unseen-task, broad self-improvement, cross-model or model-agnostic adapter claim.
- Training completed at **5:03 AM Regina time**; the final comparison finished at **7:28 AM**, while this chat was usage-limited. The jobs required no model-task intervention. Final checks found no training, inference or QEMU processes remaining; free space was **10.88% on D:** and **17.51% on E:**.

Keep this adapter as an experimental checkpoint. The useful next qualification is a frozen repeat on unfamiliar extensions and visible-input workflows, alongside a fresh disabled-adapter control. Additional verified training data should represent activation, post-activation use and finishing across varied seeds; this pilot's ordinary file-action targets did not directly train that workflow. The current evidence does not justify making the adapter a default or changing the seed around its results.

Private evidence, checkpoints, source snapshots and raw journals remain under `.data/lora-pilot-20261020/training/20261021T094702Z/`; the completed comparison is `inference-study-002/`. The machine-readable report includes individual scores, measurement coverage, hashes, cleanup and the deployment amendment, without the private training examples or full prompts.
