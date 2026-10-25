# Empero Qwen3.8 9B Q6 preflight — 2026-10-23

**The unofficial Empero distillation passed AutoProteus's standard native connection qualification. Seed-editing ability remains untested.**

Candidate: [empero-ai/Qwen3.8-9B-Distill-GGUF](https://huggingface.co/empero-ai/Qwen3.8-9B-Distill-GGUF), revision `760121cd70bb4c36b2b5ec58eb765e0df5987efe`, `Qwen3.8-9B-Q6_K.gguf`. The [source card](https://huggingface.co/empero-ai/Qwen3.8-9B-Distill) describes an unofficial distillation using the Qwen3.5 9B architecture. Publisher claims do not establish AutoProteus performance.

- Size: 7,558,901,056 bytes; verified SHA-256 `0f1271373f899912bfe4ea76299af7dd83722d98ea421b0827501c3a2c6da22b`.
- Runtime: the existing pinned Prism llama.cpp CUDA engine, GTX 1080 Ti, no adapter, 128K context, 4K responses, temperature 0.6, top-p 0.8, top-k 20, thinking disabled.
- Connection: unchanged production `ModelClient` and `qualify_profile`. The observation subclass records calls without rewriting messages, IDs or responses.
- Outcome: eight requests; three exact-value/receipt rounds, one rejected-call recovery and explicit completion. All passed without format repair.
- Calls: 14,848 reported input tokens and 321 output tokens; 16.994 seconds of aggregate call time. All eight usage/timing measurements and all traces were complete. These short diagnostics are not a general speed or coding benchmark.
- Loading/checking/qualification/cleanup: 37.28 seconds. The owned server was stopped afterward. A reasoning-enabled fallback was not needed.

The user-approved older caches reclaimed about 17.76 GiB. After downloading the single Q6 copy, the drive retained 99.81 GiB free (10.464%). All previous results, training data, adapters and the explicitly preserved model caches remain.

Private evidence: `.data/model-preparation-20261023/`, including cleanup receipts, pinned download metadata/checksum receipt, range-resume manifest and `preflight-matched/{profile,qualification,result,runtime}.json` plus raw calls and runtime logs. Weights: `.data/models/gguf/Empero_Qwen3.8-9B-Distill-Q6_K.gguf`.

The frozen v0.8.2 guidance comparison can now include this candidate alongside Qwen3.5 9B Q6. No full comparison or accepted-upgrade claim follows from this preflight, and no model seed-editing trials were started here.
