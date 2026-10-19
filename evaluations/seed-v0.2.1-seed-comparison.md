# v0.2.1: corrected context fixtures and matched seed comparison

19 October 2026, America/Regina. Local changes and experiments; no commit or push.

**This batch does not justify reverting the editable seed.** OxCoder Q6 accepted all three first hashing upgrades with each layout. The current layout passed direct second-feature checks in all three continuations; the older layout passed two. Neither completed the entire staged workflow. The older layout earned one fully verified second extension, whereas the current layout earned none under the unchanged scope and new-test requirements. These are different outcomes and should remain separate.

The earlier saved OxCoder and Qwen two-tool candidates now pass corrected grading, and both models successfully reused their own capabilities in fresh tasks. Their original failed growth verdicts remain unchanged.

## Fixture correction

Four protected history tests previously assumed that a fixed 4,096-token window would leave enough space after tool instructions to retain their target observation. A growing catalog can invalidate that assumption without changing the context algorithm.

The fixtures now measure their fixed prompt/catalog envelope and supply 1,800 bytes of observation headroom under the existing conservative estimate. They still require valid shortening/omission, usable continuation, preserved original instructions and an input within the resulting bound. The correction changes test capacity, not normal inference settings or context policy.

New controls establish that:

- All four fixtures pass with eight additional long Unicode tool descriptions.
- A deliberately unbounded message implementation fails all four fixtures.
- An irreducible catalog still raises a context error while preserving human messages.

The same corrected protected test bytes were used in both comparison arms. Version identifiers advance to 0.2.1; no model-facing runtime behavior or tool was added for this correction.

Ordinary validation: **232 passed, 45 skipped; 277 total**. The first sandboxed run could not reach temporary local HTTP servers. Its output is retained; the repeat with loopback access passed without intervening code changes. Both starters also passed independent real-VM grader calibration and protected regressions before model-driven comparison.

## Saved-candidate regrading and fresh use

The original candidate exports were preserved. Separate grading copies overlay only the corrected protected fixtures. Model-written runtime files and focused tests retain their original combined hash. This is a new fixture-version assessment, not a rewritten original result or an operator repair of model code.

| Saved candidate / model | Corrected regressions, both feature suites and public checks | Fresh task | Actions | Model-task seconds | Direct calls to both tools |
| --- | --- | --- | ---: | ---: | --- |
| OxCoder 9B Q6_K | Passed | Passed | 6 | 21.11 | Yes |
| Qwen3.5 9B Q6_K | Passed | Passed | 7 | 47.36 | Yes |

Each fresh task loaded the checked saved seed in a new VM, formatted a different Unicode JSON input, hashed its final bytes, wrote an audit receipt, inspected the outputs and explicitly completed. Both output files matched independent expectations; the seed source remained unchanged during use. These are **fresh capability-reuse successes**, not retroactive completion of the original two-generation workflows.

## Matched OxCoder study

Three hashing → formatting chains per arm, with counterbalanced order: old/current, current/old, old/current. Every chain starts with a fresh starter; a second extension starts only from its own fully accepted hashing parent. There are no hidden retries or operator candidate repairs.

The two arms are:

- **Old:** the exact saved v0.0.16 starter, with the shared corrected protected fixtures.
- **Current:** v0.2.0's layout and instructions, labelled v0.2.1 after the fixture correction.

Both use the same cached, checksum-verified OxCoder 9B **Q6_K**, standard production compatible-service adapter, verified PrismML `prism-b10777-e3de715` CUDA 12.4 runtime and one shared model-server load for the matched chains. No call-ID rewriting. Context 131,072, Q8 KV cache, flash attention, 4,096 response tokens, thinking off, temperature 0.6, top-p 0.8, top-k 20, min-p 0, repeat penalty 1, presence penalty 0. Exact launch commands are retained.

Each development stage retains the existing 128-action active-run allowance. First upgrades have 1,800 seconds and 65,536 generated tokens. Second development, independent grading, retention checks, activation and final use share one 1,800-second/65,536-token allowance. Activation retains the existing runner's fresh active-run action allowance identically in both arms. Commands are limited to 60 seconds and model requests to 900 seconds, within the shared watchdog. There were no budget increases during a trial.

The shared ordinary gate used exact-file creation, nested-directory creation and precise editing; both arms passed 3/3. Only hashing was tested as the first upgrade, and only formatting as the second. This batch does not demonstrate 3/3 success across three different capabilities.

| Measure | Old layout | Current layout |
| --- | ---: | ---: |
| Basic tasks | 3/3 | 3/3 |
| Fully accepted first hashing upgrades | **3/3** | **3/3** |
| New second-feature direct checks plus public invocation | **2/3** | **3/3** |
| Fully verified second extension, including new tests and allowed scope | **1/3** | **0/3** |
| Complete growth chain | **0/3** | **0/3** |
| Median first-upgrade wall time, including grading | 397.288 s | 395.640 s |
| Median first-upgrade actions | 53 | 52 |

The first-upgrade timings and output-token measurements are complete for all six attempts. Similar medians in this small batch do not establish a performance difference. No deterministic generation seed or repeated runtime crossover was used; cache warmth and desktop load were not controlled experimentally.

### What blocked the second extensions

| Arm / repeat | New feature cases | Candidate suite / protected regressions | Main blocking condition |
| --- | ---: | --- | --- |
| Old 1 | 20/20 | Passed / passed | Verified and activated; correct final files and direct use of both tools, but continued until the deadline without finishing |
| Old 2 | 20/20 | Passed / passed | Left `test_sample.json` inside the editable seed, violating allowed scope |
| Old 3 | 12/20 | Passed / passed | Ordinary formatting and public-use cases failed despite passing its own suite |
| Current 1 | 20/20 | Passed / passed | Added no new focused test file for the second capability |
| Current 2 | 20/20 | Passed / passed | Left `arguments.json` and `test_input.json` inside the editable seed |
| Current 3 | 20/20 | Passed / passed | Left `sample.json` inside the editable seed |

All six continuations retained hashing under its independent feature and public checks, and preserved protected source/tests. No second extension was rejected by the previously fragile context fixtures. The scratch-file findings concern upgrade-bundle contents; those files stayed inside the isolated work environment.

Old 1 reached activation in the correct order and produced the exact final JSON and audit receipt, with direct calls to both capabilities. It then repeatedly inspected saved material until the 30-minute shared deadline. Its final status was paused, so explicit completion and the full workflow score remained false. The measured development segment used 28 actions; the later activated-use segment reached 108 actions. These counters reset between active runs and are not one combined action count.

The other five continuations were not activated because independent approval failed. Passing their direct feature cases does not establish that their subsequent final-use phase would have completed. The original scope/new-test requirements were retained throughout; temporary files were not removed by the operator to turn a rejection into a success.

## Selection and interpretation

The predeclared exploratory selection rule required at least 2/3 completed chains and a lead of at least two chains. Neither arm qualified. **No provisional winner was selected, and no rollback was performed.** The conditional Qwen Q4 winning-arm confirmation was therefore deferred; the successful Qwen Q6 saved-candidate reuse above remains a separate experiment.

The useful evidence is narrower and stronger than a pooled pass/fail figure:

- Both layouts repeatedly supported accepted first hashing extensions in this batch.
- Current-layout continuations passed the tested new-feature behavior in all three attempts, although none met every submission requirement.
- Three continuations were rejected for scratch JSON files in the seed, and another for omitting a new test file.
- One fully checked old-layout candidate completed the requested file operations after activation but did not stop.
- One old-layout formatter had a real ordinary-behavior defect missed by its own tests.

The next refinement should target those specific development/submission/completion problems. A concise instruction to keep disposable examples and argument files outside `harness/`, together with a submission check that reports missing tests and unexpected bundle files, is worth testing. These are proposed follow-ups, not changes made during this comparison. Any new check should explain the existing requirements before final submission without granting approval or broadening host access.

Neither the raw 1/3 versus 0/3 verification count nor the 2/3 versus 3/3 behavior count establishes a generally superior seed. Familiar prescribed tools, three repeats, one model and one fixed extension order do not qualify broad self-improvement, autonomous capability discovery or repeatability on unseen tasks.

## Evidence and final state

- [Portable results](D:/AI_New/AP/evaluations/seed-v0.2.1-seed-comparison-results.json) retain per-trial scores, blockers, measurement completeness, configuration and audit data.
- [Frozen protocol](D:/AI_New/AP/.data/seed-comparison-v021-20261019/plan.json), source snapshots, original and fixture-overlay candidate copies, trusted runner copies, provider traces, journals and grading reports remain in the private study directory.
- [Final audit](D:/AI_New/AP/.data/seed-comparison-v021-20261019/final-audit.json) confirms both source snapshots, the current root and trusted files remained frozen during inference. All 25 queued cells completed with no interrupted/error attempts. Scripted grading/calibration cells are not additional model rollouts.
- The old original starter hash is `e7bb33ec062bd0e3d90b74434000200438aff7a5740f2e92d29edba28baf78a0`. With the common fixture overlay it is `a085318b53b30d4e46a1dfcd2eab0113ed850eeab16fd6cde26d8772a6df0e7e`. The current frozen starter is `44ac04dd3eb74191ee46481899e2ccc9d9d606ca273699b03b7b53b447fa2e4c`.
- The timed-out old-growth trial has one sent request without output usage. Its known token/call totals are partial; conservative enforcement charges are not reported as measured cost. No partial aggregate is used to claim a cheaper arm.
- No model was downloaded or deleted for this comparison. Test model servers and VMs stopped; their private ports are closed. Final free SSD space is approximately **127.9 GB, 12.48%**.
- Fixture changes, controls, release notes and version bumps are local and uncommitted. The application retains the current layout; model-written candidates were not installed into the normal seed. Unrelated research notes were preserved.
