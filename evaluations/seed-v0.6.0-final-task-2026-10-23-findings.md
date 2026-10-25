# Qwen 9B final-task replay: v0.4.0 and v0.6.0 runtimes

Completed 2026-10-23 against commit `532e36bcc9fcf7a1eb2b69015eef2558c965c13f`.

**Both runtimes produced three independently verified hashing extensions. Neither completed a correct final workflow.** All five activated candidates explicitly called `csv_preview` with `limit: 2` and saved two rows when the final audit required the default five. The other v0.6.0 attempt exhausted its shared action allowance on source reading before activation.

This establishes useful directed extension on these supplied parents. It provides no measured improvement in final-task correctness from v0.6.0 and no evidence of an autonomous two-feature growth chain: the initial CSV capability was supplied from a human reference implementation.

| Result | v0.4.0 runtime control | v0.6.0 runtime candidate |
| --- | ---: | ---: |
| Scored attempts | 3 | 3 |
| Independently verified extensions | 3/3 | 3/3 |
| Protected regressions, new-feature and fresh-worker public checks passed | 3/3 | 3/3 |
| Existing CSV functional and public checks retained | 3/3 | 3/3 |
| Activated candidates | 3/3 | 2/3 |
| Both tools used directly after activation | 3/3 | 2/3 |
| Correct final artifacts | 0/3 | 0/3 |
| Complete, independently checked workflows | 0/3 | 0/3 |
| Actual launches, including the infrastructure interruption | 3 | 4 |

## Fixed setup

- Model: `Qwen_Qwen3.5-9B-Q6_K.gguf`; no LoRA. SHA-256 `073a9275e65d9c8cd2819cf5f77b99fbaa6e87ba591da6bbaa86ec073a64bfef`.
- GTX 1080 Ti; Windows WHPX disposable, network-free VMs for all candidate execution and grading.
- Pinned PrismML `prism-b10777-e3de715` CUDA 12.4 engine; executable SHA-256 `e95c81a7f99b05b4e9c67eba3f6856d777987ff813e6c1f14069c6c599e029d7`.
- Standard production model connection, native tools, no custom tool-call ID rewrite.
- 131,072 context tokens, 4,096 response tokens, temperature 0.6, thinking off; remaining sampling and runtime flags recorded in the frozen profile.
- Per attempt: 128 actions and 65,536 generated tokens shared across development and activated use; one 1,800-second deadline covers development, independent grading, retention and final use.
- Order: old/current, current/old, old/current. Slot contents erased before each attempt. Three matched task fixtures, unchanged hidden graders. No operator candidate repairs.
- Four-hour batch bound retained from the original start. All six scored cells completed within it.

The two experimental parents share identical CSV implementation, declarations, CSV tests and a portable protected-test overlay. Three budgeting assignments in the overlay accommodate the old embedded JSON catalog and the new host-supplied format instructions. The registration assertion checks actual catalog behavior without requiring v0.4.0 to have v0.6.0's prompt architecture. All 50 protected cases remain; both parents passed them in a VM before model trials. These are controlled runtime comparisons with a supplied CSV parent, rather than byte-for-byte shipping releases.

| Identity | SHA-256 |
| --- | --- |
| v0.4.0 runtime parent | `2d3637b1f0877b32e654e61e61edb275a25cec56363d5d1e1d3589e60d0f4f2b` |
| v0.6.0 runtime parent | `b8b3369f40aa32e737c275310905361f56ebc305ac1960c59b591f8010a97a75` |
| Current application seed, before and after the study | `63d6e3a74fe5b398af2b1d4aaacfeb3f9dfd0fe023f8104f341eabd3d128a76a` |

Fingerprint-matching prior source-validation receipts were reused. Both parent suites and the protected grader calibration, including semantic faulty implementations and negative controls, passed before inference. After resumption, calibration was reused only after checking the same source, graders, runtime, fixtures and profile identities.

## Qualification and individual outcomes

The revised production qualification passed on its first attempt in eight calls both before the initial batch and after the infrastructure restart. Each pass completed all three diagnostic rounds, the intended rejected-call recovery, exact receipt confirmation and explicit finishing, with zero format repairs. This qualifies the connection for the bounded diagnostic; it does not establish seed-editing ability.

| Repeat | Runtime | Verified code | Activated | Final saved rows | Calls | Shared actions used | Trial minutes |
| --- | --- | --- | --- | --- | ---: | ---: | ---: |
| 1 | v0.4.0 | Yes | Yes | 2; requires 5 | 30 | 28 | 10.0 |
| 1 | v0.6.0, replacement | Yes | Yes | 2; requires 5 | 71 | 70 | 29.8 |
| 2 | v0.6.0 | Yes | No | Not activated; development audit had 2 | 129 | 128 | 20.9 |
| 2 | v0.4.0 | Yes | Yes | 2; requires 5 | 30 | 29 | 6.6 |
| 3 | v0.4.0 | Yes | Yes | 2; requires 5 | 32 | 30 | 6.2 |
| 3 | v0.6.0 | Yes | Yes | 2; requires 5 | 40 | 39 | 7.0 |

Each activated candidate retained its source unchanged during final use, preserved the original input bytes, called both tools through native calls, explicitly finished, and saved correct path, byte count, SHA-256 and truncation fields. The rows field alone failed the final artifact comparison. The five activated outcomes therefore fail functional growth as well as strict completed-workflow success; routing was successful.

The second v0.6.0 candidate finished development in `waiting` status to request activation, as the task requested, but had no shared actions left for activated use. Its code, regression, public and retention checks passed. The raw `review.accepted` field is false because that field additionally requires a completed development status. Accordingly, raw accepted counts are 3/3 versus 2/3; they must not be substituted for independent code verification in this staged task. The original fields are preserved in the results.

None of the six scored attempts exhausted the token allowance or reached the wall deadline. One exhausted the action allowance. A verified extension here can include the model's own repairs within its attempt; it does not mean its first written implementation was correct.

## Two observed failure patterns

The frozen user task first requests a preview with `limit: 2`, then later requests audit rows from the **default preview** after activation. The latter resolves to five rows through the existing tool contract. Every activated continuation nevertheless supplied `limit: 2` again. The final instruction says “default preview” rather than spelling out the number five in the task text. The observed mistake is carrying an earlier explicit argument into a later step with a different requirement. It is not evidence that hashing, CSV parsing or direct native dispatch failed.

In the second current-runtime attempt, the model made 72 reads after its last passing development check, with no further runtime edits. Its 73 section reads included requests such as `start=80, length=30`, followed by `start=85, length=30`, eventually reaching `start=435, length=30`. These request **characters**, so they expose tiny overlapping fragments. Confusion between line numbers and character offsets is a plausible interpretation, not an established internal cause. The saved arguments and navigation metrics provide a specific navigation case to reproduce.

All six scored runs reported zero format repairs. There were ordinary tool/command failures and self-repairs. This batch's primary completion failures do not establish native function-call serialization as the bottleneck.

## Cost and the infrastructure replacement

The original first v0.6.0 launch was interrupted by the host disk-reserve guard after 321.561 seconds and before an independent verdict. It is recorded as an infrastructure interruption, with one cancelled request and incomplete token usage, rather than a model rejection.

The user explicitly authorized ignoring the disk reserve. Before resuming, the original frozen inputs and study plan were archived, the resource-policy amendment was recorded, and one replacement was authorized for this cell alone. The completed control was preserved. Source, sampling, task budgets and graders stayed fixed. The original four-hour batch deadline stayed in force. There were **seven actual trial launches for six scored attempts**; the interrupted launch remains in total cost accounting.

| Scored-attempt totals | v0.4.0 | v0.6.0 |
| --- | ---: | ---: |
| Calls | 92 | 240 |
| Reported input tokens | 725,778 | 4,632,763 |
| Reported output tokens | 15,072 | 29,265 |
| Total trial seconds, including grading/use | 1,370.771 | 3,461.658 |

Usage and trace measurements are complete for all 332 scored-attempt calls. The current arm used more interactions and tokens in this sample, especially in the section-reading sequence. The three repeats and the server restart limit causal interpretation; this comparison does not isolate a particular prompt line, loop change or inference optimization. Runtime flags were fixed with automatic GPU offloading, rather than a recorded per-layer placement guarantee. Both launches and runtime logs are preserved.

Across **all seven launches**, 352 calls were recorded. Known input usage is **5,537,640 tokens** and known output usage **48,641 tokens**, measured on **351/352** calls. These are partial sums, not complete totals. Call timing is complete: 4,814.670 seconds. Summed trial wall time is 5,153.990 seconds. Qualification is separate: 16 additional calls, 26,602 input tokens, 642 output tokens and 193.892 seconds of measured call time. There are no matched fully successful workflow pairs on which to compare success-conditioned efficiency.

The whole interval from initial launch to final cleanup was approximately 108 minutes, including the interruption, restart, qualification and calibration. Test processes released the GPU and VMs at the end. No application source was changed or model-written candidate adopted into the checkout.

## Recommended follow-up

Keep this result as evidence that Qwen can implement and retain the requested capability under independent checks, while final-task completion remains unreliable. The v0.4.0 control did not solve the final-task error, so this batch supplies no workflow-success reason for a wholesale rollback. The increased interaction cost on v0.6.0 warrants a narrow comparison.

1. Test one focused final-use handoff that explicitly distinguishes the earlier two-row preview from the final default five-row audit. Keep the original grader and compare it with the current handoff; do not relax correctness.
2. Separately test a navigation treatment against the saved tiny-slice case. Measure calls, reading and submission after passing checks, while preserving the independent verification boundary. A line-oriented view is a candidate treatment; the inferred line/character confusion still needs confirmation.
3. Qualify any promising treatment on a fresh capability and another local model before changing defaults. Three repeats of this familiar CSV/hash workflow cannot establish general self-improvement.

These are proposed experiments. No additional model runs or seed changes were made after the fixed batch.

## Evidence and reproduction

- [Frozen study plan](D:/AI_New/AP/evaluations/seed-v0.6.0-final-task-plan.md)
- [Machine-readable results, including all actual launches and original verdicts](D:/AI_New/AP/evaluations/seed-v0.6.0-final-task-2026-10-23-results.json)
- [Frozen protocol and source inventory](D:/AI_New/AP/.data/final-task-v060-20261023/protocol.json)
- [Model profile, runtime flags and asset checksums](D:/AI_New/AP/.data/final-task-v060-20261023/profile.json)
- [Original execution manifest](D:/AI_New/AP/.data/final-task-v060-20261023/execution-01/execution-manifest.json)
- [Original archived frozen inputs](D:/AI_New/AP/.data/final-task-v060-20261023/execution-01/input-snapshots)
- [Resumed execution manifest](D:/AI_New/AP/.data/final-task-v060-20261023/execution-02/execution-manifest.json)
- [Explicit resumption ledger](D:/AI_New/AP/.data/final-task-v060-20261023/resume-source.json)
- [Final queue, retaining the interrupted attempt](D:/AI_New/AP/.data/final-task-v060-20261023/execution-02/queue.json)
- [Root integrity and completed-journal analysis](D:/AI_New/AP/.data/final-task-v060-20261023/analysis-evidence.json)
- [Final cleanup receipt](D:/AI_New/AP/.data/final-task-v060-20261023/execution-02/stopped.json)
- [Host check confirming no model/VM processes or private model listener remain](D:/AI_New/AP/.data/final-task-v060-20261023/final-host-check.json)

The manifests, saved launchers, source packages, exact task fixtures, candidate snapshots and provider traces are the reproduction inputs. The saved launchers intentionally refuse to overwrite their execution directories; a new study must use fresh output locations, freeze its own inputs and rerun the gates. Do not execute archived candidate code on the host. This report and the new results remain local and uncommitted.
