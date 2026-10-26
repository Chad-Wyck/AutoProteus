# Qwen3.5 9B: unchanged v0.14.0 growth pilot

The frozen seed produced **one fully accepted first extension out of three**.
Its one eligible second extension passed independent verification and preserved
the earlier capability. Final files were correct and completion explicit, but
neither added capability was invoked during final use: **0/1 complete growth
chains**. This is useful implementation evidence, not reliable cumulative-use
qualification. No operator repaired a candidate or supplied corrective answers.
The complete pilot took approximately 63 minutes, including calibration and
ordinary checks. The test model service stopped and its VM slot was released
afterward.

## Frozen configuration

- Repository checkpoint: `8808584`, v0.14.0; no source changes during trials.
- Seed SHA-256: `944dde7bd0e5185699c292b929d0fd4042031266872fc29a8af4c38a84b88465`.
- Qwen3.5 9B Q6_K, GTX 1080 Ti, Ollama 0.40.4; standard production adapter,
  native tools, thinking off, temperature 0.6, 65,536 context / 4,096 response.
- Model digest: `a728516d76aae19657140edb551b7c09eb6dac5bff1f90931a5271fcc925dd8a`.
- One exploratory repeat: benchmark, five ordinary tasks, three prescribed
  first extensions, then second extensions only from fully accepted parents.
- Each extension trial: 128 actions, 3,600 shared wall seconds and 65,536
  generated tokens. The provider request timeout remained 300 seconds.
- Terminal enabled in disposable VMs; internet disabled. App preferences were
  not changed. Model identity and frozen runner/source checks remained active.

Private evidence: `.data/qwen-v014-growth-20261025/study/`. The exact plan,
calibration receipts, queue, provider traces, source snapshots, independent
checks and every launched result are retained there. Completed failures were
not retried. Ten cells completed; two dependent growth cells were not launched
because their parents were not accepted. There were no interrupted queue cells.

## Observations

The inference screen and all **5/5 ordinary tasks** passed.

| First extension | Independent outcome | Fully accepted | Trial seconds |
| --- | --- | --- | ---: |
| `sha256_file` | Protected, feature, public-use and candidate checks passed | Yes | 414.914 |
| `csv_preview` | Omitted optional `limit` raised `ValueError` instead of using five | No | 986.276 |
| `format_json` | All held-out behavior assertions and public invocation passed; candidate suite failed and development ended in a provider timeout | No | 1569.238 |

The CSV candidate advertised its optional default correctly, but did not honor
it in execution. Other recorded feature assertions passed. Its own full suite
passed, demonstrating why independent default-omission checks remain necessary.

The standalone JSON candidate's full suite had two failures and one error:
an incorrect indentation expectation, an oversized-output fixture that only
expanded to 80,017 characters, and a purported valid Unicode fixture exceeding
the 100,000-character input limit. Protected starter regressions passed.
Development ended after 68 actions with a **model-response timeout**, rather
than exhausting the 128-action allowance or 60-minute trial deadline. Its
implementation's passing behavior assertions do not erase failed package checks
or establish a completed upgrade.

The accepted hashing parent then added a different `format_json` implementation:

| Second-extension condition | Result |
| --- | --- |
| New capability independently verified | Pass |
| Hashing behavior and public use preserved | Pass |
| Real input preserved during development | Pass |
| Candidate activated | Yes |
| Final canonical JSON and audit hashes/byte counts | Correct |
| Explicit final completion; activated source unchanged | Pass |
| Both capabilities used after activation | Fail |
| Complete functional growth chain | Fail |

This trial took 616.649 seconds. The final phase used existing read/list/write
tools. Neither direct calls nor recognized development invocations of the two
added tools were observed in that phase. This is more specific than a preference
for native calling syntax: both accepted invocation routes were absent. Correct
artifacts and verified capabilities are recorded separately from verified use.

## Relation to the preceding completion pilot

The earlier practical check passed 3/3 synthetic ordinary tasks through the saved
8K-context app profile. A separate six-attempt final-contract comparison used
the same larger research configuration as this growth pilot: baseline 3/3,
public final-task restatement 2/3. Those are ordinary final-use tasks, not seed
extension chains, and must not be pooled with the growth results above.

The restatement arm's failed Unicode-copy attempt read the correct default
1,000-character section, then received four runtime rejections of incomplete
`write_file` JSON arguments. No partial action executed. The trace does not
establish why the arguments were incomplete. It does not show another failure
to retain the requested default and does not justify adding the restatement to
the default seed. Evidence: `.data/qwen-v014-20261025/final-contract/` and its
`failure-review.md`.

## Measurement limits and next experiment

The standalone JSON run reported 10,532 output tokens with one unmeasured sent
call; the budget charged 14,628 conservatively. That charge is not a complete
measurement of generated tokens. The other extension trials reported complete
output usage: hashing 7,654, CSV 12,651, second extension 12,535. Traces retain
measurement-coverage flags; do not compare partial costs as complete totals.

Keep the starter frozen. The next narrow hypothesis is whether a required-only
invocation in development catches the omitted-default defect before submission.
Separately, test final use on fresh inputs after activation to distinguish actual
reuse from copying values obtained during development. Preserve current scores
and apply any changed protocol prospectively. One repeat on prescribed tools
does not establish repeatability or capability discovery; qualification needs
unfamiliar capabilities and another model. No additional seed framework is
warranted by this pilot.
