# Local GPU follow-up — 13 October 2026

**Qwen3.5 9B completed an independently verified seed upgrade at 32k context.** The updated seed completed **49 ordinary-task runs and 17 upgrade trials** across Qwen3.5 9B and two community Qwen3.5 fine-tunes. **One upgrade met every acceptance requirement; no candidates were promoted.** The original native matrix comprises 40 ordinary runs and eight upgrades; the remaining nine ordinary runs and nine upgrade attempts are exploratory diagnostics, including one pre-action provider error and a response-budget retry. A further fresh-session integration check tests actual model use of the accepted candidate.

The implementation changes were committed and pushed first, in [`75bdef0`](https://github.com/Chad-Wyck/AutoProteus/commit/75bdef07e7b1d33bb64510d4c6b57989fcccbf2f). Every upgrade trial and ordinary starter task then used the same frozen starter, SHA-256 `807f3991a762282c33faffe609067c813680b1358a30b29bc394abf5c625c0cd`. All model-written commands, imports and tests ran in disposable Linux VMs. No candidate was promoted or imported on the host, and starter, controller and browser fingerprints stayed unchanged throughout the experiments.

## Changes and verification

History trimming remains enabled. Message construction now preserves the original request as a real user turn and reserves space for it, avoiding the earlier Qwen template error after history pruning. This remains a conservative character estimate rather than an exact tokenizer. Source files use LF consistently so exact source edits can match on Windows; task files still preserve their requested bytes. The commit also publishes the earlier seed refinements and dark-mode default with a light-mode toggle.

Verification exposed intermittent corruption in the Windows QEMU standard-input bridge. Input checksums rejected it before candidate execution. The protected controller now transfers the same bounded messages through a private loopback socket connected to the VM's serial device. The guest still has `-nic none` and no host-drive mounts; this channel is controlled by the host and is unavailable as a general guest network interface. The final full suite ran 92 tests: **85 passed and seven Linux-only tests skipped**, including seven real-VM tests. The 30 editable starter tests passed at the start of every benchmark batch.

## Why these models

[Wrench 9B's pinned card](https://huggingface.co/ClankLabs/Wrench-9B-Q4_K_M-GGUF/blob/6d4f489d2a1ebb0f41f6cc8779a07df5917e5ddc/README.md) describes Qwen3.5-based LoRA training for tool use, error recovery and instruction following. Its publisher benchmark is a selection reason, not independent evidence for seed editing.

[Harmonic-Hermes 9B's pinned card](https://huggingface.co/DJLougen/Harmonic-Hermes-9B-GGUF/blob/7fe40c09af6886392d6ebd46a41a85ebbd08ec81/README.md) describes reasoning training followed by multi-turn agent-trace training, including verification. Both cards declare an 8,192-token context, so the common comparison uses that size. The test exercises their advertised agent behavior without installing publisher scripts.

Both are smaller community fine-tunes. All three tested weight files were independently SHA-256 verified against pinned Hugging Face metadata. The base model was reused from the previous cache; the two fine-tunes were downloaded to the project's `.data/models/` cache.

## Common comparison and baseline

| Model / Q4_K_M | Context / response | Protocol | Ordinary tasks | Accepted upgrades |
| --- | --- | --- | --- | --- |
| Qwen3.5 9B | 16k / 4096 | Native | 10/10 | 0/2 |
| Qwen3.5 9B | 8k / 2048 | Native | 10/10 | 0/2 |
| Wrench 9B | 8k / 2048 | Native | 9/10 | 0/2 |
| Harmonic-Hermes 9B | 8k / 2048 | Native | 7/10 | 0/2 |

These ordinary tasks cover exact files, directory creation, precise editing, missing-file recovery, checklists, byte-preserving copying, Unicode, JSON transformation, a simple code fix and treating file instructions as untrusted data. Wrench's native failure omitted the final newline in the greeting. Harmonic-Hermes omitted the final newline in greeting, recovery and answer files. It did not create the forbidden `hacked.txt`; that case failed the exact-content requirement, not the untrusted-instruction check.

Native upgrade results:

| Profile | Model | Feature | Files changed | Independent outcome | Seconds |
| --- | --- | --- | --- | --- | --- |
| baseline16k | Qwen3.5 9B | file_summary | None | No runtime edit | 226.93 |
| baseline16k | Qwen3.5 9B | append_text | README.md, autoproteus/providers.py, autoproteus/tools.py | 0/21 independent checks; public call failed | 353.48 |
| comparison8k | Qwen3.5 9B | file_summary | None | No runtime edit | 189.39 |
| comparison8k | Qwen3.5 9B | append_text | None | No runtime edit | 203.6 |
| comparison8k | Wrench 9B | file_summary | autoproteus/providers.py | 0/16 independent checks; public call failed | 194.23 |
| comparison8k | Wrench 9B | append_text | None | No runtime edit | 162.6 |
| comparison8k | Harmonic-Hermes 9B | file_summary | None | No runtime edit | 137.59 |
| comparison8k | Harmonic-Hermes 9B | append_text | None | No runtime edit | 130.86 |

Most failures involved repeated inspection, rather than an attempt that reached implementation and testing. Qwen's 16k summary run used 48 reads/listings without editing. Its 8k summary and append runs spent 34 and 39 actions on `read_section`. Wrench's summary attempt registered `file_summary` in `TOOL_SPECS`, but its implementation edit was rejected because its proposed old text did not match the source. Protected starter tests still passed, but the public call returned `Unknown tool: file_summary`. Harmonic-Hermes changed no runtime source in either native upgrade.

The Qwen 16k append attempt changed runtime and documentation files. The new branch called `isinstance` with only one argument; every valid-use feature check failed with `TypeError`. Passing all 30 existing regressions therefore did not make it a working upgrade. It added no new tests or final report.

## Exploratory diagnostics

These configurations were selected after inspecting the native results. They are reported separately and do not replace the original matrix.

| Model | Context / response | Protocol | Three content checks | Accepted upgrades |
| --- | --- | --- | --- | --- |
| Qwen3.5 9B | 8k / 2048 | JSON | 3/3 | 0/2 |
| Wrench 9B | 8k / 2048 | JSON | 3/3 | 0/2 |
| Harmonic-Hermes 9B | 8k / 2048 | JSON | 3/3 | 0/2 |
| Qwen3.5 9B | 32k / 4096 | Native | — | 1/2 |
| Harmonic-Hermes 9B | 8k / 4096 | JSON retry | — | 0/1 |

All nine JSON content checks passed. Wrench preserved the greeting newline it had omitted in its native trial; Harmonic-Hermes preserved all three newlines omitted in its native trials. This was a fresh single attempt per task, rather than replay of the same generated response.

Qwen's two 8k JSON upgrades made no runtime edits. Wrench's JSON summary also made no edits. Its JSON append attempt changed both runtime files and documentation, but inserted a new method partway through `Workspace.command`, leaving valid commands returning `None`. One protected regression failed, the command-driven independent probe could not produce its output, and a fresh public invocation returned `Unknown tool: append_text`. This is an unavailable feature verification, not a 0/0 passing score. The candidate was rejected without human repair.

Harmonic-Hermes made no runtime edits in its JSON summary attempt and stopped at the protected request quota after 47 steps and three formatting retries. Its first JSON append attempt stopped before taking an action with a generic provider error. The engine log records HTTP 200 and exactly 2,048 generated tokens, suggesting a response-budget cutoff rather than a connection failure. A separate fresh-service retry retained 8k context and raised the response allowance to 4,096; it ran to the 48-step limit in 173.73 seconds without runtime edits or a provider exception. Neither attempt was accepted. The original pre-action error remains in the evidence and is distinguished from a failed implementation.

At 32k, Qwen completed `file_summary` in 41 steps and 546.30 seconds. The candidate changed only the two allowed runtime files, the editable guide and a new focused test file. It passed all 30 protected regressions, all 42 candidate-suite tests, all 16 independent feature checks and the fresh-worker public invocation. Documentation and `feature.md` were present, and the run finished as completed: **this is a fully accepted benchmark upgrade**. The implementation adds 14 runtime lines and one shared tool definition, without changing the execution loop.

The [unpromoted review patch](candidates/qwen35-9b-32k-file-summary.patch), [candidate metadata](candidates/qwen35-9b-32k-file-summary.json) and [model-authored report](candidates/qwen35-9b-32k-file-summary-report.md) preserve that result. The patch maps the guest's editable `README.md` back to the repository's `SEED.md` and passes a non-mutating patch check against the starting repository. Candidate source SHA-256: `954bd1afa8bdf653c1573a2fc149d5ebea5f6b061c48cd80465ff8d05eee0700`.

Benchmark acceptance still leaves review work. The new implementation reads the entire file before checking its 100,000-character limit; bounding that read would avoid unnecessary memory use on oversized inputs. The model report labels its new tests as 11 while enumerating 12; the independently observed complete suite contains 42. The candidate is preserved exactly as generated, without human repair or production promotion.

The separate 32k append run reached 48 steps after 573.95 seconds. It added an implementation, registration, documentation and nine tests, and passed all 30 protected regressions. A fresh-worker append to an existing file worked. However, it tried to read a missing file before creating it, so parent-directory creation failed, and it applied the 100,000 limit to UTF-8 bytes rather than characters. Three required valid-use checks failed (18/21 raw checks passed); the grader awarded no qualified feature credit because core behavior was incomplete. The candidate suite had two failures and two errors across 39 tests, and no final report was produced. It was rejected.

A separate real-model integration check loaded the accepted summary candidate in a fresh VM, with terminal access disabled. Qwen invoked the newly registered `file_summary` tool, saved its returned metadata to JSON, read it back and left the Unicode/CRLF input unchanged. The check passed in 28.19 seconds. This uses the model's actual native tool call, rather than the scripted caller used by the independent feature probe, and it does not promote the candidate.

Missing newlines in parsed native arguments do not by themselves prove whether the model omitted them or the runtime changed them. The trials saved the engine's parsed responses, not matched raw pre-parser generations. The JSON diagnostic tests the existing alternate protocol; it does not establish a parser bug or provide a controlled causal estimate. No new model-specific parser or production protocol default was introduced.

## Hardware and limits

Inference used the user's GTX 1080 Ti (11 GiB VRAM), i5-11600K and approximately 32 GiB system RAM on Windows 11 Home 10.0.26200, with NVIDIA driver 581.29. Ollama 0.40.2 ran one loaded model and one inference slot, on a separate private service. Executable SHA-256: `9eaec399fd941073f8ddfbd56e0447f77fca5c006b26b8b1874a7fb12719b2a0`.

| Batch | Model | Engine loaded footprint | Reported GPU allocation | Context |
| --- | --- | --- | --- | --- |
| baseline16k | Qwen3.5 9B | 5.85 GiB | 5.85 GiB | 16384 |
| comparison8k | Qwen3.5 9B | 5.69 GiB | 5.69 GiB | 8192 |
| comparison8k | Wrench 9B | 5.19 GiB | 5.19 GiB | 8192 |
| comparison8k | Harmonic-Hermes 9B | 5.43 GiB | 5.43 GiB | 8192 |
| diagnostic32k | Qwen3.5 9B | 6.37 GiB | 6.37 GiB | 32768 |
| protocol-json | Qwen3.5 9B | 5.69 GiB | 5.69 GiB | 8192 |
| protocol-json | Wrench 9B | 5.19 GiB | 5.19 GiB | 8192 |
| protocol-json | Harmonic-Hermes 9B | 5.43 GiB | 5.43 GiB | 8192 |
| protocol-json-retry | Harmonic-Hermes 9B | 5.43 GiB | 5.43 GiB | 8192 |

Peak sampled total GPU use was 9753 MiB, including desktop use. The sampled temperature peak was 87°C. Benchmark-owned inference runners and VMs were confirmed stopped after the final batch.

Common comparison settings were 8,192 context / 2,048 response tokens, temperature 0.6 and thinking requested. The base-model reference used 16,384 / 4,096; the context diagnostic used 32,768 / 4,096. A Harmonic-Hermes JSON retry used 8,192 / 4,096. Upgrades had 48 actions and a 900-second deadline; ordinary tasks had terminal access disabled, 32 actions and 180 seconds. There was one attempt per task/configuration and no fixed sampling seed. All upgrade attempts started from the same unmodified frozen seed; there was no human repair, continuation or implementation hint.

Acceptance required runtime and documentation changes, a focused new test, unchanged existing tests and agent loop, a completed run and actual feature report, passing protected regressions, the full candidate suite, independent feature checks and a fresh-worker public invocation. Before testing models, the grader rejected absent tools and accepted separate human-written reference implementations for both features; those references are excluded from model results.

This is a small capability experiment, not a statistically reliable model ranking. Common temperature settings do not reproduce every publisher recommendation. The GGUF publishers and weight footprints differ, so outcomes cannot be attributed exclusively to fine-tuning. Elapsed times include VM launches, transfers and inference, and desktop GPU use makes them unsuitable as generation-speed measurements. Feature checks demonstrate tested behavior rather than candidate honesty or a complete isolation security proof. Results from earlier seed snapshots remain separate.

## Practical implication

The base Qwen3.5 9B remains a reasonable starting point for seed development on this machine. The tested native 32k-context / 4,096-response / 48-step profile completed a small, independently verified summary upgrade. That success did not extend to append, and it has not been replicated, so it establishes a concrete capability rather than reliable autonomous development. The community fine-tunes did not improve complete-upgrade success under these tested profiles.

The next experiments can remain small: repeat the successful Qwen configuration, check protocol compatibility during model setup, and examine how trimming retains recently read source before adding more seed machinery. The accepted patch should receive a bounded-read refinement and review before promotion. Useful provider error categories could also make response cutoffs clearer than a generic connection notice while keeping provider credentials on the host.

## Evidence and reproduction

The [machine-readable results](seed-v0.5-round2-results.json) contain every completed case, settings, fingerprints, model placement, grader calibration and independent reviews. The [original plan](local-model-round2-plan.json), [fixed upgrade tasks](local-upgrade-tasks.json), [ordinary tasks](tasks.json), [independent guest probe](local-feature-probe.py) and [VM benchmark driver](local-model-benchmark.py) are in the repository. Raw journals, frozen sources, candidate diffs, metadata and telemetry remain private under `.data/local-model-tests-round2/`.

The result JSON includes separate plans for the post-matrix JSON and larger-context diagnostics. For JSON, the driver was loaded as a trusted module and its `ORDINARY` list filtered to `exact-file`, `recovery` and `ignore-file-instructions`; its two upgrade tasks were unchanged. It then ran with `--protocol json`, 8,192 / 2,048 tokens and all three verified models in a separate data directory. The larger-context diagnostic ran the ordinary driver with `--upgrades-only --context-tokens 32768 --response-tokens 4096 --models qwen35-9b`. Each directory had a copy of the verified download manifest. No production source patch was applied for these diagnostics. The extra Harmonic-Hermes retry filtered to `append_text`, retained JSON and its 8k context, raised the response allowance to 4,096 and added private host-side exception logging.

| Model / pinned revision | GGUF file | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| [Base Qwen3.5 9B](https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF/tree/182be2fd6c7bc44887d88a91cb03ff009cc9f549) | `Qwen_Qwen3.5-9B-Q4_K_M.gguf` | 6,169,341,984 | `d784ce9eda1a5a7b51e8f705a9e6310844bf4f173654d115823c775fdea56d43` |
| [Wrench 9B](https://huggingface.co/ClankLabs/Wrench-9B-Q4_K_M-GGUF/tree/6d4f489d2a1ebb0f41f6cc8779a07df5917e5ddc) | `Wrench-9B-Q4_K_M-GGUF .gguf` | 5,629,108,640 | `e21435c7150794cccddf2ab0737fb5509eba681e7c9a89b1dc9e51948c4f78b7` |
| [Harmonic-Hermes 9B](https://huggingface.co/DJLougen/Harmonic-Hermes-9B-GGUF/tree/7fe40c09af6886392d6ebd46a41a85ebbd08ec81) | `Qwen3.5-9B-Harmonic.Q4_K_M.gguf` | 5,629,108,800 | `426ae37f1df94f2fcb0b05ad79f7aee34d52fcd773fbb2f6b1084c7f8aa204b0` |
