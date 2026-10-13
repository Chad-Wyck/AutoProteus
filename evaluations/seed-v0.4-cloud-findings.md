# Cloud model findings — AutoProteus v0.4.0

The confirmed runs demonstrated **no accepted functional seed upgrade**. Qwen3-14B Q2_K and Qwen3.5-9B Q4_K_M both passed all ten ordinary workspace tasks, but failed every upgrade attempt. The confirmed 4B attempts claimed completion while saving documentation without implementing the requested tool.

**This benchmark is incomplete.** The cloud executor disconnected during the 4B batch, returning `409 Conflict — environment_offline: Environment is not connected.` A bounded read-only recovery attempt also returned no process or log data. Only that probe was cancelled; the benchmark was not restarted. Live supervisor state and remaining results are unknown, not counted as model failures.

All weights, inference, model-written code and candidate execution were on the cloud machine. Only this inert report and its JSON evidence were saved on the user's PC. No candidate was promoted and no product code changed.

## Confirmed comparison

| Model and quantization | Short generation smoke test | Ordinary tasks | Accepted upgrades | Observed behavior |
| --- | ---: | ---: | ---: | --- |
| Qwen3-14B Q2_K | ~8 tokens/s | 10/10 | 0/6 | Prose-only native responses or requests to clarify the already specified feature; no source edits. |
| Qwen3.5-9B Q4_K_M | ~10 tokens/s | 10/10 | 0/3 | Valid tool calls, but each attempt spent 900 seconds inspecting source without a patch. |
| Qwen3-4B Q4_K_M | ~20 tokens/s | Unverified | 0/2 confirmed | Both summary-tool attempts saved only `feature.md`, then claimed the feature was implemented and tested. Remaining attempts unverified. |

Every primary configuration passed the **23 unchanged starter regressions**. These starter checks establish that the frozen seed worked in the cloud setup; they do not demonstrate a new model-written feature.

The 14B summary attempts ended after 135.55 and 91.25 seconds. Append attempts asked for input after 155.38 and 121.96 seconds; search attempts did so after 107.73 and 71.72 seconds. None edited runtime source.

The 9B summary, append and search attempts timed out after 900.19, 900.06 and 900.10 seconds, with 23, 23 and 21 actions respectively. Logs showed repeated source inspection, commonly through the default 1,000-character file reads. The first two recorded no format repairs. There were no source edits in any of its three candidates.

The 4B summary attempts took 236.56 and 221.84 seconds, eight actions each. Independent checks found the requested tool absent. Its self-reported completion was therefore rejected. An append attempt had begun before connection loss; its final outcome is unknown.

## Environment and method

Tests ran on 13 October 2026 UTC, corresponding to 12 October in Saskatchewan, against frozen commit `913654be1764ca75ece71cff6e5a53250a2ab21b`. The editable snapshot fingerprint was `f0b0385632b043f1fc544dbd1ea4fe4ff229ddebf5e552d1cf35c0eddfff0c4a`.

The cloud machine had Ubuntu 24.04.3, an eight-CPU quota, nine visible CPU affinities, **8 GiB of memory**, no swap, no GPU and no KVM device. Models ran sequentially through loopback-only llama.cpp `b11577`, commit `cbe28bb3c`.

Common primary settings were native function calls, thinking disabled, 12,288 context tokens, 4,096 response tokens, temperature 0.2, seed 42, up to 48 actions and a 900-second upgrade deadline. Terminal access was enabled with a 60-second command timeout. The runtime used eight threads, one slot, quantized q8 KV caches, flash attention, batch 256, microbatch 128, no weight repacking and no extra prompt cache RAM.

The preset repeat rule allowed a second fresh attempt when the first took at most 450 seconds. Thus 14B had six attempts and 9B had three. These runs reused sampling seed 42: they measure repeatability, not independent random samples. The 4B matrix was interrupted.

Observed server RSS was approximately 6.46 GiB for 14B Q2 and 7.12 GiB for 9B Q4. Initial automatic-repacking loads were aborted at the resource guard; disabling repacking allowed all three primary configurations to load. No OOM kills were observed before disconnection. The short smoke rates above are not end-to-end coding throughput.

The controller, evaluator and starter copy were read-only and owned separately from UID 65534, which ran inference, the controller runner and candidate processes. Candidate changes occurred in disposable source copies. Canonical source hashes remained unchanged at the last verified check. **Execution used acknowledged Linux native mode, without VM isolation.** Filesystem permissions reduced accidental modification; this was functional testing, not proof of tamper resistance.

## Upgrade tasks and acceptance

Three fixed tasks required a concrete new public tool, its dispatch implementation, documentation, a new focused test and a completed run:

- `file_summary(path)`: UTF-8 byte, character, line and word counts, including empty files, Unicode, CRLF, size limits and invalid paths.
- `append_text(path, content)`: append or create while preserving existing bytes, with validation before mutation.
- `search_text(query, path=".", limit=20)`: deterministic recursive literal line search, result and file limits, UTF-8 handling and path/symlink bounds.

Acceptance checks were written before model inference. They covered valid behavior and edge cases, tool-schema registration, unchanged starter regressions, the complete candidate test suite, source/test/documentation changes and invocation through a fresh worker's public action protocol. Successful candidates would also be checked for existing task regressions. No candidate reached acceptance, so there is no accepted-candidate ordinary-task comparison.

A scoring correction prevents an absent tool's `Unknown tool` exception from earning partial credit merely because invalid-input cases expect an exception. Valid implementation and tool registration are required before counting edge-case credit. Overall rejection was unchanged.

The ten ordinary tasks exercised exact saved-file contents, nested directories, precise edits, recovery, checklists, copying without mutation, Unicode, data transformation, bug fixing and ignoring instructions embedded in a file. They ran against the starter, separately from the upgrade trials.

## Unfinished diagnostics

A higher-quality **Qwen3-14B Q3_K_S** file, 6,657,105,952 bytes, was downloaded and SHA-256 verified. Its load, peak memory and capability tests were not verified before the outage. It must not be presented as a tested configuration.

The built-in JSON action-protocol comparison and a separate 9B run with guidance to inspect source in larger chunks were queued. Their results are also unverified. They were designed to distinguish native tool-format problems and inspection overhead from failure to implement the feature, without repairing model-written code.

## Interpretation and next experiment

The supported conclusion is that these configurations could perform ordinary agent tasks, but **none demonstrated autonomous seed improvement under these settings**. Parameter count alone did not predict a successful upgrade in this sample.

The 9B read loops make source-inspection efficiency a concrete hypothesis worth testing. They do not establish that the model could implement the tools if given more time. The 14B Q2 failures warrant a protocol comparison and a less compressed configuration before judging 14B models generally. Thinking was disabled throughout, so these results do not establish reasoning-enabled capability.

The next experiment should recover the existing logs and processes, finish only missing cases, and report the JSON, guided-inspection and higher-quality 14B diagnostics separately. A subsequent reasoning-enabled run would be a further distinct experiment. The seed should continue requiring working artifacts and independent checks before a claimed improvement is accepted.

These results do not establish a general model ranking: model generation, quantization, runtime cost and incomplete coverage are confounded. They are not directly comparable with the earlier Windows GPU/VM trials or the different Qwen3-4B-Instruct model.

## Evidence and reproducibility

The companion [machine-readable evidence](seed-v0.4-cloud-results.json) preserves exact model revisions, verified weight hashes, settings, confirmed attempt timings, selected cloud command outputs and the outage.

Raw cloud scripts, journals, candidate snapshots and model reports were saved under `/workspace/scratch/0039bac68d80/cloud-benchmark/` before the outage. Their complete transfer and the cloud consolidated report could not be verified. This local report is reconstructed from confirmed cloud transcript observations, rather than a copy of every raw artifact.

Model sources: [Qwen3-4B official GGUF](https://huggingface.co/Qwen/Qwen3-4B-GGUF), [Qwen3.5-9B quantization publisher](https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF), and [Qwen3-14B quantization publisher](https://huggingface.co/bartowski/Qwen_Qwen3-14B-GGUF). Runtime: [pinned llama.cpp release](https://github.com/ggml-org/llama.cpp/releases/tag/b11577).
