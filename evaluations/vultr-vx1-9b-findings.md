# Vultr VX1: CPU-only Qwen3.5 9B pilot

On 14 October 2026, Qwen3.5 9B Q4_K_M completed all five selected ordinary AutoProteus tasks on a Vultr VX1 server with four vCPUs and 16 GB RAM. All candidate commands and checks used AutoProteus's normal QEMU/KVM boundary. The five tasks took 748.12 seconds in total.

At the advertised USD 0.153/hour rate for the 4-vCPU/16-GB/240-GB-local-storage plan, those task runtimes represent USD 0.03180 of compute, averaging USD 0.00636 per completed task. These are runtime-based cost estimates, not invoice amounts: initial server setup, reserved idle time, billing minimums, regional variation and tax are additional. The server remains billable until destroyed.

| Task | Result | Seconds | Tool actions | Model requests | Runtime compute, USD |
| --- | --- | ---: | ---: | ---: | ---: |
| Exact file creation | Pass | 167.44 | 2 | 3 | 0.00712 |
| Precise JSON edit | Pass | 181.30 | 3 | 4 | 0.00771 |
| Exact Unicode text | Pass | 109.59 | 2 | 3 | 0.00466 |
| Copy while preserving original | Pass | 154.11 | 4 | 4 | 0.00655 |
| Missing-file recovery | Pass | 135.68 | 3 | 4 | 0.00577 |

The generation smoke sample produced 128 tokens at 7.30 tokens/second using four inference threads. Actual ordinary requests used Ollama's automatic two-thread selection; observed request logs showed approximately 6.9 generation tokens/second and 29.5 prompt tokens/second. Most basic-task latency was prompt processing across tool turns. The smoke sample is not end-to-end coding throughput.

This is a workable, inexpensive server for serial basic-task experiments. The evidence does not yet establish a cost per successful autonomous upgrade, so it does not justify scaling up spending on that workload. Long conversations were substantially slower than the basic tasks.

## Method and provenance

- Source: public `main` commit `fce3f6307e9513d3923957548e1345a54202ff31`, verified against GitHub before inference. The server received a clean archive of that commit.
- Host: Ubuntu 24.04.5 LTS, x86-64, Linux 6.8.0-146-generic; AMD EPYC-Turin CPU presented as four vCPUs/two cores/four threads; approximately 15.6 GiB usable host RAM and 240 GB local storage. No GPU.
- Execution: separate unprivileged `autoproteus` account with KVM access. Default diskless, network-free AutoProteus VMs; no native execution or candidate promotion.
- Isolation qualification: all ten real VM tests passed. The unchanged starter's 40 protected guest tests passed before model inference.
- Inference: checksum-pinned Ollama 0.40.4, one model loaded and one request slot, listening only on host loopback.
- Model: `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q4_K_M`; weight size 6,169,341,984 bytes, SHA-256 `d784ce9eda1a5a7b51e8f705a9e6310844bf4f173654d115823c775fdea56d43`. The downloaded blob was rehashed and matches the earlier local/cloud weight file.
- Ordinary profile: native tools, thinking disabled, temperature 0.2, no fixed sampling seed, 8,192 context tokens, 2,048 response tokens, 32 actions, 600-second task/request deadlines, terminal disabled. One attempt per task, serial execution.
- Host supervision: a background system service survives SSH disconnection, with a four-hour process deadline, a 13 GiB service memory ceiling and no service swap allowance. This does not automatically stop server billing.

The ordinary tasks are a small sizing/reliability sample, not the complete sixteen-task suite or a comparison against a GPU. Different source revisions, context sizes, inference backends and sampling settings prevent treating earlier reports as a controlled hardware comparison.

Public `main` advanced to `4281750d4fcb25dfc79628b66c7d7728652ae380` during the trial, confirmed directly after completion. It was not incorporated into the frozen experiment; these results describe `fce3f63` only.

During the upgrade, the inference logs repeatedly showed reuse of only the first approximately 843 prompt tokens, followed by reprocessing much of the conversation. The tested seed appends the changing action counter to its initial system message (`autoproteus/agent.py`, `messages`), before the task and history. This is a plausible contributor to cache invalidation and CPU latency; no controlled cache-layout comparison has been run, and the tested source was not changed to optimize it.

## Setup reproducibility

Fresh appliance preparation stopped at the pinned Alpine package-index checksum. The current upstream `APKINDEX.tar.gz` hashed to `3f93c63dc198aa3f97b62378b41e464bebd4f30f62cc58bafcc7ea82f5c0b10e`; the repository pins `24fc2ccb08f3125429a38b31bd6c76a7b394c6236df0975760dc8259e50dfbd5`.

All Linux appliance dependencies were available in the existing local cache and individually matched their pinned hashes. Those exact bytes were transferred to the server; appliance preparation and all hardware isolation tests then passed without changing the lock file or disabling integrity checks. A fresh installation still needs the verified cache or maintenance of the upstream download strategy.

## Upgrade trial

A separate, single `file_summary` trial was interrupted by an automatic OS service restart after approximately 2,065.38 seconds (34 minutes 25 seconds), before its 45-minute deadline. Its profile was 16,384 context tokens, 4,096 response tokens, 128 tool actions and a 600-second model-request limit, with terminal access inside the VM. Thinking was disabled. The feature grader had passed calibration with absent-tool negatives and human-written reference positives, including public-tool invocation through a fresh worker.

At interruption, the saved journal contained 14 completed model responses and 14 read actions, 764 generated tokens and 63,431 prompt tokens. The exported candidate matched the unchanged starter: no runtime implementation, new tests or documentation had been written. There was no accepted upgrade. This is an infrastructure-interrupted attempt, not a completed model failure or a timeout; it cannot establish the model's success rate for upgrades. Its elapsed runtime represents approximately USD 0.08778 at the advertised rate, with no completed upgrade to use as a cost-per-success denominator.

The service peaked at its 13 GiB memory ceiling, including file cache; sampled host available memory stayed above 2.53 GiB. The host and service used no swap. The journal records a requested service stop and restart, rather than an out-of-memory kill. The memory ceiling and 16K context remain practical limits for larger experiments; this was not a 32K-context trial.

## Interruption and recovery

Ubuntu's unattended security updates invoked `needrestart`, which stopped the experiment service at approximately 23:09:11 UTC. The replacement process refused to overwrite the existing run, preserving its results. The original report was left untouched, including its stale `running` status. A separate postmortem report explicitly records the interruption; all original run-file hashes and all protected source hashes matched before and after recovery.

A narrowly scoped `needrestart` rule now excludes `autoproteus-pilot-run-*.service` from automatic restarts. Security updates and other service restart rules remain enabled. The rule loaded successfully and was checked against both experiment unit names. This configuration is also included in the saved bootstrap procedure. It defers library adoption until a bounded job finishes; it does not prevent reboots or every possible service interruption. The additive configuration follows [Ubuntu's documented service override mechanism](https://github.com/canonical/ubuntu-server-documentation/blob/main/docs/how-to/software/automatic-updates.md).

A separate post-update recovery diagnostic passed all 40 protected guest tests and the same exact-file task in 164.34 seconds, using the original 8K ordinary profile and frozen source. It is excluded from the original five-task sample. Original evidence and protected source hashes still matched afterward. The model engine stopped cleanly after the check; no experiment is left running, although the server remains billable.

Private evidence is saved locally under `.data/vultr-pilot/` and remotely under `/opt/autoproteus-pilot/.data/vultr-pilot/`. `run-01/basic-results.json` preserves the local report after the five ordinary tasks. The original remote `run-01/report.json` is retained as recorded; `run-01-postmortem/report.json` contains the recovered verdict, and `recovery-01/report.json` records the separate recovery diagnostic.

The local `results-20261014.tar.gz` archive includes the original journals, postmortem, recovery results, resource samples, inference logs and service/update audit. Its SHA-256 was verified after transfer: `af886effcac9b138af5de63c0261874547bc921a282de8bf2d4c4045b1de3fc0`.

Sources: [Vultr pricing](https://www.vultr.com/pricing/#vx1-compute), [server billing](https://docs.vultr.com/support/platform/billing/how-am-i-billed-for-my-servers), [tested source commit](https://github.com/Chad-Wyck/AutoProteus/commit/fce3f6307e9513d3923957548e1345a54202ff31).
