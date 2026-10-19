# Vultr: Qwen, K2 and Gemma seed-editing comparison

Status: stopped at the user's request on 15 October 2026 at 08:36:52 UTC (02:36:52 America/Regina). No model produced an accepted seed improvement. Qwen and K2 completed two bounded attempts each without runtime edits; Gemma's attempts were interrupted by memory failure and then the requested stop.

The user authorized an initial comparison lasting up to four hours, focused on effective edits to AutoProteus's seed. Price is excluded as a test factor at the user's request. The batch has an absolute deadline of 15 October 2026, 09:20 UTC (03:20 America/Regina), with time reserved for independent grading and cleanup.

The server exposes **two vCPUs, 16 GB RAM and 120 GB local disk**. This differs from the earlier four-vCPU/240-GB Vultr pilot. Automatic APT maintenance is masked, automatic update-driven reboots are disabled, and `needrestart` is configured to report only. The setup passed all **11 real QEMU/KVM isolation tests**.

CPU topology reports one core with two threads. The default inference runtime selected `n_threads = 1` and `n_threads_batch = 1`; the experiment service permits up to two logical CPUs but does not override that runtime default. This is a material throughput detail, and results should not be presented as a benchmark of a tuned two-thread configuration.

## Model selection

The [Artificial Analysis leaderboard](https://artificialanalysis.ai/leaderboards/models), read on 14 October 2026 in America/Regina, was used to select compact open-weight candidates. Its Intelligence Index v4.3.2 measures a broader workload than this seed-editing experiment. Estimated scores are marked below.

| Model | AA score used for selection | Tested weight format | Core weight bytes |
| --- | --- | --- | ---: |
| Qwen3.5 9B | 13 estimated, non-reasoning; 11 reasoning | Q4_K_M | 6,169,341,984 |
| K2 Horizon 7B | 21 | Q4_K_M | 5,592,217,984 |
| Gemma 4 12B | 14 estimated, reasoning; 9 estimated, non-reasoning | Publisher QAT Q4_0 | 6,975,879,296 |

All three selected repositories declare Apache 2.0 licenses and allow public weight downloads. Core GGUF files were rehashed against revision-pinned Hugging Face metadata before inference. K2's core-size name excludes some parameters; its earlier GGUF metadata reported approximately 9B total parameters. Gemma's quantization-aware training differs from the other models' quantization, so formats are recorded explicitly.

Model references: [Qwen](https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF), [official K2](https://huggingface.co/IFM/K2-Horizon-7B-GGUF), [official Gemma QAT](https://huggingface.co/google/gemma-4-12B-it-qat-q4_0-gguf). Exact revisions and SHA-256 identities are in the saved comparison plan.

## Method

- Start from public `main` at `4281750d4fcb25dfc79628b66c7d7728652ae380`, plus the explicitly approved prompt-stability patch described below. Each primary attempt starts from a fresh copy of this same adjusted seed.
- Run inference on the CPU with checksum-pinned Ollama 0.40.4. Load one model at a time; serve only on host loopback.
- Run every candidate command, regression suite and functional probe inside network-free disposable QEMU/KVM VMs under a separate unprivileged account. There is no native fallback or candidate promotion.
- Calibrate feature graders with absent-tool negatives and human-written reference positives before model trials.
- Plan `file_summary` and `append_text` once per model, with 25 minutes per feature, a ten-minute limit per model request, 64 tool actions, 32,768 context tokens, 2,048 response tokens, temperature 0.2 and no fixed sampling seed. After Gemma's actual 32K workload exhausted memory, its separate fallback used 16,384 context tokens and up to twenty minutes per feature. The user stopped that fallback before its first feature completed; Gemma's second feature was not attempted.
- Disable thinking where the runtime exposes that switch; record models with no such switch separately. Prefer native tools after a two-turn protocol diagnostic; record any JSON fallback explicitly.
- Grade exported edits independently, including unchanged protected source/tests, existing regressions, a new focused test file, Unicode character boundaries, CRLF, invalid UTF-8, path validation, failed-write preservation, the candidate's full test suite and invocation through a fresh worker.
- Report functional implementations separately from fully accepted submissions. Check runtime edits even when the model stops early or times out.
- A full feature pass requires the independent edge cases and candidate test suite to pass; nominal basic behavior is recorded separately in raw reviews. Acceptance additionally requires successful completion, a focused new test file, permitted edits only, unchanged protected source/tests, regressions and invocation through a fresh worker. Protocol compatibility alone earns no improvement credit.
- Record elapsed time, tool actions, generated/prompt tokens, actual model placement and host/service memory use. Preserve source fingerprints before and after the batch.

This is a small practical comparison within a CPU/time budget. It does not reproduce AA evaluation settings, publisher-recommended reasoning allowances, unquantized models or maximum advertised context lengths. Models supporting reasoning may behave differently with thinking enabled. Weight size alone is not a RAM measurement; actual load and memory use must be verified.

The initial 8K run was stopped after the user raised the context limit. Its first upgrade request had not completed a model response or tool action, and no edits were made. Its raw `budget_stopped` label records the runner's generic cancellation path; the actual cause was the requested context reassessment. Those files are preserved separately and excluded from model verdicts. The original four-hour absolute deadline remains unchanged.

All three models passed separate 16K and 32K load checks alongside fresh protected guest regressions. At 32K, Ollama reported approximately 7.07 GiB for Qwen, 9.98 GiB for K2 and 8.25 GiB for Gemma. Adding a full 2 GiB VM allowance and 0.5 GiB controller margin remained within the 14 GiB service ceiling for every model. Service swap is disabled. These checks establish load-time capacity and guest coexistence; they are not full-context saturation tests, so resource samples continue throughout actual tasks.

The frozen seed's `Agent.messages` uses a conservative serialized-byte allowance of `(context_tokens - response_tokens - 128) * 2`, including tool schemas, instructions, task and history. With a 2K response allowance, that is only 12,032 bytes at 8K context, versus 61,184 bytes at 32K. The two relevant implementation files total roughly 11 KB before JSON serialization overhead. This is a concrete reason to avoid the initial 8K setting for this source-editing comparison. The same estimate now includes late runtime context before history trimming.

## Approved prompt adjustment

The stock seed inserted a changing used/remaining action counter into its first system message on every turn. It also inserted the latest `todo.txt` there. Changes near the opening can limit common-prefix cache reuse during local inference. After discussing this with the user, Codex made a separate harness adjustment: remove the live counter, place the current checklist at the conversation tail, and append an exhaustion notice only at the action cap. The opening instructions remain stable as action counts and checklist contents change.

The enforced cap is unchanged: failed calls and individual calls in a batch count; excess calls pause the task; finishing is free; Resume provides a fresh allowance. The existing budget tests were updated to verify the stable opening and late exhaustion notice, and a new test covers checklist changes, preserved task text and serialized input limits. All 65 seed/native/provider tests passed on Ubuntu; Windows passed with seven platform-specific skips.

This is an assistant-authored setup change, **not an improvement produced by any tested model**. The patch, normalized source hashes and base commit are saved in `stable-prompt.patch`, `stable-prompt-manifest.json` and the primary report's plan. The primary comparison is a common adjusted condition, not a controlled before/after experiment proving a performance benefit.

Development handoff: **the opening prompt was changed during this experiment**. The implementation is in `autoproteus/agent.py`, with coverage in `tests/test_seed.py`; matching prose updates are in `README.md` and `SEED.md`. The complete local handoff is `.data/vultr-64.177.47.120/development-prompt-handoff.patch`, with a companion manifest. It has not been committed or pushed. Keep the stable prompt change separate from model-authored candidate diffs when reviewing results.

The original `stable-prompt.patch` and its manifest preserve the exact code variant tested on the server. Documentation corrections and one comment identifying `_run` as the action-cap enforcer were made locally after the input freeze. All models saw the same frozen recipe, including its now-stale sentence describing the live counter. The complete development handoff includes the corrected wording.

The development handoff also contains a post-freeze boundary fix: if user instructions exactly fill the input allowance, omit the optional exhaustion notice so it cannot block the free final request or displace user text. A regression test covers exact-fit requests in both native and JSON protocols. This follow-up passed 66 tests on Windows with seven Linux-specific skips; it was not introduced into the frozen model comparison. The earlier 65-test Ubuntu result applies to the frozen experiment variant.

Initial runtime verification found one distinct opening across Qwen's first three saved requests. On its second task request, the engine retained 1,766 cached tokens from a 1,913-token prompt and processed the remaining 147 in 9.54 seconds. The provider's `prompt_eval_count` reported the full 1,913 tokens, so that field alone must not be read as the number recomputed. This confirms reuse in that request; it does not establish an overall task speedup or successful editing.

A separate limitation appeared after Qwen's eighth action: its repeated large test-file reads filled the seed's conservative byte allowance. The ninth saved request dropped earlier action groups, changing the retained conversation prefix despite the stable opening. The engine restored only 1,722 cached tokens for that 13,703-token prompt. Nominal 32K model capacity therefore does not mean the current seed retains 32K tokens of history; input packing and CPU prefill remain material limits. This trimming policy was held common across models and was not relaxed during the experiment.

The completed stock Qwen `file_summary` baseline used **1,800.09 seconds and six inspection actions**, made no edits and was neither functional nor accepted. The next stock `append_text` attempt was operator-stopped after one inspection action to apply the approved adjustment; it is excluded from comparison verdicts. Both original journals are preserved in `run-32k-01` with an operator-stop note.

## Results

Final reports, resource samples, journals and candidate snapshots are preserved locally under `.data/vultr-64.177.47.120/evidence/vultr-comparison/`. The source fingerprint was unchanged across all three primary run directories. No candidate was promoted.

| Model / feature | Task seconds | Actions | Result |
| --- | ---: | ---: | --- |
| Qwen3.5 9B / `file_summary` | 1,438.02 | 8 | Per-request timeout while processing trimmed history; no edits, no functional or accepted implementation |
| Qwen3.5 9B / `append_text` | 1,464.48 | 10 | Per-request timeout after repeated test-file inspection and history trimming; no edits, no functional or accepted implementation |
| K2 Horizon / `file_summary` | 1,500.10 | 16 | Overall task timeout after inspection; no edits, no functional or accepted implementation |
| K2 Horizon / `append_text` | 1,500.06 | 14 | Overall task timeout after inspection; no runtime edits, no functional or accepted implementation |
| Gemma 4 12B / `file_summary`, 32K | Interrupted | 7 | Service reached its 14 GiB ceiling and was OOM-killed; no runtime edits. Excluded from completed task counts |
| Gemma 4 12B / `file_summary`, 16K | Interrupted | 4 | User-requested stop during inspection; no write actions. Excluded from completed task counts |

K2 produced **0/2 accepted improvements**, using 3,000.16 task seconds. Overall, the four completed adjusted-prompt attempts yielded **0/4 accepted improvements** and no runtime source edits. Gemma has no completed coding trial, so it should not be given a comparable 0/2 task score. Its 32K session wrote only `todo.txt`, inspected files and ran an early seed check; its 16K session performed two directory listings and two file reads.

Qwen's two primary attempts therefore produced **0/2 accepted improvements and no runtime edits**, using 2,902.50 task seconds (48 minutes 22.5 seconds). This excludes preflight, setup and the separately preserved stock baseline. Its raw completed task journals and candidates were backed up locally before the next model's trials.

For this Qwen attempt, `timed_out: false` means it did not reach the **overall task** cutoff. Its `failure_kind: timeout` and saved notice identify the distinct **per-request** timeout. Nine requests were issued; eight returned responses, and the ninth expired. The eight completed responses generated 340 tokens in total; cumulative reported prompt counts include reused context and must not be treated as recomputed tokens.

## Inference cleanup and continuation

After K2's first task reached its overall cutoff, the canceled HTTP request was still processing a large prompt in the inference service while the first `append_text` session waited. That waiting session completed no response or action. It was operator-stopped and excluded, rather than charged as a model editing failure. All three completed primary results above remain in `run-stable-32k-01`.

`run-stable-32k-02` completed K2 `append_text`, then failed during Gemma `file_summary`. It asserted the identical seed fingerprint (`8255385c8c4fe75748256f9eb98c7c11f1d7d3ea22315080008898b47df3e149`) and retained the model pins, context, output budget, temperature and request/task limits. The runner closed the entire inference service after each feature, before grading, and started a fresh one before another feature. This avoided stranded inference occupying the next task's slot. The revised lifecycle and resulting cache/load differences are a comparison limitation; this is not a strict controlled timing ranking across models.

Development observation: canceling the host caller can leave its blocking HTTP worker alive during prefill until a response or socket timeout. The runner workaround clears the complete service between features. A production cancellation fix is separate from the opening-prompt handoff; no such controller change is included in that patch.

## Memory failure, final stop and evidence

Gemma's 32K load-only check passed, but the actual workload grew to the 14 GiB service ceiling. The service finished with `Result=oom-kill`, `MemoryPeak=15032385536` and zero service swap. Its generic JSON `budget_stopped` label is not the cause: `run-stable-32k-02/oom-note.json` and the saved service audit identify the OOM. The host remained running. Load-time capacity therefore did not establish practical 32K workload fit.

`run-stable-16k-03` retried Gemma alone with the same frozen seed, 16K context, 2K response tokens and an allowance of up to twenty minutes per feature. The user requested an early stop during its first feature. It had four inspection actions and no write actions. Its service also approached the memory ceiling, with allocation-limit events but no recorded OOM kill. The stop completed successfully; the raw report uses the runner's generic `budget_stopped` status. Neither Gemma interruption is counted as a completed coding failure.

The server's narrow CPU throughput, large file reads, conservative history packing and Gemma's actual memory growth limited this trial. These results establish no useful seed improvements under the tested conditions; they do not establish that the models cannot edit code on faster hardware or with a different harness.

The experiment service is inactive and no live model or guest VM process remains. One defunct model child appeared in the immediate process check; it consumes no compute. The Vultr instance remains provisioned, and automatic updates remain paused. No CPU tuning probe or additional model tests were started after the user's stop request.

The complete evidence archive is `.data/vultr-64.177.47.120/comparison-results-20261014.tar.gz`, verified SHA-256 `62a4ce8a88e764f9985ea5598afc9d0dc787d508e4bc9c09457b7834d3a5018a`. The extracted evidence includes all run directories, plans, journals, resource samples, frozen starter sources, candidates and service audits. `final-summary.json` merges the four completed primary trials while preserving each run's context setting. The OOM service audit is authoritative even though the resource sampler stopped before its final OOM event.

The ready-to-forward development patch is [stable-prompt-handoff.patch](stable-prompt-handoff.patch). It matches the four current local files and the saved handoff manifest; `git diff --check` and reverse application checks passed. The tested variant passed 65 Ubuntu tests. The final handoff's additional exact-fit boundary regression passed the 66-test Windows suite with seven platform skips; that final boundary fix was not tested in the model comparison or revalidated on Ubuntu. The patch is Codex-authored and remains uncommitted and unpushed.
