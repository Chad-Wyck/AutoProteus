# OxCoder checkpoint audit — 21 October 2026

**The currently published official OxCoder checkpoint has no tensor-content differences from the pinned official Qwen3.5 9B reference beyond reproducible precision conversion.** This changes the premise of using it as a distinct foundation for the next AutoProteus LoRA experiment. Training and seed-comparison trials were not started while the user's preference was requested.

## Direct measurements

The official `OrionLLM/OxCoder-9B` repository was pinned at revision `07ba04e2149bace1b43c66448471a70378a7a708`. Its `model.safetensors` is 18,819,722,360 bytes, SHA-256 `d4fca6821fe35b46e684ab88217ec25cdbfcdf9fa208c01110be95a200fcc33b`. The complete download was checked against the published LFS checksum. Configurations, tokenizer and chat template were also pinned and verified. No remote model code was executed.

Reference: the previously verified `Qwen/Qwen3.5-9B` instruction checkpoint, revision `c202236235762e1c871ad0ccb60c8ee5ba337b9a`, used for the first LoRA pilot. This is not the raw pretrained `Qwen3.5-9B-Base` edition.

Every byte of every published OxCoder tensor was compared on the CPU, in bounded memory:

| Comparison | Tensors |
| --- | ---: |
| Same shape, dtype and bit-identical contents | 712 |
| Identical after explicit float32-to-bfloat16 rounding of the Qwen reference | 48 |
| Content differences beyond that precision conversion | **0** |
| Total published tensors compared | **760** |

The compared tensors contain 9,409,813,744 elements. The 48 precision conversions were checked with finite float32 input and explicit round-to-nearest-even conversion; both tensor hashes were recorded after conversion. The comparator included known-value and changed-value controls. Shape mismatches, missing reference tensors, unexpected dtypes and truncated reads would fail the audit.

OxCoder omits 15 `mtp.*` tensors present in the reference. The complete model artifacts are therefore not byte-identical files, and this finding does not say their configurations, templates or precision are identical. It establishes that all **published OxCoder tensor contents** are accounted for by the pinned Qwen reference plus the stated precision conversion. It supplies no evidence of a distinct learned fine-tune in this release.

## Relation to earlier inference results

The previously tested cached GGUF packages differ materially:

| Cached Q6 package | Qwen | OxCoder |
| --- | ---: | ---: |
| File bytes | 7,958,818,848 | 7,359,267,840 |
| Chat-template bytes | 7,756 | 16,289 |
| Stored tensors | 442 | 427 |
| Q6_K tensors | 142 | 250 |
| Q8_0 tensors | 68 | 0 |
| Float32 tensors | 232 | 177 |

Their chat templates have different hashes; 108 shared tensors use different storage types. The Qwen package also contains the extra MTP block. These metadata differences do not identify a cause of the earlier performance differences, and the present audit does not independently reconstruct the provenance of every cached GGUF payload.

Earlier accepted extensions and saved correct outputs remain valid observations of those specific inference packages and settings. They should not establish a learned-weight advantage for OxCoder. A new matched before/after LoRA test on the OxCoder release would still be meaningful for that release's template and deployment package, but would not compare an independently fine-tuned foundation against Qwen.

## Publisher evidence

The repository's [weight-export discussion](https://huggingface.co/OrionLLM/OxCoder-9B/discussions/3) reports a similar tensor comparison. The author acknowledged a possible final save/export problem and said they would inspect the exported checkpoint path. That prompted this independent audit; the counts above come from the actual pinned local files, not from copying that report. The current repository revision was checked rather than assuming the older discussion still applied.

No intent, training-history or unpublished-checkpoint claim follows from this artifact comparison. A corrected release or original trained adapter would need a fresh identity check.

## Preparation retained

- The verified full checkpoint is preserved at `E:\AutoProteus-training\oxcoder-lora-20261021\checkpoint` (about 18.84 GB including tokenizer/configuration files). Existing Qwen weights and adapters were preserved.
- Private evidence is under `.data/oxcoder-lora-20261021/`: pinned public metadata, download receipts, representative samples, the full per-tensor comparison and inference-packaging comparison.
- An initial workflow review pool identifies **52 source-linked positive targets from seven independently completed workflows**, including seven activation requests. It preserves the recorded wire prompts and catalogs. These remain closely related formatter tasks and candidates from the same supplied hashing parent, not seven independent task families or lineages.
- The activation contexts range up to 117,405 bytes and do not fit the prior 32,000-byte preparation limit. No silent context truncation or training release was performed. Any bounded-context transformation needs to be explicit and reviewed; tokenizer and memory readiness remain unqualified for this new pool.
- No GPU training, LoRA export, live seed trials, application changes, commit or push were performed during this audit. The user was asked whether to continue the OxCoder deployment-package experiment or use the workflow-focused Qwen route.

[Machine-readable audit](oxcoder-checkpoint-audit-2026-10-21-results.json) contains all tensor hashes and packaging measurements. It excludes raw workflow prompts and training targets.
