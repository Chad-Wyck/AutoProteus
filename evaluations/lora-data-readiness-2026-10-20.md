# LoRA data readiness: 20 October 2026

**Assessment: enough recorded material to justify curating a small, targeted LoRA pilot. A training-ready dataset has not yet been established, and the archive does not establish enough diversity for broad recursive-improvement training.**

This was a read-only audit of existing local evidence, apart from saving this note and a metadata inventory. No model training, inference, candidate execution or application changes were performed. Project HEAD was `cbc238b` (v0.3.0). Counts are a point-in-time snapshot; four model sessions had a running status and were not assessed as completed examples.

## Inventory

| Recorded material | Count | Interpretation |
| --- | ---: | --- |
| Unique saved session IDs | 2,865 | Includes scripted verifiers, source snapshots and calibration. Eight additional session files repeated an existing ID. |
| Model-labelled sessions with response events | 684 | Provider is Ollama or hosted; demo, offline-test and baseline labels excluded. These labels and journals identify recorded model attempts; endpoint execution was not independently re-audited. |
| Model response events in those sessions | 15,386 | Includes failures, repairs, repetitions and incomplete work. |
| Completed sessions with journals stable during reading | 493 | Completion alone is a model status, not independent acceptance. |
| Model sessions linked to a completed, passing task result | 399 | At least one scoped recorded task result passed. This does not imply every intermediate action was correct or that a complete growth workflow passed. No linked sessions had conflicting pass/fail task records in the inspected reports. |
| Exact distinct request/response-content pairs in those passing sessions | 5,789 | An extraction upper pool before quality, protocol, length and semantic-duplication filtering. Native raw tool calls and other response fields need appropriate conversion; this count is not a finished dataset size. |
| Accepted upgrade reviews linked by `submission.session` to a model session | 44 | Also 44 distinct candidate source hashes. This is a linkable subset of historical reviews, not an exhaustive total. Acceptance of an extension does not establish activation and later use. |
| Distinct literal initial task texts across the 684 sessions | 54 | Repeated tests dominate. This is not a semantic task-family count: source versions, supplied parents, follow-ups and treatments can differ. |

Of the 399 sessions with passing task records, 225 concern five familiar task labels: precise edit, exact file, recovery, bug fix and Unicode. The 44 linked accepted reviews span multiple models, with 14 from the original Qwen 9B Q4 model label and 12 from the newer OxCoder Q6 label. Model aliases and quantizations are not independently different architectures.

Metadata, per-session counts, source paths and report links are saved in `.data/lora-data-audit-20261020/inventory.json`. Raw prompts, responses, credentials and model settings were not exported into that inventory. The scan excluded model/runtime directories and copied trusted runners, and inspected metadata reports without importing project or candidate code. Protected grader sessions were excluded through their demo provider labels. Provider traces outside the guest journals were not exhaustively inventoried.

## What the archive can support

The most credible first target is reliable tool use, precise edits, focused testing and useful recovery. The journals retain request messages, model responses and action results, providing material for selecting successful decisions with their actual preceding context. Logs are richer than aggregate scores.

Complex workflow evidence is thinner. The latest OxCoder comparison independently verified six formatter extensions, but only one completed activation and final use in the required order. The other five should not become positive examples of that complete workflow. See [the original findings](seed-v0.3.0-feedback-findings.md). Older regraded or reused candidates must retain their original verdicts and the separate scope of their later evidence.

Before training:

1. Link selected examples to their task result, source version and acceptance scope. Review intermediate actions even within passing sessions; remove incorrect, redundant and obsolete-protocol targets. Failed attempts can supply repair scenarios only when a corrected continuation is separately established.
2. Group near-duplicate tasks, related source lineages and repeated model attempts. Keep each group entirely within one training or evaluation partition. Familiar test-night tasks used for training become training material; claims of improvement require fresh, untrained tasks and independent grading. Never turn protected grading fixtures or answers into training targets.
3. Preserve required tool observations as context and format assistant/tool-call targets for each selected base model. Apply training loss to the intended assistant outputs; shared examples do not make an adapter portable across different bases.
4. Start with a few hundred carefully selected decisions if curation supports that yield. Treat this as an experimental starting size, not an established sufficiency threshold. Measure unseen-task performance against the original base and recheck the final merged/quantized artifact before promotion.

Small curated datasets can be informative: [LIMA](https://arxiv.org/abs/2305.11206) studied 1,000 curated examples on a 65B model. Its result is not a sample-size guarantee for AutoProteus, 9B models, LoRA or agent workflows. [TRL's supervised fine-tuning documentation](https://huggingface.co/docs/trl/main/en/sft_trainer) describes conversational datasets and assistant-output training; the archive still needs deliberate preprocessing and selection.
