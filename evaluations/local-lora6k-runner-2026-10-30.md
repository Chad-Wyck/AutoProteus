# Prepared local-Qwen 6K training runner

The full single-epoch pilot runner is implemented and prepared, **not started**.
No Qwen weights were loaded, no GPU training or live inference was performed,
and no packages, services, seed code or model defaults were changed.

The public research entry point is `evaluations/lora6k.py`. Its `prepare` and
`verify` commands use standard-library file/provenance checks and package metadata;
they do not import ML libraries or inspect/start the GPU. Private reviewed data,
checkpoints and logs stay under `.data/` and are not shipped with the repo.

## Frozen inputs and training path

The prepared run uses only the previously reviewed 93 training and 27 validation
examples from the pinned official local Qwen3.5 9B teacher, without teacher
adapters. Checks enforce dataset/file hashes, local teacher identity, original
quality review, disjoint source-lineage groups, frozen example order and exact
completion-only masks. No truncation, oversampling or generated replacement
targets are introduced. Sol interactions and scripted calibration controls are
not part of this dataset.

It preserves the tested 6,144-token NF4/FP32 path: rank 8/alpha 16 across all 32
decoder layers, CPU input embedding and checkpoint inputs, Pascal SDPA helper,
and 64-target checkpointed vocabulary loss. The local HF checkpoint lock and
installed package versions remain pinned. Full base-file hashes are checked
before a future worker starts; preparation checks their locked sizes without
loading weights. A small numerical loss/gradient agreement control runs before
optimization when training is eventually started; it performs no optimizer step.

The run is exactly one frozen epoch: 93 batch-one updates, peak learning rate
`5e-5`, five warmup updates, linear decay to 10% of peak and gradient clipping
at 1.0. The schedule derives from the committed update cursor, so Resume does
not restart warmup or skip/reorder examples.

## Checkpoints, recovery and measurements

After every update, a staged checkpoint saves only the LoRA weights/config,
AdamW state, Python/NumPy/Torch/CUDA RNG state, parameter signature, example
cursor, baseline metrics and last-update measurements. It never saves or
replaces the base weights. Payloads are flushed and hashed before the committed
directory becomes resumable. The latest two complete checkpoints are retained;
partial staging directories remain for diagnosis.

A crash before commit rolls back that uncommitted update. A crash after commit
but before the latest-pointer write recovers the committed directory. A corrupt
or differently bound checkpoint stops recovery instead of silently falling back.
An OS-held run lock blocks duplicate supervisors.

Validation runs before optimization and after the single epoch. Reports include
token-weighted NLL, per-bucket/per-lineage NLL, workflow-bucket macro NLL and
lineage macro NLL. Partial validation can resume only against the exact same
checkpoint, with checksummed row records. These losses do not establish better
seed editing. The prospective 1% overall improvement/no more than 10% workflow
macro deterioration gate only identifies a candidate for later review.

Per-attempt JSONL events, console logs, resource samples, progress and terminal
receipts survive interruption. A completed run keeps its final resumable
checkpoint; it does **not** merge, convert, install or export an inference
adapter, start generation, or launch another epoch.

## Resource control

The Windows supervisor owns a kill-on-close job containing only its training
worker/process tree. It applies no VM-specific 3-GiB/process-count/CPU quota.
Closing/crashing the supervisor closes that job; resource stops never terminate
unrelated applications. A CPU process control verified suspended launch,
ownership and termination.

Before loading, the GPU must be idle with at least 90% VRAM free and no reported
compute owner, and physical RAM must have at least 8 GiB available. During the
run, external counters enforce the existing 4-GiB shared-GPU allowance, 6-GiB
free-RAM floor, 4-GiB commit floor, 600-second operation guard, 3-GiB disk floor
and four-hour cumulative worker allowance across resumes. Loading, validation
and checkpoint saving count toward worker time. Offline input verification and
paused downtime do not. An unclean supervisor exit charges a conservative
30-second unsampled tail on Resume.

`STOP` requests a graceful pause after an in-flight update is committed;
Ctrl+C/resource/time failures close the owned job and retain the prior complete
checkpoint. The four-hour allowance does not reset on Resume. Exhaustion needs
review rather than an automatic retry. As the earlier probes caused desktop
latency, the actual pilot remains intended for when the user is away/asleep.

## Validation performed

- **18 CPU controls passed** in the pinned training environment. They cover
  transaction failures, deterministic state-machine recovery, cursor/schedule,
  validation resumption/checksums/aggregation, guards, teacher/mask rejection and
  a tiny randomly initialized CPU PEFT model's adapter/optimizer/RNG round-trip.
  That serialization fixture uses no Qwen weights or pilot optimization data;
  CUDA calls are stubbed and devices hidden.
- Ordinary regression suite: **571 tests, 503 passed, 68 skipped, no failures**.
  The installed-ML CPU test is opt-in in that suite and was run separately above.
- The real 93/27 dataset and frozen run directory passed offline verification.
- The prepared directory has no training attempts, optimizer checkpoints or
  trained adapter. The earlier successful two-update GPU readiness check remains
  the hardware evidence; this full-epoch implementation has not been GPU-run.

Private handoff: `.data/lora6k-pilot-20261029/TRAINING-RUNNER.md` and
`training-run-prepared-v2/`. The existing dataset, evaluation-v2, one-epoch pilot
plan and editable starter remain unchanged. Training still requires a separate
user start instruction; live-model evaluation requires its own authorization.
