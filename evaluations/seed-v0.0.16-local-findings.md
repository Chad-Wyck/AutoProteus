# AutoProteus v0.0.16: six-model first- and second-pass screen

OxCoder 9B Q6 produced one complete, independently checked growth chain on the frozen starter: it added hashing, extended that accepted seed with JSON formatting, activated the edited seed, and completed the audit using both tools through native calls. Qwen3.5 9B and OxCoder each achieved two accepted first upgrades and two verified second extensions. Repeatable ordered completion remains unestablished.

These are exploratory results from **one attempt per contract**, not three repeats of one task or a model ranking. Runtime, quantization and some sampling settings differ between profiles. The default application settings and starter were not changed during this study.

## Results

| Local profile | Basic tasks | Fully accepted first upgrades | Verified second extensions | Correct use after activation |
|---|---:|---:|---:|---:|
| OxCoder 9B Q6_K | 5/5 | 2/3 | 2/2 | 1/2 |
| Qwen3.5 9B Q4_K_M | 5/5 | 2/3 | 2/2 | 0/2 |
| Qwen3.5 4B Q4_K_M | 5/5 | 0/3 | Untested | Untested |
| Qwable 4B Q4_K_M | 4/5 | 0/3 | Untested | Untested |
| Qwopus3.5 9B Coder Q4_K_M | 5/5 | 0/3 | Untested | Untested |
| Ternary Bonsai 2 27B PQ2_0 | 4/5 | 0/3 | Untested | Untested |

Second-pass trials started only from fully accepted first parents. An absent accepted parent is an untested second pass, not a second-pass failure. Both successful 9B profiles accepted `sha256_file` and `format_json`; neither accepted `csv_preview` in this screen.

Across the 18 first attempts, nine candidates passed every independent feature case, while four met the complete acceptance criteria. All four second extensions passed code verification. One produced correct output after activation; the other three had correct saved outputs before activation. Those artifact diagnostics remain separate from the ordered-use score.

The acceptance columns combine several requirements. First upgrades need an actual source change, allowed files, unchanged protected tests, focused model-written tests that pass, independent feature and public-interface checks, and completion within the allowance. Second extensions must additionally preserve the earlier tool. Correct final use requires preserving the real input during development, activating the checked candidate, and completing the prescribed audit with both capabilities. Functional use and native-call routing are scored separately; the one successful OxCoder chain passed both.

## Important distinctions behind the scores

**Qwen's second-pass code worked, but its phase ordering failed.** Both extensions passed independent code checks and retained the earlier capability. A separate read-only inspection of saved bytes confirmed correct formatted files and audit receipts in both attempts. The model had performed that work before activation, violating the instruction to keep `inventory.json` unchanged during development. The stage-order guard therefore prevented activation. Missing a `needs_input` request alone was not the blocking condition: the runner can proceed from a completed or waiting development session when the other guards pass.

OxCoder followed the required order in its hashing-parent chain. Its formatter-parent chain also produced a verified extension and correct saved outputs, but changed the real input early. That second chain failed the same stage-order condition as Qwen. These preactivation artifact inspections are **post-hoc diagnostics**; they do not replace or improve the frozen workflow scores. Qwen's trace records development invocations of both capabilities. OxCoder's successful activated chain records direct native calls to both. Its other chain has correct saved artifacts without equivalent recognized invocation-route evidence.

**Qwable demonstrated a working feature despite its zero accepted score.** Its hashing candidate passed independent behavior checks, public invocation and its test suite, but left an extra `test.bin` in the harness. The allowed-file check rejected the upgrade. The operator did not remove that file, repair the candidate or promote it to a second-pass parent. Its CSV attempt made no runtime change before its allowance ended; its formatter registered a tool without completing a working dispatcher implementation.

**Some other rejected candidates also passed the feature cases.** Qwen 4B's hashing and CSV implementations passed the independent contract cases but retained failing model-written tests. Bonsai's formatter passed all 20 independent feature cases and the protected regressions, but its own test suite failed and development reached the 30-minute deadline. For example, it classified valid `[1, 2]` as invalid JSON and constructed an alleged 100,000-character boundary fixture whose expected length was 99,999. Its hashing and CSV attempts made no source change before exhausting their action allowances.

Qwopus's hashing implementation failed oversized-file rejection; its CSV candidate failed multiple behavior cases. Its formatter lacked the `json` import and repeatedly retried a test command containing an unclosed brace. The saved request trace confirms that the syntax-error feedback reached the model. These results qualify the tested nonthinking profile; they do not establish how another thinking or sampling configuration would perform.

## Reproduced context-accounting defect

Two CSV attempts stopped on a host context-estimate error. Offline replay of the saved messages reproduced the same rejection without model inference or candidate execution:

| Profile | Neutral history bytes | Native wire bytes | Allowed bytes | Excess after translation |
|---|---:|---:|---:|---:|
| Qwen3.5 4B | 248,011 | 254,066 | 253,696 | 370 |
| OxCoder 9B | 250,768 | 257,834 | 253,696 | 4,138 |

The editable seed budgets its neutral messages. The protected adapter translates them into native tool-call/result messages, then applies the same byte-based limit to that different representation. Translation overhead can therefore reject a request the seed considered within budget. This is a harness accounting defect, not a measured exhaustion of the model's actual 128K tokenizer context.

Both affected CSV candidates passed the independent feature cases but still had failing model-written tests. Correcting the accounting would remove an infrastructure blocker; it would not establish that either attempt would eventually finish successfully. Their original outcomes remain unchanged. The frozen starter was not patched during the screen.

The next narrow correction should align seed budgeting with the adapter representation, preserving complete user instructions and tool-call/result pairing. A regression should replay these long histories through the standard adapter and verify that budgeting either prepares an admissible request or returns a consistent error before inference.

## Efficiency and navigation

For one matched successful contract, including all calls inside each successful attempt:

| Accepted hashing attempt | Tool actions | Model calls | Reported output tokens | Total trial seconds |
|---|---:|---:|---:|---:|
| Qwen3.5 9B Q4_K_M | 97 | 98 | 18,947 | 818.101 |
| OxCoder 9B Q6_K | 39 | 40 | 11,177 | 439.753 |

Both rows have complete call and usage measurements. This is useful profile-level efficiency evidence, but one matched success with different weight precision cannot establish a causal benefit from fine-tuning or a general model ranking.

Saved actions show a concrete navigation problem: Qwopus repeatedly paged through growing source files in 100-character sections despite the tool's 1,000-character default and progress hints. Its hashing attempt used 112 section reads. Bonsai instead became stuck repeatedly searching for a not-yet-created tool or checking its absent registry entry. These are different failure modes. Existing opt-in navigation, edit-feedback and phase-focused experiments remain appropriate comparisons; no new extension framework or default prompt treatment was added here.

## Runtime and quantization

All inference ran locally on the GTX 1080 Ti through a loopback OpenAI-compatible endpoint and the standard production `ModelClient`. The configuration value `provider: hosted` selects the wire adapter; it does not mean cloud inference. No custom tool-call-ID rewriting was used. All candidate code, model-written tests and independent probes executed inside disposable network-free VMs. Candidate bytes were only read, hashed, diffed or parsed as data on the host.

The shared engine was the verified PrismML `prism-b10777-e3de715` CUDA 12.4 build. Profiles used 131,072 configured context tokens, 4,096 response tokens, native calls, thinking off, and 128 tool actions per active run. First development had 1,800 seconds and a 65,536 generated-token allowance. Second development, grading and activation/final use shared the wall and generated-token allowance. Failed and cut-off responses remained charged. Ordinary tasks used 240 seconds and 8,192 generated tokens. Requests had a 900-second timeout; commands had 60 seconds.

Qwen-derived profiles used temperature 0.6, top-p 0.8, top-k 20, min-p 0, repeat penalty 1, presence penalty 0, and Q8 KV cache. Bonsai used temperature 0.7, presence penalty 1.5 and Q4 KV cache. These experimental profiles differ from normal app defaults and from earlier Ollama-backed studies. This screen does not qualify the default first-launch experience or isolate a seed-version effect.

OxCoder precision was selected before its upgrade outcomes using a declared rule: prefer the highest precision with passing native benchmarks, exact requested context, all layers on GPU, and at most twice the Q4 benchmark time.

| OxCoder precision | Explicit GPU placement | Two-call benchmark seconds | Qualified |
|---|---:|---:|---|
| Q4_K_M | 33/33 layers | 11.614 | Yes |
| Q5_K_M | 33/33 layers | 12.235 | Yes |
| Q6_K | 33/33 layers | 12.735 | Yes; selected |

The first three preflights lacked layer-placement lines because default logging omitted them. Those observations and their inference costs remain saved. All three were repeated with explicit logging before any OxCoder upgrade trial. The selected full runtime was checked again for all-GPU placement. Preflight prompts were short and moderately sized; loading 128K capacity does not qualify reasoning or speed on a full 128K prompt.

The new public downloads were pinned to Hugging Face revisions and checked against published LFS sizes and SHA-256 values. Qwable used the Q4_K_M file available in its pinned release. All three OxCoder quantizations remain cached for later comparisons.

## Evidence, interruption and next work

Frozen starter SHA-256: `e7bb33ec062bd0e3d90b74434000200438aff7a5740f2e92d29edba28baf78a0`.

A user-requested pause interrupted Qwen's first second-pass attempt. Its incomplete attempt was retained; resuming launched a separately recorded attempt from the same accepted parent. Completed tasks were reused without rerunning inference. No model candidate was edited, repaired or promoted by the operator. The initial aggregate, which recorded the missing-placement measurement, was preserved before a consolidated six-model aggregate was written.

There are **65 launched attempts**: 30 basic tasks, 18 first upgrades, four completed second extensions, one user-interrupted second attempt, and 12 inference-only benchmark/preflight attempts. Token and call-time coverage is complete for 63 attempts; the interrupted attempt and timed-out Bonsai development make overall totals partial. Known sums are 57,628,632 input tokens, 315,636 output tokens and 15,110.903 model-call seconds. Input-token sums include repeatedly presented/cached history and are not uncached processing totals or monetary cost. No partial sum is used to rank models as cheaper.

All six frozen plans were checked again after completion. No trial remained running or unresolved. The inference server and test VM stopped; the final GPU check reported 1,176 MiB used and 0% utilization. Application source retained the frozen fingerprint.

The useful next steps are the accounting correction, repeated qualification of the OxCoder profile alongside Qwen, and one controlled navigation or phase-order comparison on unseen extensions. The present results support useful small-model self-extension, while leaving repeatability, broader generalization and deeper cumulative growth open.

- [Machine-readable results](D:/AI_New/AP/evaluations/local-model-round-v0.0.16-2026-10-18.json)
- [Consolidated local evidence](D:/AI_New/AP/.data/model-round-v0.0.16-20261018/evidence-summary.json)
- [Verified OxCoder two-tool candidate review patch](D:/AI_New/AP/.data/model-round-v0.0.16-20261018/accepted-oxcoder-two-tool.patch)
- [Candidate fingerprint and provenance](D:/AI_New/AP/.data/model-round-v0.0.16-20261018/accepted-oxcoder-two-tool.json)
