# AutoProteus v0.2.0 local model and precision screen

19 October 2026. This is exploratory screening, with one attempt per prescribed extension and profile. It does not establish repeatability or a model ranking.

**OxCoder 9B Q6 and the separate Qwen3.5 9B Q6 follow-up each earned one accepted first extension. Neither produced a fully accepted growth chain. However, both second candidates passed every direct check for the new and retained tools, plus fresh public calls; the same two protected context tests blocked verification.** A separate diagnostic reproduced those test failures by adding only tool-catalog metadata to the unchanged trusted seed.

The navigation pilot accepted 1/3 upgrades in each arm. Its outline tool was never called, so this pilot provides no evidence that using source outlines improves editing. Swift loaded successfully but was too slow for two basic-task deadlines on this machine. LFM was fast at generating tokens but had recurring protocol difficulties.

## Frozen setup and scope

- Starter: v0.2.0, Git commit `aed23d3b73d304c32ae86a9b247fc947c7f4e502`.
- Starter fingerprint: `2e941e2256a467c2f7f61c71f1d84b97a28190f39b96928a16994b7d72447569`.
- Windows 11, GTX 1080 Ti with 11 GiB VRAM, approximately 32 GB physical RAM.
- Primary runtime: verified PrismML `prism-b10777-e3de715`, CUDA 12.4, one private loopback server and one model at a time. This was the existing compatible runtime, not a newly installed upstream release.
- Standard production provider adapter, without the earlier experimental tool-call-ID rewriting. Model-written source ran only in disposable VMs. No operator repaired or promoted a candidate.
- Screen: two tool-format benchmark calls, three ordinary tasks, two independent first-extension contracts (`sha256_file`, `format_json`), then one conditional second extension per accepted parent. CSV was not a primary screening contract.
- Extension allowance: 128 actions, 4,096 response tokens per request, 65,536 generated tokens and 1,800 seconds. Growth development, grading, activation and final use share the allowance. Ordinary tasks have a separate 240-second/8,192-generated-token limit.
- Thinking disabled for Qwen and OxCoder; publisher-oriented thinking/sampling settings retained for the other families. Context: 131,072 for Qwen/OxCoder/Ornith, 128,000 for LFM, 65,536 for Swift/Nemotron; Q8 KV cache throughout. Exact settings, weight hashes, revisions, templates and launch commands are saved with each plan.

These are practical configurations with different protocols, contexts and sampling, rather than an isolated comparison of model weights. The tasks prescribe the capability and contract; this is directed self-extension, not evidence of autonomous capability discovery.

## Primary screen

| Profile selected by the initial rule | Ordinary tasks | Accepted first extensions | Verified second extensions |
| --- | ---: | ---: | ---: |
| Qwen3.5 9B Q4_K_M, native | 3/3 | 0/2 | Not eligible |
| OxCoder 9B Q6_K, native | 3/3 | **1/2** | 0/1 |
| LFM2.5 8B-A1B Q6_K, JSON | 3/3 | 0/2 | Not eligible |
| Ornith 1.5 9B Q6_K, JSON | 2/3 | 0/2 | Not eligible |
| Swift 1.5 Qwen3.8 27B GSQ-RCO IQ3_S, native | 1/3 | Not run | Not run |
| Nemotron Nano 9B v2 Q4_K_M, native | 3/3 | 0/2 | Not eligible |

Primary totals: **15/18 ordinary tasks; 1/10 accepted first extensions; 0/1 verified second extension**. Swift's two unrun extensions are not counted as failed editing attempts. These small exploratory counts should not be pooled with the follow-ups or navigation pilot below.

An accepted first extension requires a runtime change, a new test file, preserved protected files and allowed scope, passing protected regressions, direct feature checks plus the candidate suite, successful public invocation, and autonomous workflow completion. `documentation_updated` is recorded but is **not** a blocking acceptance criterion in this grader. A model announcing completion, a green development check, or direct behavior alone does not establish full acceptance.

### What failed, and what worked

- **Qwen Q4:** both tasks used all 128 actions. Both candidates passed all direct feature checks and public calls, and preserved the protected regressions. Their own tests still failed. Hashing had an unsuccessful symlink assertion; formatting had test/fixture errors. This is weaker workflow/test-repair performance than the accepted score alone might suggest about coding ability.
- **OxCoder Q6:** hashing was fully accepted after 98 actions and about 426 seconds of model-task time. Its independent first formatting candidate passed 20/20 direct checks and public use, but failed its own suite and exhausted the action allowance. The conditional two-tool candidate is discussed separately below.
- **LFM Q6/JSON:** hashing consumed its 65,536-token allowance with 15 response-format repairs and stopped after 50 actions. Formatting stopped with a compatibility failure; its schema advertised `format_json`, but invocation still returned “Unknown tool.” High raw throughput did not translate into a completed upgrade.
- **Ornith Q6/JSON:** precise editing failed during the ordinary screen. Hashing exhausted its 30-minute allowance, leaving independent grading unavailable; that is not an independent verdict that its implementation was wrong. Formatting passed ordinary examples and public use but failed the exact Unicode boundary checks and its own tests, then stopped with a compatibility failure.
- **Swift IQ3_S:** approximately two generated tokens/second. Exact-file passed; precise-edit and recovery hit their 240-second limits. No extension tests were launched after the basic gate failed. Its coding ability was not established by this run.
- **Nemotron Q4:** passed the three basic tasks and reported completion on both extensions, but neither earned independent verification or added a new test file. No second-extension parent qualified.

## Separate Qwen Q6 and LFM Q8 follow-ups

These profiles were added after observing the initial preflights/results. They are explicitly post hoc and do not replace the primary selections.

| Follow-up | Ordinary tasks | Accepted first extensions | Verified second extensions |
| --- | ---: | ---: | ---: |
| Qwen3.5 9B Q6_K, native, 128K | 3/3 | **1/2** | 0/1 |
| LFM2.5 8B-A1B Q8_0, native | Not run | Not run | Not run |

Qwen Q6's hashing candidate passed all 11 direct checks and public use but left an undefined `Cancelled` name in its own test. It exhausted 128 actions after about 1,602 seconds. Its formatting candidate was fully accepted in **54 actions, 54 requests and about 899 seconds**. The resulting seed then received the second-extension task.

The LFM Q8 native preflight had passed earlier, but both fresh tool-format calls failed with protocol/JSON parsing errors when the quality screen started. The normal gate skipped basic and extension tasks. This shows that a single successful native preflight did not establish reliable native transport; it does not measure LFM Q8's editing ability. The earlier Q6/JSON result remains intact.

## Cumulative growth: direct functionality versus full verification

| Candidate | New feature checks | Retained feature checks | Fresh public calls, both tools | Protected regressions | Activated / final workflow |
| --- | ---: | ---: | --- | --- | --- |
| OxCoder Q6: hashing → formatting | 20/20 | 11/11 | Passed | Two context-test errors | No / not run |
| Qwen Q6: formatting → hashing | 11/11 | 20/20 | Passed | Same two context-test errors | No / not run |

Both candidates therefore show useful two-feature functionality under direct independent checks. Neither is a fully accepted growth chain, and neither has checked final task outputs after activation in this run. OxCoder stopped waiting for a reply/activation; Qwen reported completion. Full verification remained false for both.

The fresh public checks use grader-scripted actions through the unchanged seed loop in independent workers. They verify that the tools can be invoked there; they do not establish that the tested language model independently chose and used both tools after activation.

The protected failures were `test_large_history_keeps_tool_messages_valid` and `test_shortened_read_context_preserves_usable_continuation`. Both fixtures use a small 4,096-token context and assume the latest shortened action result will still fit. Enlarging the advertised tool catalog can invalidate that assumption.

A separate diagnostic ran **only the unchanged trusted seed and those two protected tests**, with inert synthetic tool descriptions. It executed no candidate implementation and changed no files:

| Trusted-seed catalog treatment | Tests passing |
| --- | ---: |
| Original catalog | 2/2 |
| Hashing metadata alone | 2/2 |
| Formatting metadata alone | 2/2 |
| Both longer descriptions, 678 added description characters | **0/2** |
| Both concise descriptions | 2/2 |

This reproduces a catalog-size sensitivity without model-written runtime code. It is a material evaluation limitation, particularly for growth. It does not retrospectively accept either candidate, prove the absence of other defects, or establish successful activation/final use. The original plans, traces and verdicts remain unchanged.

**Recommended next change:** make these retention fixtures account for advertised-schema overhead while preserving their budget and continuation assertions, and separately test irreducible catalog overflow. Then regrade the unchanged saved candidates under a new, explicitly versioned grader and test final use in fresh VMs. Do this before interpreting another growth-screen score as a model capability limit. No fixture or application change was made during this run.

## Precision and speed

Four families received Q4/Q6/Q8 probes; Swift and Nemotron each received one profile: **14 precision preflights** in total. Each fixed-work probe generated 128 tokens from a short prompt and a 7,018-token reference prompt, with cache disabled, fixed seed and temperature zero. Returned probe text was not executed. These measurements are throughput diagnostics, not answer-quality scores.

| Family | Quantization | Short generation tok/s | Long-prompt generation tok/s | Long-prompt processing tok/s | Tool protocol usable in initial preflight |
| --- | --- | ---: | ---: | ---: | --- |
| Qwen3.5 9B | Q4_K_M | 38.48 | 34.42 | 579 | Native |
| Qwen3.5 9B | Q6_K | 9.92 | 14.64 | 407 | Native |
| Qwen3.5 9B | Q8_0 | 8.96 | 7.52 | 246 | Native |
| OxCoder 9B | Q4_K_M | 37.35 | 35.83 | 604 | Native |
| OxCoder 9B | Q6_K | 35.51 | 34.19 | 669 | Native |
| OxCoder 9B | Q8_0 | 9.13 | 8.22 | 246 | Native |
| LFM2.5 8B-A1B | Q4_K_M | 130.37 | 133.60 | 2,494 | JSON diagnostic; native failed |
| LFM2.5 8B-A1B | Q6_K | 110.60 | 117.11 | 2,215 | JSON diagnostic; native failed |
| LFM2.5 8B-A1B | Q8_0 | 72.66 | 77.43 | 2,065 | Native initially; fresh screen failed |
| Ornith 1.5 9B | Q4_K_M | 42.50 | 40.01 | 687 | Native |
| Ornith 1.5 9B | Q6_K | 31.99 | 27.92 | 585 | JSON diagnostic; native failed |
| Ornith 1.5 9B | Q8_0 | 8.04 | 7.72 | 238 | Native |
| Swift 27B | IQ3_S | 2.16 | 2.07 | 79 | Native |
| Nemotron Nano 9B v2 | Q4_K_M | 37.15 | 27.04 | 529 | Native |

The initial selection rule used the sum of the two fixed-work wall times: prefer compatible Q6 at no more than twice Q4; choose Q8 only within twice Q4 and 1.25 times Q6; otherwise use Q4. Qwen Q6 narrowly missed the 2× threshold (39.606 versus 39.028 seconds), and LFM Q8 narrowly missed the Q6-relative threshold (6.941 versus 6.879 seconds). Those near misses motivated separately labelled follow-ups rather than silently changing the rule.

Q8 substantially reduced throughput for the three dense 9B families on this setup. OxCoder Q6 retained most of Q4's generation speed. Qwen Q6 did not, although it later produced an accepted formatting extension. One attempt cannot isolate a precision-quality benefit, and this is not a completed quality test at every precision.

### Memory and timing limits

GPU/RAM snapshots and 30-second samples are saved, but the runtime did not expose layer-count messages to the original parser. Empty `placements` and derived `all_gpu: false` fields mean **unknown placement**, not CPU-only execution. A final load-only reproduction on retained weights is saved separately; it is not proof of historical placement during the timed runs. Exact CPU/GPU layer counts were still unavailable in those logs.

Desktop GPU use changed after the gaming pause. Automatic fitting may therefore differ between earlier probes and later follow-ups. Global RAM/VRAM snapshots include other applications; they are not per-model memory measurements. Tool-format benchmark cache warmth was uncontrolled. Nonstreaming request timing is not time to first token.

## Separate navigation pilot

This was a balanced **six-attempt pilot**: three prescribed first-extension contracts × baseline/outline × one repeat, with counterbalanced arm order. It used the normal Ollama connection, engine version `0.40.4`, Qwen3.5 9B Q4_K_M, 64K context, thinking off and temperature 0.6. The primary screens used Prism at 128K. Their outcomes must not be pooled or treated as a controlled runtime/context comparison.

| Contract | Baseline | Outline variant |
| --- | --- | --- |
| `sha256_file` | Accepted; 17 actions, 158 seconds | Accepted; 54 actions, 468 seconds |
| `csv_preview` | Rejected; 32 actions | Rejected; 114 actions |
| `format_json` | Rejected; 126 actions, 30-minute timeout | Asked for a reply before taking any action |

Each arm accepted **1/3**. **No trial invoked `source_outline`**, including the treatment arm. This measures availability/prompt effects, not the benefit of actually using outlines. It gives no basis to promote that tool into the default seed.

On the one matched accepted contract, baseline used 18 model calls and 3,256 output tokens, versus 55 calls and 13,221 output tokens for outline. Both measurements are complete. With a single matched pair and no outline use, this is a description of this pilot rather than a repeatable treatment effect.

CSV baseline failed the explicit `limit=None` rejection; outline failed the one-extra-row cases and also encountered context-test errors. Formatting baseline passed all 20 direct behavior checks and public use but its own tests called an absent `Workspace.format_json` method and it timed out. The outline arm stopped at a clarification request without editing. These are distinct failure modes.

The timed-out baseline trial has incomplete call/token capture; aggregate baseline token and call-time totals are labelled **partial**, not complete costs. The full paired-study summary preserves completeness separately for each measurement.

## Evidence, interruptions and cleanup

Private evidence root: [overnight study](D:/AI_New/AP/.data/overnight-v020-20261019).

- [Original protocol](D:/AI_New/AP/.data/overnight-v020-20261019/protocol.json), pinned model metadata, launch commands, weight receipts, frozen plans and runner snapshots are retained there.
- [Compact evidence](D:/AI_New/AP/.data/overnight-v020-20261019/compact-evidence.json) joins primary screens, post-hoc follow-ups, measurement coverage, navigation and the context diagnostic. Full provider traces, journals and exported candidate sources remain under each trial directory.
- A portable [results snapshot](D:/AI_New/AP/evaluations/seed-v0.2.0-local-results.json) contains the compact evidence alongside this report; raw traces remain private in `.data`.
- [Context diagnostic](D:/AI_New/AP/.data/overnight-v020-20261019/trusted-metadata-context-diagnostic.json) records the trusted-only reproduction; [navigation results](D:/AI_New/AP/.data/overnight-v020-20261019/navigation-pilot/results.json) contain the separate pilot.
- The user requested a gaming pause. Test drivers and owned model servers stopped, and the interrupted Ornith benchmark was retained as attempt 001. Resume explicitly created attempt 002. It was an interruption retry, not an unreported best-of retry.
- Staged Q6/Q8/Swift downloads were removed after use to protect disk space. Qwen Q6 and LFM Q8 were retained through verified hard links; two existing duplicate model copies were also replaced with hash-verified hard links, preserving their paths and bytes. Receipts and cleanup manifests are retained.
- The final audit checks the original seed fingerprint, unchanged tracked source, stopped study services and disk reserve. Final free space is approximately **127 GB, 12.4% of the SSD**. Model changes were not merged into the application, and no new application commit was made.

The useful next step is a narrow evaluation-fixture correction followed by fresh final-use checks of the saved two-tool candidates. More models, larger contexts or a new extension framework would be less informative until that obstruction is resolved.
