# Local-Qwen 6K pilot — preflight and launch

The user authorized one epoch on the frozen local-Qwen 93/27 dataset, retaining
the existing safeguards and excluding live-model tests. The initial launch
stopped **before loading Qwen or starting optimization**: 9,825 MiB of 11,264 MiB
VRAM was free, below the original 90%-free requirement (at least 10,138 MiB).
A later snapshot showed 9,847 MiB free. Physical RAM was about 15 GiB available.

No game, inference service or active Compute/CUDA engine was detected. Discord
reported roughly 1 GiB of dedicated GPU reservation; Windows desktop contexts
also appeared in `nvidia-smi --query-compute-apps` with memory `[N/A]`.

The ownership preflight had a Windows/WDDM classification bug: it interpreted
every such GUI context as a compute owner. The corrected guard distinguishes
known desktop executables only when their memory is unreported and actual
compute engines are idle. Unknown owners, Python/model services, measured
compute allocations and active compute engines remain blocked. This is an idle
heuristic, not a process-identity security boundary. All original VRAM, RAM,
commit, shared-memory, disk and time thresholds remain unchanged.

The original frozen preparations and initial launch logs are preserved. Fresh
`training-run-prepared-v3/` contains the corrected guard and the same dataset,
order, one-epoch hyperparameters and limits. Its actual ownership check
classified 28 desktop contexts and found zero active compute engines. The
initial VRAM requirement still needs roughly 0.3 GiB more headroom; the user was
asked to close an unused GPU app before retrying. No application was stopped.

Private continuation: `.data/lora6k-pilot-20261029/START-CONTINUATION.json` and
`TRAINING-RUNNER-v3.md`. At that initial preflight checkpoint there were no optimizer updates,
training checkpoints, model-generated outputs or live-model trials. This is a
preflight finding, not a training outcome.

## Authorized retry

The user closed Discord and authorized a retry. The same VRAM/headroom and
resource guards passed; the frozen v3 supervisor and training worker started.
The model loaded and its dense/chunked numerical loss/gradient control passed.
Initial checkpoint saving succeeded and baseline validation is running. This
establishes launch readiness, not one-epoch completion or training benefit.

The corrected ownership path passed all 19 CPU controls. The ordinary suite
ran 572 tests with 68 skips and no failures. No frozen dataset, example order,
hyperparameter or resource threshold was changed for the retry.

The user explicitly clarified **Run live-model tests afterward**. After complete
finite training/validation and worker closure, the continuation authorizes
separate adapter conversion/enable-disable checks and the prepared matched
local base-versus-final-LoRA first/second-extension screen. It does not authorize
another epoch, model installation, merging, cloud/API use or extra repeats.
An attached 15-minute checkup reads durable state quietly while healthy, rather
than keeping an assistant active with minute polling.

The run and fixed gated screen have now finished. See the
[training findings](local-lora6k-training-2026-10-30-findings.md) and
[closed comparison](local-lora6k-seed-comparison-2026-10-30-findings.md).
The base completed two chains; the LoRA's 3/5 explicit ordinary completions gated
its extension trials despite correct artifacts. Owned compute and listeners are
closed; the adapter remains experimental and no extra tests were launched.
