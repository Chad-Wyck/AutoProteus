# Inference engines: video review and AutoProteus relevance

Date: 2026-10-17, America/Regina. Research only; no engine installed, model run, preference changed, or candidate promoted.

## Evidence and conclusion

I read the complete timestamped transcript through YouTube's Show transcript panel for Cloud Codes' [7 Free Engines That Run Local AI 2x Faster Than llama.cpp](https://www.youtube.com/watch?v=tL0KwFaAe0Y), published October 17, 2026, duration 18:58. The transcript has automatic-caption spelling errors; repository names below come from the description's links and primary sources. An initially returned search result about a different inference-engine video was excluded.

The video is an audit of performance claims, rather than seven proven replacements. Relevant passages cover speculative decoding (8:42 and 12:11), expert offloading (10:08), and model/hardware specificity (16:04). My recommendation is to qualify acceleration within the existing engine first, retain interchangeable inference services, and treat the Pascal fork as a separate exploratory model/engine candidate.

## Current AutoProteus baseline

Inspected local working files on HEAD `4edc8ad1bc568c40f62fd3532300f88c9ca1ad92`, including existing uncommitted changes. This review adds only this memo.

- [Runtime](D:/AI_New/AP/controller/runtime.py) and [runtime lock](D:/AI_New/AP/controller/managed-runtime-lock.json): managed Ollama 0.40.4, one loaded model and one inference stream. The ordinary launch configuration does not explicitly set flash attention or KV-cache quantization.
- [Provider adapter](D:/AI_New/AP/controller/providers.py): streaming Ollama `/api/chat`; the compatible-service branch sends nonstreaming `/chat/completions`, accepts native tool calls, and supports JSON fallback. Alternate local servers can potentially use that existing branch, subject to qualification. This is an integration path, not a completed compatibility test.
- [Protocol check](D:/AI_New/AP/controller/compatibility.py): two-turn tool/result/finish diagnostic. Basic compatibility does not establish recursive-upgrade competence.
- [Latest Qwen findings](D:/AI_New/AP/evaluations/seed-v0.0.14-qwen9b-findings.md): GTX 1080 Ti 11 GB; Qwen3.5 9B Q4_K_M, 128K configured context, 4K response allowance, temperature 0.6, thinking off, flash attention enabled and q8_0 cache in the research profile. First upgrades accepted 2/3; complete staged growth 1/2. The remaining failures include incorrect defaults and action exhaustion. These small exploratory batches do not establish repeatability.

The configured context allowance is not the actual prompt length. Evaluate both, particularly as a tool conversation grows. Existing research already uses two common memory optimizations; enabling them again is not a new result.

## What the primary sources support

| Candidate | Verified evidence and applicability | AutoProteus decision |
| --- | --- | --- |
| [Pascal Strata fork](https://github.com/SirDebugALot/Strata-Qwen3.6-35B-A3B-Pascal-Optimized) | Windows/sm61, Qwen3.6 35B-A3B MoE. Reported 8K decode: 24.53 versus 7.88 tokens/s; 16K: 21.40 versus 7.16. Test: 4 GB GTX 1050 Ti Mobile, 48 GB RAM, 25,088 effective context, greedy sampling. Experimental, unequal repetition counts, missing baseline offload flags. | Closest hardware lead, but no evidence of those gains on our 1080 Ti, 9B model, or 128K profile. Its model file is about 14.1 GB. RAM and long-context suitability need checking. |
| [Lithos-Metal](https://github.com/lithos-ai/lithos-metal) | Apple Silicon/macOS 26+; M5 Max case study. Its 168/127 tokens/s figures are target-compute projections excluding draft/acceptance/rewind costs, explicitly not measured end-to-end rates. | Future Mac research; AutoProteus currently lacks a macOS VM backend. |
| [PolyStrata](https://github.com/VecSzn/PolyStrata) | Current repository advertises Windows and Linux support for several families; requirements vary by backend. Qwen3.6's documented NVIDIA path requires RTX 20 series or newer. | Do not repeat the video's blanket Linux-only characterization. Current documented path does not qualify our Pascal card. Hardware-aware setup is a useful product idea. |
| [Glyd Hummingbird model card](https://huggingface.co/glyd/nemotron-3-hummingbird) | Read directly in the browser. Lossy checkpoint, separate Glyd engine; Linux, Ampere+ GPU with at least 16 GB, 64 GB host RAM for full speed. Engine and weights have separate licenses. | Not a current-machine candidate. Review exact redistribution/commercial terms before any packaging proposal. |
| [V620 vLLM fork](https://github.com/JoseMiralles/vllm-rdna2-qwen) | Targets Radeon PRO V620 multi-GPU hardware. Its current table reports about 70 tokens/s on eight cards; that is not evidence of an eightfold gain on our hardware. | Not relevant to this single Pascal GPU setup. |
| [Lucebox megakernel](https://www.lucebox.com/blog/megakernel) | A real, linked implementation explains fused execution using a small Qwen model, tested on RTX 3090 and targeting Ampere+. | Useful architecture background, not validation of the separate 27B/140 tokens/s anecdote or a Pascal replacement. |
| Lamina / claimed 27B megakernel | No primary implementation supporting those particular headline claims was established in this review. The Lucebox project is separate. | Insufficient evidence to recommend. |

The Pascal fork's transferable ideas are phase-specific VRAM allocation, native packed expert computation, and overlapping CPU/GPU expert execution. These belong in the inference runtime, not the editable seed. Its [server source](https://github.com/SirDebugALot/Strata-Qwen3.6-35B-A3B-Pascal-Optimized/blob/main/serve/server.py) documents an OpenAI-style endpoint and opt-in server MCP tools. Qualification should use only inference and AutoProteus's existing guest action path, without enabling the server's independent MCP loop. Actual native tool behavior remains untested here.

## Most useful opportunities

### 1. Test speculative decoding through the existing runtime first

Speculation proposes several tokens cheaply, then asks the target model to verify them together. The [original paper](https://arxiv.org/abs/2211.17192) establishes distribution-preserving acceleration under its acceptance procedure. This does not promise identical sampled strings across implementations or seeds, nor that every implementation is correct.

Crucially, [Ollama's documentation at our pinned 0.40.4](https://github.com/ollama/ollama/blob/v0.40.4/docs/modelfile.mdx) already documents `draft_num_predict`: zero disables drafting, while embedded MTP needs the parameter set. An engine replacement is therefore not a prerequisite. First check whether the exact cached checkpoint contains compatible draft tensors and whether its model configuration already enables them; the saved research profile alone does not settle that.

[llama.cpp MTP PR #22673](https://github.com/ggml-org/llama.cpp/pull/22673) was merged May 16. One historical benchmark improved generation but slowed prefill and used roughly 2.49 GiB more VRAM; it used an RTX 3090 plus RTX 3060, not our GPU. [Probabilistic drafting PR #27694](https://github.com/ggml-org/llama.cpp/pull/27694), merged October 2, adds a relevant option for sampling above zero. Verify exact bundled support before attempting to map standalone llama.cpp flags into Ollama. They are not interchangeable APIs.

### 2. Make tested profiles convenient while preserving model choice

My proposed profile identity is engine version + model digest + quantization + template + hardware + context + sampling + cache/draft settings. Store measured compatibility, memory needs and task results with it. A simple recommended profile and an advanced override would reduce user setup work. Unsupported acceleration should fall back to ordinary generation through the same action contract.

Keep the protected host in control of runtime downloads, resource limits and configuration. Recursive seed improvements should remain independently evaluated guest changes; faster inference can increase affordable trials, but is not itself recursive improvement or grounds for relaxing verification.

### 3. Measure the whole conversation

[llama.cpp's server documentation](https://github.com/ggml-org/llama.cpp/tree/master/tools/server) describes common-prefix cache reuse. AutoProteus's stable opening prompt makes reuse relevant, but actual reuse must be measured rather than inferred from total prompt-token counters. Its compatible-service adapter currently does not stream, so client timing alone cannot provide genuine time to first token; collect server timing or qualify a streaming adapter separately.

The video's bandwidth rule is a rough dense, single-stream decoding bound. Use bytes actually read per token, plus cache/activation costs, rather than applying total file size as a universal law. MoE active weights, CPU/GPU transfers, cache residency and multi-token verification change the calculation. It is not a reliable pass/fail test for all headline speeds.

## Suggested bounded follow-up experiment

1. Freeze the current Qwen9B baseline, checkpoint digest, starter seed, sampling and independent grader. Inspect draft availability/configuration before choosing experimental arms.
2. If supported, compare drafting off with a small draft budget using the same checkpoint. Record the setting and actual accepted-draft counts. If draft tensors require a different checkpoint, label that a combined checkpoint/runtime comparison rather than an isolated speed test.
3. Test short and long actual prompts, cold and warm sessions, then repeated fresh upgrade tasks and second extensions. Keep action/output allowances fixed; report elapsed-time gains separately from capability changes under a fixed wall-clock budget.
4. Record verified acceptance/completion first; then matched-success time, prefill/decode timing, memory/offload, context errors, invalid calls, cancellations and incomplete replies. A faster wrong answer is not a win. Preserve all unsuccessful attempts.
5. Only after that, consider a separately labeled Pascal-Strata + 35B MoE pilot. Compare it with the same GGUF on a pinned mainstream engine for engine effects, and separately with the current 9B profile for practical product utility. Start with the existing protocol/basic-task gate before spending on recursive trials.

No experiment was run for this review. The recommended first step is a draft-support audit and controlled qualification within Ollama; the Pascal fork is the next exploratory candidate, not a justified default replacement.
