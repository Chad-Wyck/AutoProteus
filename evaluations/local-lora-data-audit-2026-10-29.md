# Local Qwen LoRA data audit — 29 October 2026

**There is enough promising local evidence for a small, targeted pilot, but this
audit did not release a training-ready dataset.** Complete seed-editing examples
exceed the previous roughly 4K-token training configuration, and workflow/lineage
splitting and final context review remain necessary. The initial audit used CPU
tokenization only. Subsequent user-authorized context curation and bounded GPU
probes are summarized below and in the linked memory report; no full training or
new adapter was produced.

## Conservative primary pool

The audit inventoried 97 saved study plans/queues, then required a loopback
inference endpoint, an allowlisted official Qwen3.5 9B GGUF hash, recorded local
runtime asset verification and an actual loaded model argument bound to that
asset. The selected teacher is the existing Qwen3.5 9B Q6_K. A `hosted` provider
label on these records describes the local compatible API, not a cloud teacher.
Sol's entire study directory was excluded before reading trajectories. No other
external-provider teacher responses were selected.

| Evidence | Count | Meaning |
| --- | ---: | --- |
| Pinned local Qwen attempted cells inspected | 81 | Includes failures, calibration/preflight and corrected runs |
| Independently successful stages admitted | 55 | Scope-specific successes, not 55 distinct capabilities |
| Ordinary task stages | 20 | Five recurring task families |
| Accepted first extension plus correct first use | 16 | Unassisted at the public correction layer |
| Complete-chain second stages | 13 | Earlier behavior retained and correct cumulative use recorded |
| Other verified growth stages | 6 | Supplied-parent/legacy or diagnostic scope; not new full-chain credit |
| Candidate decisions after action-quality filters | 944 | Successful sessions alone did not qualify every action |
| Exact distinct examples | 851 | Exact prompt, target and catalog identity |
| Candidates after a cap of three semantic variants | 638 | 43 sessions and 18 recorded running-source identities |

First and second stages can belong to the same chain. These numbers must not be
added as independent workflows. Different source hashes also do not imply
different task families. Implementation evidence still concerns hashing, JSON
formatting and CSV preview, with five ordinary file-task families.

Other model identities/finetunes, alias-only or missing-runtime records, prior
adapter lineages, interrupted cells, manual candidate repairs and automatically
corrected public finishes were held outside this primary pool. This is a
conservative lower bound on available material, not a finding that all held
models or examples are unusable or unlicensed. Historical grades were unchanged.

## Target quality and provenance checks

The index binds each candidate to the actual recorded request, native tool
catalog, model response and successful action receipt. Host content-addressed
inference blobs reconstruct the exact wire request, including concise activation
context. Transport counters restart on activation/Resume, so counter identity
alone is insufficient. Event UUIDs are not chronological; stage boundaries use
the journal's actual order.

The filters reject malformed/incomplete/batched replies, failed actions,
superseded intermediate writes/edits, unsupported edit fragments, repeated
unchanged reads, empty searches, sensitive/redacted material, and protected
grader/test source content. Terminal programs require separate semantic review;
only observed successful `seed.py check` calls were admitted automatically.
Capability-use targets must match the actual final public input/result. Explicit
CSV limits are excluded from tasks requiring omission of the optional argument.
Completion targets require recorded completion in a qualified stage. Explicit
activation requests are distinguished from questions. Raw thinking is not a
training target. No candidate program was executed or imported on the host.

The nine private audit controls pass, including negative controls for an
external teacher disguised by Qwen asset metadata, a different actually loaded
model, adapter lineage, manual repair, public correction, broken inference blobs,
unproved input preservation and completion labels without independent success.
340 input-file receipts record the audited evidence. The audit is an index over
retained originals, not a self-contained archive if those originals are deleted.

## Exact tokenizer and previous hardware configuration

The existing pinned Qwen tokenizer/chat template was checked by hash and run
offline on the CPU. No model weights were loaded. Every candidate reconstructed
its original audited identity, retained the complete context/catalog and rendered
an unambiguous selected-assistant completion boundary. No context was shortened,
no synthetic observations were added, and no token-ID or training-label dataset
was written.

All 638 examples rendered successfully. Lengths range from 2,007 to 40,957 tokens;
the median is 8,865.

| Complete example limit | Candidates fitting |
| --- | ---: |
| 2,048 | 3 |
| 3,072 | 82 |
| 4,096 | 179 |
| 6,144 | 229 |
| 8,192 | 296 |
| 16,384 | 508 |

At 4K, 127 of 179 examples are reads/listing. Keeping every non-read target and
at most one read per three non-read targets leaves **69 proposed examples**:

- 33 ordinary-task examples and 36 workflow examples.
- 31 post-activation examples: actual capability use, saved outputs and finishing.
- Only five workflow development examples: four reads and one successful check.
- **No workflow source-write or source-edit target fits at 4K with its full
  recorded context.** The four `edit_file` targets in this short subset concern
  ordinary tasks, not seed extension implementation.

The 69 include 14 finish targets and 16 native capability calls (eight hashing,
five formatting and three CSV). They are promising for a finishing/use pilot,
but are not a substantial new seed-implementation dataset. A 4K training window
is distinct from the 128K inference configuration used in the studies. Counts
at longer lengths are not evidence those training lengths fit the GTX 1080 Ti.

## Source provenance and dataset status

The [pinned official Qwen checkpoint license](https://huggingface.co/Qwen/Qwen3.5-9B/blob/c202236235762e1c871ad0ccb60c8ee5ba337b9a/LICENSE)
is Apache-2.0. Its permissive weight license supports adaptation, subject to its
terms and notices. AutoProteus's original project source is
[MIT-0 licensed](../LICENSING.md). These are positive model/software license
findings, separate from target quality, context selection and evaluation design.

All selected assistant targets are recorded local Qwen outputs. The
complete prompts also contain AutoProteus policy text, tool descriptions, task
contracts and source excerpts developed with Codex/OpenAI assistance. Excluding
Sol's assistant replies therefore does not establish that every input is free
of AI-assisted project material. This provenance distinction is not itself a
finding that local Qwen trajectories are prohibited merely because the harness
was developed with coding assistance.

The initial private index conservatively records `training_approved: false`.
That flag must not be presented as a blanket legal rejection of the local
examples. It is also not a released training split: selected contexts, complete
workflow lineages and evaluation separation still require review. The user
subsequently authorized context curation and memory probes, while explicitly
withholding a full training run. Sol interaction logs were removed at the user's
request, and its entire retained study remains excluded from training.

The older 98/18 pilot and 141-example workflow training set were not automatically
merged. Their model mix, source context, prior validation use and teacher/adapter
lineages need the same explicit review. A historical successful training run is
not a permission clearance.

## Recommended next step

Do not start another broad three-pass LoRA yet. Curate a small finishing/use pilot,
or test explicit evidence-preserving context selection for the longer local
seed-editing examples. Any transformed example must retain the original request,
catalog, required instructions and supporting source observations in its audit;
it must not be described as the original full teacher context. This audit did
not make that transformation.

Training and validation must separate complete workflows and generated-source
lineages. Random message splitting would leak near-duplicate solutions. Shared
starter platform code can remain common context, but the three repeatedly tested
capabilities are too narrow to establish general recursive-improvement gains.
Fresh, unfamiliar capability tasks are needed for a later base-versus-LoRA
comparison. More repeats of the same cases would not solve that diversity gap.

## Follow-up context curation and memory probes

Whole-message dependency selection produced 55 local Qwen seed-development
examples: 42 core-module writes/edits and 13 test-file writes. All original
system/user content, target responses and tool definitions were retained, with
closed native tool pairs, source anchors, intervening mutations and imported
helper implementations. Retained/omitted message indices and source hashes make
the changed student contexts explicit. No synthetic observations were added.

The median length decreased from 12,950 to 5,047 tokens; 41 examples fit 6K and
53 fit 8K. Seven integrity controls passed. These are 55 decisions across three
familiar capability families, not 55 distinct independently successful upgrades.
No train/evaluation split or full training run was released.

The [bounded memory report](local-lora-memory-probes-2026-10-29.md) distinguishes
the earlier shared-memory guard stops from the final 4 GiB probe: a 6,043-token
forward completed, but backward exceeded the retained ten-minute update deadline.
No optimizer update completed, no adapter was saved and 8K was not attempted.

Private evidence: `.data/lora-data-audit-20261029/` contains the candidate index,
successful-stage inventory, input hashes, quality rejections, exact token lengths,
read-balanced proposal IDs and audit-control results. No training-approved data,
new adapter or model service was created by the audit. Follow-up private
preparation is in `.data/lora-context-20261029/`. Original Qwen evidence remains;
the separately excluded Sol interaction logs were deliberately removed.
