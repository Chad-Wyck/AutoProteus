# Local v0.0.15: faster experiment tooling and Bonsai seed editing

Date: 2026-10-17 (America/Regina). Local working changes on `4edc8ad`. No commit, push or candidate promotion.

## Testing changes

The optional runner provides inference-only benchmarks, quick screens and full first/second-pass queues. Plans freeze source, tasks, tools, settings, trusted files and VM inventory. Completed cells resume without inference; launched unfinished attempts remain interrupted unless explicitly retried as additional attempts. Calibration reuse requires exact identities and appliance integrity. Successful candidate-check reuse is limited to one attempt. Provider phase timings and missing-measurement coverage remain separate from correctness. The normal seed interface, app preferences and isolation policy are unchanged by this revision; prior local v0.0.14 edits remain.

Validation: the full suite passed **214 tests with 16 platform skips (230 total)**, including **24 real VM checks**. Final runner checks after bookkeeping refinements passed **18/18**, including its real VM cache check. Actual completed-queue replay reused calibration and left all provider traces and queue bytes unchanged.

## Bonsai method

The cached official Ternary-Bonsai-2-27B PQ2_0 checkpoint and official PrismML CUDA12.4 build were verified. One GTX 1080 Ti (11 GB), one loopback inference slot, standard production compatible-service adapter, native tools and no call-ID rewriting. All model-written code and graders execute only in disposable network-free Linux VMs on Windows/WHPX.

Two bounded inference preflights tested 64K/Q8 and 128K/Q4 cache. Both passed; the predeclared rule selected 128K/Q4 (52.59 s versus 46.09 s in these single preflights), each using about 10.7 GB total GPU memory at loading. This is adaptive profile selection, not an isolated speed or seed-effect comparison. Sampling: temperature 0.7, top-p 0.8, top-k 20, min-p 0, presence penalty 1.5, repeat penalty 1.0; thinking explicitly disabled. Full tasks retain 4,096 response tokens, 128 actions per active run, 30 minutes and 65,536 generated tokens. Second-pass development and activation share the wall/output allowance. One fresh attempt per first contract; every fully accepted first source receives one fresh second extension preserving and using the earlier capability.

Starter SHA-256: `77b08def273f9a58206ef129161db1452f9c8d2cc8a1dbd25b3ea3f46bd8c566`. Basic tasks: **4/5**.

| First tool | Verified | Fully accepted | Status | Actions / reads | Model-task seconds |
| --- | --- | --- | --- | --- | --- |
| sha256_file | False | False | paused | 86 / 25 | 1800.29 |
| csv_preview | False | False | paused | 115 / 27 | 1800.37 |
| format_json | False | False | error | 20 / 13 | 731.89 |

First-pass accepted: **0/3**. Second extensions verified: **0/0 attempted**. Complete staged growth: **0/0 attempted**.

- `sha256_file`: status`paused`, category`timeout`; independent failed cases: `registered`, `schema`. Allowed scope=True, protected files=True, new focused test files=[].
- `csv_preview`: status`paused`, category`timeout`; independent failed cases: none recorded. Allowed scope=True, protected files=True, new focused test files=[].
- `format_json`: status`error`, category`connection`; independent failed cases: none recorded. Allowed scope=True, protected files=True, new focused test files=[].

No fully accepted first parent existed, so the main queue's automatic second-pass cells were explicitly untested; these are not second-pass failures.

The hashing attempt spent 1780.417 seconds in measured model calls and 20.082649 seconds in independent grading. Provider-reported phase timings identify generation as the main inference cost for this attempt. Its token usage includes an unmeasured cancelled call and remains explicitly partial.

These single attempts do not establish repeatability or a ranking against Qwen 9B. Earlier Bonsai v0.0.12 tests already covered first-pass editing but accepted 0/3 and reached no second pass. The new selected profile changes context/cache precision as well as using the current seed. No result should be attributed solely to the testing infrastructure.

Private evidence: `.data/bonsai-v0.0.15-20261017/`. See the [validation record](seed-v0.0.15-bonsai-validation.json) and [runner guide](model-study.md). The helper stopped its owned model server; no model-authored seed was activated in the normal app.

## Separately labelled second-extension diagnostic

The original 0/3 fully accepted first upgrades and zero automatic second-pass attempts remain unchanged. A separate diagnostic used the exact, unmodified model-written formatting candidate, whose scope, protected files, regressions, independent feature grader and public invocation passed. Its original run lacked focused tests and stopped at the 300-second request timeout while generating a response (about 2,039 tokens, approximately 6.8 tokens/s). It is a behaviour-checked parent, not a fully accepted first upgrade.

One new frozen attempt added hashing while preserving and using formatting. Request timeout was increased to 900 seconds to allow longer responses at the measured speed; the whole task still had 30 minutes, 65,536 generated tokens and 128 actions per active run. The same engine/checkpoint, 128K/Q4 cache, sampling and production adapter were used after restarting the owned service. No operator changed candidate code.

| Diagnostic measure | Result |
| --- | --- |
| New extension verified | True |
| New feature grader including candidate suite | True |
| New focused test files | tests/test_sha256.py |
| Prior capability retained, including combined suite and public check | True |
| Development status | paused |
| Final-use status | not reached |
| Exact final artifacts | None |
| Complete diagnostic workflow | False |

Diagnostic development used 58 actions in 1800.25 seconds. This diagnostic cannot establish an accepted two-generation chain or a causal benefit from the timeout change. All original verdicts, traces and source identities remain preserved. The root seed and trusted files were rechecked unchanged after both live studies.

## Separate fresh-use check

A final fresh task loaded the exact unchanged two-tool seed (`b7ae28263ba1a8a25ccbc9614b7c610f840f301a2494be512673c6f821464d4b`) and asked Bonsai to format a new Unicode JSON file, hash its final bytes, write an audit receipt and finish. This had a separate 240-second / 8,192-generated-token allowance, with the same inference settings and a 900-second per-request limit constrained by that shorter overall deadline. No new capability was requested or added.

The task **passed** in **71.22 seconds**, using 7 actions and 8 model requests. Exact file and receipt checks=True, source unchanged=True, direct use of both capabilities=True.

This is concrete evidence that the model-written cumulative capabilities work and are usable by Bonsai in a fresh task. It does not rescore the paused development workflow, repair the original missing tests, establish repeatability or demonstrate a fully accepted unattended two-generation chain. The model authored both implementations and the second extension's focused tests; the operator edited no candidate. The final owned server was stopped.

## Final bookkeeping validation

After live inference ended, the runner gained an additional root/model identity check after each executed cell, including the final cell. A change during a long attempt now leaves an error record and cannot earn completed-study credit. The final 18 runner checks all passed, including negative controls for both kinds of mid-attempt changes and a real VM cache check. The full 230-test run and completed model trials retain their earlier runner snapshots; the editable seed fingerprint is unchanged. The earlier 16-check pretrial runner result is retained separately in the validation record.

No successful response in the second-extension diagnostic exceeded the original 300-second request limit (maximum 289.508 seconds). The changed timeout was a prospective allowance; these data do not demonstrate a benefit from it.
