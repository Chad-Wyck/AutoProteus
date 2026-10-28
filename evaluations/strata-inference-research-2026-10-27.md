# Strata inference review — 2026-10-27

**Assessment: a credible candidate for an isolated Qwen3.6-35B-A3B trial on this machine, with experimental Pascal support and significant RAM constraints. It is not yet a demonstrated improvement over the current AutoProteus engine.**

Reviewed upstream revision [5e8a4cc](https://github.com/Niko1221/Strata/commit/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d); app/Terminal 0.2.7, engine 0.1.52. AutoProteus baseline: c2c7d13501b165130bcc13994ba0be0344cb58a1 (v0.14.1). Research only: no model downloads, installs, service changes, inference or GPU tests.

The recorded local hardware is a GTX 1080 Ti (11 GiB, compute capability 6.1), i5-11600K (6 cores / 12 threads), 34,132,537,344 bytes of physical RAM (31.79 GiB), Windows 11 Home and NVIDIA driver 581.29. These are recorded observations in [the local findings](seed-v0.5-local-findings.md), not a fresh hardware inventory. Live CIM access was unavailable in the sandbox. Current free RAM/VRAM, storage performance, memory bandwidth and PCIe configuration were not measured.

Strata is a specialized hybrid inference engine for selected MoE model families. It distributes expert work between the GPU and CPU, supports model-native MTP speculative decoding, and supplies a local compatible API and desktop/Terminal setup. This is a useful approach when a model exceeds VRAM. Support is model-specific: the presence of a GGUF file does not establish support for arbitrary architectures or the current Qwen3.5 9B baseline. [Model coverage](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/docs/MODELS.md), [architecture overview, primarily Flash-Next](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/docs/HOW_IT_WORKS.md).

For Qwen3.6, Strata has a dedicated engine under src/qwen35. The model has 35B total parameters and approximately 3B active per token; the active parameter count reduces computation, not the requirement to store the complete quantized weights. It supports the Unsloth MTP GGUFs below. [Qwen3.6 documentation](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/docs/QWEN36.md), [pinned model sizes](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/setup.py#L629).

| Quantization | Weight download | Setup RAM planning figure | Assessment here |
| --- | ---: | ---: | --- |
| UD-Q4_K_XL | 22.85 GB / 21.28 GiB | 32 GB | The sensible first candidate; headroom must be measured |
| UD-Q6_K_XL | 32.61 GB | 44 GB | Beyond the documented RAM planning figure for this PC |
| Q8_0 | 37.80 GB | 52 GB | Beyond the documented RAM planning figure for this PC |

The [older-GPU guide](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/docs/OLDER_GPUS.md) explicitly includes GTX 10-series / sm_61 through the **experimental CUDA 12 engine**, with a prebuilt package. A custom source build is not inherently necessary. CUDA 13 packages do not support this architecture. The recorded driver is above the guide's Windows CUDA 12 minimum of 528; that establishes a documented prerequisite, not a tested installation. The mainstream supported NVIDIA range remains RTX 20 and newer.

A current [community report, issue #4332](https://github.com/Niko1221/Strata/issues/4332) says the exact Q4 model boots on an 11 GB GTX 1080 Ti with 16 of 256 experts per layer in VRAM. The report's measured speed figures belong to an RTX 4080 SUPER on WSL2 with a different CPU; **none is a GTX 1080 Ti speed measurement**. This strengthens feasibility but does not establish native Windows stability, useful throughput or AutoProteus correctness.

Memory is the principal qualification risk. In hybrid mode, the [current source](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/src/qwen35/q36_engine.cu#L2921) retains a host copy of every routed expert, including GPU-cached ones, attempting pinned allocation and falling back to pageable memory. Setup records approximately **18.75 GiB of Q4 experts in host RAM**. GPU offload therefore does not subtract the same number of bytes from this host expert allocation, and 32 GB RAM plus 11 GB VRAM cannot be treated as a simple combined pool. Additional process buffers, the OS, file-backed pages, desktop GPU use and AP guest memory matter.

[Issue #3508](https://github.com/Niko1221/Strata/issues/3508) reports roughly 30.1 GB of system RAM used on a 32 GB Windows PC with a Quadro P5000, plus MTP and configuration concerns in older engine 0.1.46/0.1.47. It is one machine, not proof these symptoms occur in 0.1.52. The issue closed for template housekeeping; that is not evidence of a fix. The proposed workaround to force expert allocations past actual free VRAM is not a sound recommendation, and its prediction that GPU caching reduces the full host copy conflicts with the current source.

Context also has a price: the documented Qwen3.6 cache is fp32, about 1.5 GB per 32K slot plus recurrent state. At 128K, that component alone is roughly 6 GB and would displace much of an 11 GiB card's expert cache. Generic Strata int8-cache switches should not be assumed to work on this model path. I would start at 8K or 16K, one text-only slot and vision disabled, then qualify 32K and the actual AP prompt lengths. Short-context results cannot qualify the current 128K AP configuration. [Cache and batching](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/docs/QWEN36.md).

The project reports Q4 decode around 59.7 tokens/s on an RTX 3060 12 GB with a 20-thread CPU, versus 48–52 on its llama.cpp comparison. These are publisher measurements with their own settings. They show the hybrid approach can be competitive, not an estimate for the i5/1080 Ti. MTP acceptance, prompt processing, repeated-prefix reuse and CPU/RAM traffic all affect end-to-end speed.

AutoProteus already accepts independent loopback compatible services through its standard adapter; see [the current study handoff](local-model-test-handoff.md). Strata's [server](https://github.com/Niko1221/Strata/blob/5e8a4cca7d690ac60ca37eb09e7d0e010099ad6d/serve/server.py#L7590) handles native tool requests/results and nonstreaming responses, making an external-engine trial plausible. Compatibility still needs testing: call IDs, tool choice, finish reasons, history replay, cancellation and long inputs. This Qwen3.6 path refuses logit_bias. Keep Strata's separate opt-in MCP execution disabled so that AP continues to execute model-written code in its disposable VMs.

A useful later trial, when other tests are idle:

1. Pin the engine, exact Q4 GGUF/hash and sampling/template settings. Begin with one text-only slot and 8K/16K context; record any ignored flags.
2. Compare against llama.cpp using the same model file, actual input/output lengths and comparable placement. Measure MTP off and on separately. Do not interpret a Qwen9B-vs-Qwen35B comparison as an engine comparison.
3. Separate cold load, cold prompt, reused-prefix prompt and generation speed. Capture RAM working set/commit, available RAM, dedicated/shared GPU memory, paging, MTP acceptance and time to first token.
4. Pass AP's existing inference/protocol checks, ordinary tasks and activation-use-v2 first-use/complete-chain study. Use prompts that fit the tested context; fail clearly on overflow.
5. Consider changing the default only after it improves real AP outcomes or elapsed task time without unacceptable memory pressure.

No benchmark was run, no performance estimate for this PC is established, and the existing inference service/defaults were left unchanged.
