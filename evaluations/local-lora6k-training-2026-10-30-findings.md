# Local-Qwen 6K LoRA: one epoch complete

The pilot completed its one frozen epoch on **93 training examples**, followed
by all **27 held-out validation examples**. The final checkpoint is the only
candidate; no generation results selected it. All supervision remained the
reviewed original local-Qwen outputs. No new teacher, Sol data, prompt-token
supervision, truncation, oversampling or extra epoch was introduced.

| Held-out metric — lower is better | Baseline | Final epoch | Relative change |
| --- | ---: | ---: | ---: |
| Token-weighted NLL | 0.137606 | 0.111867 | −18.7% |
| Workflow-bucket macro NLL | 0.323746 | 0.260512 | −19.5% |
| Source-lineage macro NLL | 0.134891 | 0.115651 | −14.3% |
| Ordinary-task NLL | 0.062956 | 0.086299 | +37.1% |

The frozen validation gate passed. Ordinary-task loss and the single held-out
development-check example worsened; improvements are not uniform. These are
teacher-forced losses on a small, lineage-separated familiar-family validation
set. **Better autonomous seed editing or completed workflows is not established.**

## Execution and recovery evidence

The GTX 1080 Ti run used the prepared 6,144-token NF4/FP32, rank-8/alpha-16,
all-32-layer setup, CPU embedding/checkpoint inputs and chunked 64-target loss.
All 93 committed update IDs match the frozen order, without extra/skipped
updates. Each recorded all 496 gradient tensors finite. The final step-0093
checkpoint and its adapter/optimizer/RNG/cursor payload hashes verified.

The supervised worker ran **4,845.8 seconds (80.8 minutes)**, including loading,
the numerical agreement control, baseline validation, optimization, checkpoint
saving and final validation. No safeguard tripped. Across 851 resource samples:

- Peak sampled shared GPU memory: **3.916 GiB**, below the 4-GiB allowance.
- Minimum sampled free physical RAM: **7.885 GiB**, above the 6-GiB floor.
- Minimum sampled commit headroom: **13.955 GiB**, above the 4-GiB floor.

These sampled values do not establish unsampled peaks. The owned training
worker closed successfully before inference work began. There was no guard
relaxation, training restart or base-weight replacement. Earlier preflight
failure and the Windows desktop-owner correction remain separately recorded.

## Authorized inference follow-up

The user explicitly authorized live-model tests afterward. A separate F32 GGUF
LoRA export passed static mapping: 248 projection pairs, 21,639,168 finite
elements, rank 8, alpha 16 and matching base tensor shapes. Production native
chat and raw completion probability controls both verified an enabled-adapter
effect and exact disabled → enabled → disabled restoration, with slot erasure.
This establishes overlay application, not task-quality improvement.

The first study publication stopped before any agent trial because its checksum
used the training helper's ASCII JSON serialization rather than the study's
Unicode serialization. The failed launch and original plan/source remain
unchanged. A corrected publication reuses the exact cases, starter, limits and
sampling; this infrastructure event is not a model failure or a repeated trial.

The matched screen is now running: base Q6 versus the final one-epoch overlay,
five fixed first/second-extension families, one repeat per arm, common first-use
contracts, native production adapter, 128K context, 4K responses, temperature
0.6 and thinking off. It retains shared 128-action/65,536-token/3,600-second
feature-task allowances, first-use gating, no human repairs and no automatic
public correction. Functional completion and native invocation remain separate.

No persistent deployment, merge, installed-model change, cloud/API call or
additional training is authorized by this follow-up. Task results and failure
audits remain pending; do not interpret validation gains as acceptance scores.

Private evidence: `.data/lora6k-pilot-20261029/post-training-20261030/`, including
`TRAINING-CLOSED.json`, `training-verification.json`, `adapter-preflight.json`,
the preserved failed publication in `study/`, and active `study-v2/`.

The [gated task screen has now closed](local-lora6k-seed-comparison-2026-10-30-findings.md).
The base completed two of five scheduled chains. The LoRA's correct artifacts
but 3/5 explicit ordinary completions failed the predefined retention gate, so
its seed-editing trials were not run. Validation gains did not establish
improved autonomous workflows; no adapter promotion is supported.
