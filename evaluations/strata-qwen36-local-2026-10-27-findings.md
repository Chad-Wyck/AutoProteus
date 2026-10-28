# Strata feasibility and Qwen3.6-35B-A3B local screen

**Qwen3.6-35B-A3B UD-Q4_K_XL runs on this PC through the existing Prism
llama.cpp engine with memory mapping disabled, generating about 28–29 tokens/s.**
Strata's two guarded loading attempts stopped before inference because of
memory pressure. There is **no measured Strata generation rate or MTP result**.

The AutoProteus screen produced correct artifacts for all five ordinary tasks,
but only one satisfied explicit completion. The existing gate therefore skipped
all first/second seed-editing tasks. Upgrade ability remains **untested**, not
0/3 tested failures.

## Model, machine and controls

- AutoProteus `c2c7d13501b165130bcc13994ba0be0344cb58a1`, v0.14.1. Starter
  `ebbbddc665b4f5eadfb9beb6bc47b3bd99bfaf3aa414b7f20980a00c212469de`.
- Windows, GTX 1080 Ti 11 GiB, i5-11600K, 31.79 GiB visible RAM. Observed
  Windows commit capacity was 46.29 GiB, including the currently allocated
  14.5 GiB pagefile. These are observed totals, not a claim about its maximum
  possible automatic growth.
- Unsloth `Qwen3.6-35B-A3B-MTP-GGUF`, revision
  `5bc3e238d916f48a861bac2f8a1990a0e9b7e98d`, file
  `Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf`: 22853663008 bytes, SHA-256
  `55983c5a75a1ab969824077b3bb3de4146e82a9234072b48ad4e8f92ad3fe9f1`.
  Download size/hash and 16 tokenizer round-trip cases passed. No adapter/LoRA.
- Strata v0.2.7 portable Control/runtime and CUDA 12 engine 0.1.52, build
  `a42cc3d7df70+cuda12.9`; the package declares sm_61. Published archive
  checksums and individual engine component hashes were checked. No claim of
  independently verifying the component's Ed25519 signature is made here.
  The source review used upstream `5e8a4cc`; live server code came from the
  pinned portable release package, not an unpinned checkout.
- Native compatible API, text only, one slot, 16384 context, thinking off,
  six CPU worker threads. Strata used 512-token prefill chunks and MTP 0.
  Vision and Strata's host-side MCP execution were disabled; API bound only
  to loopback. Windows settings, application defaults and existing model
  caches were unchanged. The user approved temporarily lowering disk reserve
  and closed Brave; no other user application was force-closed.
- A private watcher sampled RAM/commit headroom every 0.5 seconds and stopped
  only owned inference processes below a 2 GiB floor. Starting an AP guest also
  required at least 4 GiB available physical RAM. These safeguards can stop an
  otherwise potentially runnable configuration; a stop is not an engine OOM
  verdict or model capability failure. No pagefile resizing was performed.

## Loading feasibility

| Configuration | Outcome | Minimum available physical / commit | Peak owned working set |
| --- | --- | ---: | ---: |
| Strata, automatic expert cache | Guard stopped load on commit headroom | 15.67 / 1.48 GiB | 4.24 GiB |
| Strata, expert VRAM capped at 1 GiB | Guard stopped load on physical RAM | 1.95 / 2.91 GiB | 19.59 GiB |
| llama.cpp, default mapped loading | Short response succeeded; guard stopped during longer prompt | 1.97 / 11.14 GiB | 19.03 GiB |
| llama.cpp, loading mode `none` | All four short inference checks completed | 6.15 / 6.72 GiB | 14.83 GiB |

Strata reached its dedicated qwen35moe loading path, checked 753 tensor layouts,
loaded 4.40 GiB of GPU weights and reported its K-quant kernels. It did not finish
loading or generate tokens. Reducing GPU expert cache does not remove its full
host expert copy. MTP 2 and AP VM work under Strata were not attempted after
these resource stops.

The mapped llama.cpp attempt's raw cleanup reason is a connection reset: its
driver catch replaced the earlier guard reason with the resulting transport
exception. The below-floor memory sample and watcher logic identify the
resource-triggered shutdown; raw evidence was preserved. Later private-runner
error handling retained the resource reason separately.

Loading modes were not randomized, cache warmth and available memory differed,
and there was one completed speed run. These observations identify a working
configuration; they do not establish a universal speedup from disabling mapping.

## Working llama.cpp speed

Prism build 10777, commit `e3de71522`, same GGUF, `-ngl 99 -ncmoe 30`, six
generation/prompt threads, 16K context, one slot, batch 256/microbatch 128,
flash attention on, `--load-mode none`. Dense layers and the remaining expert
layers used the GPU; the first 30 expert layers used CPU. No speculative decoder
was configured; the file's extra MTP tensors were ignored by this runtime.

| Request | Prompt tokens | Response tokens | API elapsed | Reported decode rate |
| --- | ---: | ---: | ---: | ---: |
| Short, greedy | 25 | 256 | 9.375 s | 28.67 tokens/s |
| Cold reference prompt, greedy | 4774 | 256 | 46.235 s | 28.68 tokens/s |
| Same reference prompt, greedy | 4774; 4770 cached | 256 | 9.140 s | 28.21 tokens/s |
| Same reference, temperature .6 | 4774; 4770 cached | 256 | 8.969 s | 28.74 tokens/s |

Cold long-prompt processing was 37.292 s, approximately 128 input tokens/s.
Cold model load was 53.875 s. Responses were intentionally capped at 256 tokens;
length stops are not task-completion verdicts. Time to first streamed content
was not measured. The default mapped attempt's one short response decoded at
16.75 tokens/s before its later resource stop; this is not a complete paired
engine/loading-mode benchmark.

During AP's inference benchmark and five ordinary tasks, 21 measured responses
reported 1123 generated tokens over 40.107 generation seconds: about **28.0
tokens/s**, with median reported per-response rate 27.64. This excludes prompt
processing, model loading, tool execution and the separate connection qualifier.

## AutoProteus screen: correct output versus explicit completion

The working configuration passed the standard production-adapter native
qualification first try: eight requests, no format repairs. Scripted protected
calibration passed. The full one-repeat plan scheduled hashing, CSV and formatting
first extensions plus eligible second extensions, after five ordinary tasks.

| Ordinary task | Independent artifact check | Final native finish call | Composite result |
| --- | --- | --- | --- |
| Exact file | Pass | No | Waiting; fail |
| Precise JSON edit | Pass | No | Waiting; fail |
| Missing-file recovery | Pass | No | Waiting; fail |
| Unicode file | Pass | No | Waiting; fail |
| Fix addition function | Pass | `finish(completed)` | Pass |

The four waiting cases ended with ordinary prose stating that the task was done,
with API `finish_reason: stop`. They did **not** request more information in that
prose. The current host adapter conservatively maps plain replies without a
finish call to `needs_input`; the seed's finishing requirement was not satisfied.
The fifth case used the supplied finish function correctly. This is a concrete
completion-contract mismatch, not four incorrect files or four malformed action
responses.

The ordinary gate was **1/5**, with artifact correctness **5/5**. No first
extension, activation/use or second extension ran. Six conditional cells were
marked not_run. There were no model-task retries, coaching or candidate repairs,
and no source changes during screening. A preparation-only private profile
loader error was corrected before the plan or any screen inference started.

The research profile used 4K responses, temperature .6, top-p .8, top-k 20,
thinking off and per-request seed 104729. Intended upgrade/use allowances were
128 actions, 3600 seconds and 65536 generated tokens, but those tasks were never
entered. Fresh servers separated measured screen attempts. The 16K context and
different model/task mix prevent treating this as a matched comparison with the
9B 128K repeatability batch. The 35B model's approximately 3B active parameters
also do not make it equivalent to a dense 35B model.

The next useful qualification question is whether a small, generic clarification
of the explicit finishing contract fixes this behavior. A separately labelled
diagnostic upgrade could measure editing despite the failed ordinary gate, but
neither was run here. No default, seed or grader change is established by these
results.

## Local evidence

Root: `.data/strata-qwen36-20261027/`.

- `release.json`, `model-metadata.json`, `model-receipt.json`, `prepared.json`:
  versions, published hashes, component identity, model pin and prepared controls.
- `windows-memory-before-load.json`, `memory-summary.json`: Windows accounting
  and read-only aggregation of sampled resource data.
- `strata-mtp0-benchmark-01/`, `strata-mtp0-expert1-benchmark-01/`,
  `llama-mtp0-benchmark-01/`, `llama-mtp0-nommap-benchmark-01/`: command/config,
  logs, memory samples, measured responses where available and cleanup receipts.
- `ap-qualification.json`, `ap-qualification-calls.jsonl`: native connection check.
- `ap-screen-llama16k/`: frozen plan, calibration, queue, all basic-task exports
  and provider traces, plus explicit skipped-extension records.
- `ap-screen-report.md` / `.json`: closed-study report. Its zero upgrade counts
  mean untested after the failed gate, not measured zero success rates.
- `ap-screen-runtime.json`, `ap-screen-cleanup.json`: frozen runtime settings,
  guards and owned-service cleanup. Dedicated ports 47845/47846 were free afterward.

No model-generated code ran on the host. All AP task commands ran in disposable
VMs. Inference services and test VMs were stopped after the screen. Only local
research records were added to the checkout; nothing was committed or pushed.
