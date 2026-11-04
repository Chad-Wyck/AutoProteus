# Setup, assets and implementation map

## CPU entry point

Python 3.11 and the small dependency set in requirements-cpu.txt are sufficient
for the selected CPU checks. Commands are in the root starting file. These
versions were observed in the existing qualified research environment; this file
is not a hash-locked complete native/GPU environment. Produce an installation
lock and record `pip check` for a new machine. Do not modify another active venv.
The public suite has four explicit skips for absent private historical artifacts;
see AUDIT.md and VALIDATION.json for the exact coverage limits.

## Live runtime prerequisites and gaps

The current native binding targets Windows x64, WHPX/QEMU and the exact b10777
PrismML-Eng/llama.cpp C ABI. Its source pin is
`e3de715222b2667c54a267441159a5729f11155e`. The VM uses a separate NumPy 2.4.6
guest image. No DLLs, QEMU binaries, kernels, wheels or image are bundled. Another
OS, engine version, GPU, architecture or batching topology needs a qualified port.
Do not substitute host `exec` for the VM or assume a server API has matching
presence-penalty semantics. The historical native sampler applies penalties to
generated tokens only.

The live publication builders are historical workflows: several require earlier
private manifests, exposure inventories, token journals and closure receipts.
They are useful implementation references, not a portable launcher for a new user.
Create a fresh preparation layer from the new manifest and cases; qualify it before
model use. Hidden original evaluation questions are intentionally absent. Acquiring
model files alone will not recreate the original publications. No automatic
frontier API integration or specific paid frontier model is supplied.

## Model/source pins from the local records

| Component | Identity |
| --- | --- |
| Teacher canonical source | `Qwen/Qwen3.5-4B`, revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a` |
| Historical teacher conversion | `--outtype q8_0 --no-nextn`, text-only; 4,482,403,072 bytes |
| Original teacher GGUF SHA-256 | `e6385ebadc227b4869f20f8db3d136fdafb37f2c079bdfcef0deb0e217b4cfe8` |
| Student canonical source | `Qwen/Qwen3.5-0.8B`, revision `2fc06364715b967f1860aea9cf38778875588b17` |
| Original student F32 GGUF SHA-256 | `610157ac84f6a5db368959c8ef3bb124148b87d25d8ef4e90be193a1c6ae6bab` |
| Published repair source | `RikiyaT/lm_understand-logs`, revision `4d09ba6d6a7e891dd8063974dfe81b3d78e3494f`, `exp8_math/runs/p50c` |
| MATH-500 source pinned by acquisition code | `HuggingFaceH4/MATH-500`, revision `6e4ed1a2a79af7d8630a6b768ec859cb5af4d3be` |
| Independent math grader | math-verify 0.9.0; latex2sympy2_extended 1.11.0; antlr4-python3-runtime 4.13.2 |

Acquire sources directly, inspect their pinned terms and record hashes. The
AutoProteus MIT-0 license does not license third-party models, datasets or engines.
Do not redistribute checkpoints or upstream patch/log files on that basis.

## Resources and settings

The original hardware was a GTX 1080 Ti with 11,264 MiB VRAM. That establishes
only local feasibility for qualified configurations, not a minimum for every
teacher/student pair. Historical 4B Q8 short readiness used about 5.6 GiB owned
dedicated GPU allocation; long outputs and concurrent models need fresh measurement.
Run teacher and student phases sequentially unless another topology is qualified.
Allow storage for original BF16 sources, separate deployed files and multiple
copies; 20 GiB free is an admission floor, not a complete storage estimate.

Historical memory policy: admission free VRAM >=8,192 MiB, free host RAM >=8 GiB,
commit headroom >=4 GiB, free disk >=20 GiB and owned shared GPU memory <=512 MiB.
Running stops: free VRAM <2,048 MiB, free RAM <6 GiB, commit <4 GiB, disk <5 GiB
or owned shared GPU memory >512 MiB. Identity/critical measurement failures stop.
The opt-in `memory-availability-v1` logs background GPU activity instead of
rejecting on utilization alone. Older publications keep their strict rules;
the intervening proposed 5% tolerance was never applied. Freeze the receiving
owner's policy equally for every arm. Never stop unrelated processes.

Real student math settings were thinking enabled, temperature 0.6, top-p 0.95,
top-k 20, generated-only presence penalty 1.5, 32,768 output and 34,816 context
tokens per slot. Newer teacher screens used 8,192 output caps. Do not silently
apply student settings to teacher screens or normal AutoProteus operation.
Sampler/EOS/tokenization controls are required even with the same visible values.

## Source map

| Files under evaluations/ | Purpose |
| --- | --- |
| `weight_repair*` | Pinned published-repair acquisition, reconstruction, protocol and grader controls |
| `weight_editor_native.py`, `weight_editor_worker.py` | Native binding and sampled-token worker |
| `weight_editor_owned.py`, `lora6k_supervisor.py`, `memory_availability_policy.py` | Owned worker lifecycle, measurements and resource admission |
| `tensor_workspace_policy.py`, `tensor_workspace_precision.py` | Closed numeric broker, changed-only BF16 rounding, exact candidate/checkpoint/test receipts |
| `tensor_workspace_guest.py`, `tensor_workspace_vm.py`, `tensor_workspace_image.py` | Isolated Python, VM transport and separate guest image |
| `tensor_workspace_contract.py`, `tensor_workspace_teacher_stage.py` | Explicit helper contracts, teacher screen and conditional student comparison |
| `tensor_workspace_code_diagnostic.py`, `tensor_workspace_overnight.py` | Synthetic execution graders and diagnostic workflows |
| `neuron_focus*` | Bounded channel-localization design, static-vs-hook controls, continuation accounting |

All copied sources/tests and hashes are listed in SOURCE-MANIFEST.json. Changes
for public packaging remove a private instruction/thread ID and make generated
execution authorizations false. Numerical algorithms and historical scores are
not rewritten. Those adaptations make the source snapshot different from the
original frozen live publications; use the packaged hashes for new experiments.
