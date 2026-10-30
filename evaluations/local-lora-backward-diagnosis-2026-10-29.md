# Local Qwen 6K backward-pass diagnosis

**Two complete 6K readiness updates now pass with a checkpointed, chunked output
projection/loss.** They took 127.187 and 64.125 seconds. A matched ordinary-loss
control completed the first example in 170 seconds. This supports a practical
bounded pilot on this configuration, not a full-training or model-quality claim.
No adapter/checkpoint was saved, no full training started and 8K was not tested.

## What the diagnosis established

Lightweight host/CUDA progress markers show that backward enters decoder-layer
gradient computation. The loss/output-gradient markers occur early; the long
observed wall time accumulates while decoder gradients arrive. This is not
evidence of a format problem or an autograd path that never starts.

The decoder backward working set is close to the card's memory capacity, with
system-memory-backed GPU allocations. Large retained vocabulary results add
pressure to that working set. The targeted change computes the same supervised
projection and cross-entropy in checkpointed chunks of 64 target positions,
instead of keeping all target-position vocabulary results together. It uses
ordinary installed PyTorch operations, without new packages, kernels, weight
precision changes, shorter targets or fewer adapter layers. This follows the
[documented chunked-loss memory approach](https://huggingface.co/docs/trl/v1.6.0/en/reducing_memory_usage).

This is a phase/working-set diagnosis, not an operator-level proof of the exact
Windows driver, transfer or kernel responsible for every delay. Shared GPU
allocation alone does not prove harmful paging. The earlier ten-minute failure
cannot be attributed solely to the loss implementation.

## Checks before the real updates

Five CPU numerical cases compare ordinary and chunked loss and upstream
gradients, including uneven chunks, an FP16 frozen head and deliberately wrong
labels. All pass. A 192-token/96-target full-model numerical control compares
all 496 adapter-gradient tensors without an optimizer step. Both tested paths
report the same gradients in that control, with losses agreeing within rounding.
It is a numerical control, not a training example or task-success evaluation.

The actual 6K examples retain every selected target token. Both complete
updates check finite loss, all 496 finite/present adapter gradients, a nonzero
adapter gradient and a witnessed optimizer change. Base weights remain frozen.

## Results and matched comparison

| Run | Total / supervised tokens | Complete update | Gradient norm |
| --- | ---: | ---: | ---: |
| Chunked, longest fitting example | 6,043 / 789 | 127.187 s | 0.354329 |
| Chunked, largest fitting edit target | 5,606 / 1,569 | 64.125 s | 0.229717 |
| Matched ordinary loss, first example | 6,043 / 789 | 170.000 s | 0.354329 |

The first short diagnostic baseline stopped at its declared 180-second limit,
after reaching roughly half of the decoder's layer gradients. It also began
with about 600 MiB less free VRAM and lacked the small full-model numerical
warm-up, so it is not the primary speed comparison.

The additional matched ordinary-loss control used the same numerical preparation,
same freshly initialized adapter, pinned model/token inputs and a comparable idle
desktop: starting free VRAM was 10,942 MiB versus 10,945 MiB for the chunked run.
It retained the same 600-second update limit. The first chunked update used
about **25.2% less elapsed time** in this single matched pair. No repeated
benchmark, stable speed ratio or explanation of all earlier variability is claimed.

| First-example memory observation | Ordinary loss | Chunked loss |
| --- | ---: | ---: |
| Allocated at end of forward | 6,960.66 MiB | 5,892.46 MiB |
| Peak allocated across complete update | 10,711.42 MiB | 10,393.33 MiB |
| Peak reserved across complete update | 11,420 MiB | 11,060 MiB |

Forward retained allocation falls by about 1.04 GiB. The whole-update peak falls
by a smaller 318 MiB: decoder backward still needs substantial temporary memory.
Both paths remain close to the GPU's physical capacity. Reported CUDA free
memory briefly reaches zero despite completed updates under Windows-managed
memory; these are not comfortable all-VRAM training configurations.

Across the chunked run, sampled shared GPU memory peaked at 2,348 MiB, free host
RAM stayed above 10,550 MiB and commit headroom above 16,797 MiB. The matched
ordinary run reached 2,710 MiB sampled shared GPU memory. No guard or CUDA OOM
occurred in either completed run.

## Scope and reproducibility

Hardware is the same GTX 1080 Ti 11 GiB / approximately 32 GiB Windows machine.
The existing offline Qwen3.5 9B HF checkpoint, NF4/FP32 computation, rank-8
adapters on all 32 text-decoder layers, frozen FP16 vocabulary, CPU input
embedding, CPU saved checkpoint inputs and efficient-SDPA compatibility path
remain unchanged. Supervision uses only the previously audited local-Qwen
targets; no Sol conversations, synthetic observations or rewritten targets.

Safeguards retain a 4 GiB shared GPU allowance, at least 6 GiB free physical RAM
and 4 GiB commit headroom, with up to 600 seconds per candidate update and 1,500
seconds per worker. Only disposable readiness updates were authorized. All owned
workers closed; final GPU usage returned to idle baseline. No inference service,
application source/default or installed training package was changed.

Training remains best scheduled while the user is away/asleep, with the PC kept
awake: the preceding probe elicited user-reported keyboard/mouse latency. The
two successful examples do not establish reliability across every prepared row,
8K feasibility, convergence, useful LoRA behavior or accepted seed improvements.
Dataset semantic review and workflow/lineage-separated evaluation design remain
necessary before a separately authorized full run.

The new helpers and exact executed copies remain private in
`.data/lora-context-20261029/`: `chunked_loss.py`, `memory_worker_chunked.py`,
`backward-diagnosis-summary.json` and the three `backward-*/` receipt directories.
The frozen original probes are preserved. These private artifacts are not an
installed public training feature or a standalone public reproduction dataset.
