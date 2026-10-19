# Local model screening on frozen AutoProteus v0.0.13

Date: 2026-10-16 (America/Regina). Exploratory first- and second-pass screening on the GTX 1080 Ti (11 GB). The default seed tools, instructions and loop were unchanged during testing. All generated code, candidate tests and independent graders executed only in disposable network-free VMs. No candidate was repaired by the operator or promoted.

Frozen starter: `f7e7b5bfb5af6c8da22c868804eec0fba42e94ffc57571a25ac7c8e467cc7bb6` at commit `4edc8ad`. This round uses the production ModelClient through managed Ollama with a protected research token-budget wrapper; no custom call-ID rewriting. Five cached checkpoints were checksum-verified. New real-VM positive, absent-tool and boundary-bypass calibration passed before inference.

| Profile | Basic tasks | First-pass verified | First-pass fully accepted | Second-pass verified / attempted | Complete staged growth |
| --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.5 9B | 5/5 | 2/3 | 2/3 | 2/2 | 1/2 |
| Qwen3.5 4B | 5/5 | 1/3 | 0/3 | 0/0 | 0/0 |
| Qwopus3.5 9B | 5/5 | 1/3 | 1/3 | 0/1 | 0/1 |
| Ministral 3 8B | 5/5 | 0/3 | 0/3 | 0/0 | 0/0 |
| FineEnvs LFM2.5 2.6B | 5/5 | 0/3 | 0/3 | 0/0 | 0/0 |

## Method and limits

Each profile received the same five basic tasks (gate: at least 4/5), then one fresh attempt each at hashing, CSV preview and JSON formatting. Every fully accepted first candidate received a fresh second-extension task on its exact source: use the earlier tool, add the remaining audit capability, preserve earlier behavior/tests, request activation, then produce and inspect an audit using both tools. Second-pass development uses a new task, rather than preserving the entire first-pass development transcript; activation uses the existing concise handoff. There are no hidden candidate repairs or reruns.

Upgrade attempts allow 30 minutes, 65,536 cumulative generated tokens, 4,096 response tokens and 128 actions. The original 300-second request timeout, command limits and VM watchdog remain. Development and activation in a second pass share one generated-token allowance; activation receives only remaining wall time, including elapsed independent grading. Basic tasks and separate fresh-use diagnostics allow 240 seconds and 8,192 generated tokens. Missing output usage is conservatively charged for enforcement and remains labelled unmeasured in cost records.

The Qwen-family profiles use 128K context, temperature 0.6, top-p 0.8, top-k 20 and thinking off. Ministral uses 64K, temperature 0.05, top-p 1, top-k 0 and template-default thinking. FineEnvs uses 64K, temperature 0.8, top-p 1, top-k 0 and its preserved template default; this differs from the previous explicit 1,024-thinking-token sub-budget. All use native tools, min-p 0, repeat penalty 1 and presence penalty 0. Weights are Q4_K_M except FineEnvs Q8_0. The research server enables flash attention and q8_0 K/V cache without editing app preferences.

Ministral partly offloaded to CPU at 64K; saved placement records quantify it. Runtime, context, cache and sampling differ from older screens, so differences cannot be attributed to v0.0.13. The default seed behavior did not change between these runs and the preceding v0.0.13 comparison. Single attempts, different models/settings and familiar text-tool contracts do not establish a model ranking, repeatability or broad autonomous self-improvement.

## First-pass details

| Profile | Task | Verified / accepted | Status / category | Actions / reads | Model-task seconds | Reported output tokens / usage complete |
| --- | --- | --- | --- | ---: | ---: | ---: |
| Qwen3.5 9B | sha256_file | True / True | completed / none | 22 / 5 | 194.69 | 5940 / True |
| Qwen3.5 9B | csv_preview | False / False | completed / none | 28 / 6 | 220.36 | 5885 / True |
| Qwen3.5 9B | format_json | True / True | completed / none | 40 / 6 | 339.85 | 9027 / True |
| Qwen3.5 4B | sha256_file | True / False | error / connection | 126 / 111 | 442.81 | 12753 / False |
| Qwen3.5 4B | csv_preview | False / False | paused / none | 128 / 124 | 262.51 | 8108 / True |
| Qwen3.5 4B | format_json | False / False | paused / none | 128 / 106 | 469.64 | 14159 / True |
| Qwopus3.5 9B | sha256_file | True / True | completed / none | 33 / 14 | 205.71 | 6712 / True |
| Qwopus3.5 9B | csv_preview | False / False | completed / none | 128 / 99 | 418.73 | 12014 / True |
| Qwopus3.5 9B | format_json | False / False | error / connection | 10 / 7 | 144.74 | 1010 / False |
| Ministral 3 8B | sha256_file | False / False | error / connection | 79 / 40 | 921.29 | 7201 / False |
| Ministral 3 8B | csv_preview | False / False | error / timeout | 36 / 21 | 507.41 | 2929 / False |
| Ministral 3 8B | format_json | False / False | completed / none | 45 / 15 | 384.62 | 4843 / True |
| FineEnvs LFM2.5 2.6B | sha256_file | False / False | error / budget | 23 / 11 | 950.35 | 65536 / True |
| FineEnvs LFM2.5 2.6B | csv_preview | False / False | completed / none | 19 / 8 | 508.19 | 33814 / True |
| FineEnvs LFM2.5 2.6B | format_json | False / False | error / connection | 4 / 4 | 49.04 | 1071 / False |

Verification requires a runtime edit, new focused tests, protected file preservation, allowed scope, regressions, independent behavior checks and public invocation. Full acceptance also requires autonomous completion within task limits. A reported connection/request failure is not proof that a model cannot implement the feature. Original requests, incomplete responses, conservative enforcement charges and candidate artifacts are retained.

## Failure audit

- Qwen 9B CSV completed its own checks but failed the independent default-limit case. Its hashing and formatting upgrades passed all checks.
- Qwen 4B hashing passed independent verification, then kept reading. The final stream contained 107 read_file call entries, exceeding the existing 32-call guard. The app labelled it connection; an earlier live update incorrectly attributed it to the context guard.
- FineEnvs formatting produced an explicit server error for malformed edit_file arguments (an unescaped newline). That was also labelled connection. Its hashing attempt exhausted exactly 65,536 generated tokens after 23 actions, with no verified upgrade.
- Qwopus formatting has an unresolved provider failure with no usable final response frames. Ministral hashing/CSV ended at roughly 300-second request failures; its partial CPU placement affected throughput. These must not be interpreted as 30-minute task stops.
- The generic connection category conflates native protocol/guard failures with transport problems. Preserving redacted error details and routing repairable protocol errors through the existing bounded retry path is a candidate follow-up; it was not changed during this study.

## Second-pass details

### Qwen3.5 9B: sha256_file → format_json

Verified extension: True; earlier verifier including the combined suite / public invocation: True / True; stage order: True. Development status: waiting; final status: waiting. Functional growth: False; direct-route success: False.

Separate fresh-task diagnostic on the exact unrepaired combined seed: functional reuse True, direct-route use True, source unchanged True. This does not rescore the failed staged workflow.

### Qwen3.5 9B: format_json → sha256_file

Verified extension: True; earlier verifier including the combined suite / public invocation: True / True; stage order: True. Development status: waiting; final status: completed. Functional growth: True; direct-route success: True.

### Qwopus3.5 9B: sha256_file → format_json

Verified extension: False; earlier verifier including the combined suite / public invocation: False / True; stage order: True. Development status: completed; final status: not activated. Functional growth: False; direct-route success: False.

All earlier hashing behavior cases passed. The retained verifier failed because the new formatting test file had a syntax error and the verifier includes the whole combined suite. This does not show that hashing itself regressed.

## Evidence

The serial screening/calibration window was 128.4 minutes; preparation and final auditing are additional. No tracked seed/controller source changed, no candidate was promoted, and model servers were unloaded/closed after the batch. Experimental model aliases remain cached. Private frozen inputs, model receipts/manifests, runtime identities, provider traces, journals, candidate source/diffs, independent grades and GPU samples are in `.data/model-round-v0.0.13-20261016/`. The [compact results](local-model-round-v0.0.13-2026-10-16.json) retain cost completeness and separate staged outcomes from fresh-use diagnostics.
