# Local Qwen LoRA context and memory preparation

**Shorter successful-edit contexts are available, but 6K training is not yet
qualified on the tested GTX 1080 Ti configuration.** The final probe completed
a finite-loss forward pass, then reached its ten-minute update deadline during
backward. No optimizer updates completed, no adapter was saved and no full
training run started. The conditional 8K stage was not attempted.

**Later follow-up:** the [backward diagnosis](local-lora-backward-diagnosis-2026-10-29.md)
subsequently completed two real 6K readiness updates using chunked projection/loss,
with a matched ordinary-loss control. The observations below preserve the earlier
guard-limited probes; they are not the latest readiness verdict.

## Data preparation

The [local data audit](local-lora-data-audit-2026-10-29.md) supplied independently
checked local Qwen3.5 9B Q6 teacher decisions. Selection focused on 55 successful
seed-development writes/edits from 24 sessions and 14 running source versions:
42 core-module decisions and 13 test-file writes. They cover hashing, JSON
formatting and CSV preview, including first and second extensions. They are not
55 independent upgrades or unfamiliar capability families.

Every original system/user message, full selected assistant response and tool
catalog remains unchanged. Relevant whole native exchanges retain observed file
state, subsequent mutations and explicitly imported helper source. Unique edit
anchors, source receipts and retained/omitted message indices are checked.
No observations are invented and no target code is truncated. Student contexts
are explicitly selected versions of the original teacher requests; semantic
review and workflow/lineage-separated evaluation design remain necessary.

| Total token allowance | Candidates fitting | Core-module decisions fitting |
| --- | ---: | ---: |
| 4,096 | 0 | 0 |
| 6,144 | 41 | 41 |
| 8,192 | 53 | 42 |

Median length decreased from 12,950 to 5,047 tokens. The final selected contexts
range from 4,188 to 9,677 tokens. Seven integrity controls passed. Actual pinned
Qwen tokenization masks prompt positions and supervises only the selected local
assistant response. No train/validation split has been released. Sol's entire
retained study and generated artifacts are excluded; its interaction logs were
removed separately. No raw conversations, token datasets or weights accompany
this public report.

## Bounded GPU checks

Hardware: GTX 1080 Ti 11 GiB, approximately 32 GiB host RAM, Windows WDDM. The
existing offline Qwen3.5 9B HF checkpoint and training environment were reused:
Torch 2.6.0+cu124, Transformers 5.20.2, PEFT 0.21.2 and bitsandbytes 0.50.2.
Batch size is one, with NF4/FP32 computation, rank-8 adapters on all 32 text
decoder layers, a frozen FP16 vocabulary, CPU input embedding, pinned-CPU saved
checkpoint inputs and the previously checked efficient-SDPA/GQA compatibility
path. Only selected supervised positions reach the output projection/loss.

Each stage permits two disposable optimizer updates and no adapter export. The
selected 6K cases contain 6,043/789 and 5,606/1,569 total/supervised tokens. The
8K stage is conditional on two complete 6K updates with finite losses/gradients
and a witnessed optimizer change. Ordinary desktop apps remained open.

| Shared GPU allowance | Outcome |
| --- | --- |
| 512 MiB | Guard stops during loading or first forward; no update |
| 2 GiB | First forward stopped at 2,050 MiB shared allocation; no update |
| 4 GiB | Forward completed; backward reached the ten-minute update deadline |

These are host policy stops, not proof of absolute hardware capacity. A shared
allocation counter alone does not identify harmful paging or its cause. A
process-local allocator split-size experiment increased loading pressure and
was not promoted; the relaxed probes use the default allocator.

For the final 4 GiB probe:

- The 6,043-token forward took 18.382 seconds, with finite loss 0.1123273.
- Shared GPU allocation peaked at a sampled 2,546 MiB, below the allowance.
- At least 9,115.95 MiB physical RAM and 15,913.40 MiB commit headroom remained.
- No CUDA out-of-memory error was reported; no complete backward/update finished.
- The second 6K case and 8K stage were not launched.

The retained safeguards require at least 6 GiB free physical RAM and 4 GiB commit
headroom, with 600 seconds per update and 1,500 seconds per worker. Five guard
controls passed for each relaxed driver. Frozen executed scripts, events,
resource samples and cleanup receipts are retained privately. Earlier startup
encoding and instantaneous-idle-check failures occurred before a numerical
training result and are not treated as model failures.

## Usability and interpretation

The user reported slight desktop lag and increased keyboard/mouse latency,
explicitly allowing the probe to continue. Future guidance should recommend
this resource-heavy training configuration while the user is away/asleep,
keeping the PC awake. No scheduling or training feature was added to the app.

All owned workers closed, and GPU memory returned to desktop baseline. Existing
base weights, adapters and application preferences were unchanged. The next
technical question is the slow backward pass and its GPU working set, rather
than assuming another shared-memory increase will make training practical.
There is no new adapter-quality or seed-improvement claim.

Private evidence: `.data/lora-context-20261029/`, particularly `curated-v2/`,
`probe-relaxed-001/` and `probe-shared4-001/`. These private inputs are not a
standalone public reproduction dataset.
