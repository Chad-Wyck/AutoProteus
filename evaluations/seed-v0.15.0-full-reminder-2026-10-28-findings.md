# Qwen 9B full growth study with an activation task reminder

The frozen v0.15.0 starter accepted **5/9 first extensions**. All five accepted packages completed their first autonomous use. All five eligible second extensions independently verified and preserved the earlier capability, but only **2/5 completed final use**, giving **two complete growth chains out of nine scheduled starts**.

## Results

| First capability | First packages accepted | Correct first use | Second extension verified | Correct second use / complete chain |
| --- | ---: | ---: | ---: | ---: |
| `sha256_file` | 3/3 | 3/3 | 3/3, adding `format_json` | 2/3 |
| `csv_preview` | 2/3 | 2/2 | 2/2, adding `sha256_file` | 0/2 |
| `format_json` | 0/3 | Not reached | Not reached | Not reached |

The five ordinary task gates passed. No second stage was attempted for the four rejected first packages. Two user-requested gaming interruptions were preserved as separate attempts, then explicitly retried; they are excluded from model-quality denominators. There were no resource stops or infrastructure errors in this batch.

The report preserves functional use separately from calling route. One successful chain used the development/Python route and passed independently checked functionality and actual capability use; its strict native-route score remains false.

## Setup and intervention

- Qwen3.5 9B Q6_K, native production adapter, 131072 context tokens, 4096 response tokens, temperature 0.6, thinking disabled, no adapter.
- Sampling seeds: 104729, 130363 and 155921. These are repeated sampling conditions, not a guarantee of deterministic generation.
- Per first or second stage: 128 actions, 65536 generated-token allowance and one shared 3600-second deadline covering development, grading, retention, activation and use.
- Frozen starter identity: `34588c61faa52d0288fc52fcfbf95dca5a730499a6fca1e486921bda717fdd0c`, Git base `f3f3533`. Internet disabled for this study; application settings unchanged.
- After independent checking and host activation, the experimental host context repeats the final-use clause **verbatim from the original user task**. It supplies no grader feedback or new requirements. Delivery was recorded in all five first-use and five second-use branches. Rejected packages never reached that intervention.
- Codex did not edit candidates or coach individual runs. Gaming interruptions restart only the interrupted cell from its frozen input, retaining the abandoned attempt and its costs. No completed cell was rerun.

## Failure audit

First-package rejections had different causes:

1. Formatting repeat 1 exhausted 128 actions. All 20 independent feature behavior checks passed and protected regressions passed, but the model's own test suite still had failures and errors. Examples include expecting error dictionaries where the workspace raises exceptions, an inverted key-order assertion, and an output-size fixture below the rejection threshold. This is a package/workflow failure, not evidence that those independent feature checks failed.
2. Formatting repeat 2 reached the shared hour limit after 48 actions and 49 requests. Independent checks were not launched after expiry. Its final feature correctness is **unmeasured**, although it did not qualify as an accepted package.
3. CSV repeat 3 exhausted 128 actions. All 35 independent behavior checks and protected regressions passed, while model-written tests failed. Examples include expecting 20 rows from a ten-row fixture, confusing literal Unicode escapes with encoded characters, and using the bounded write tool to construct an intentionally oversized fixture.
4. Formatting repeat 3 passed its 71-test development suite but failed two independent Unicode boundary checks. Its implementation reused the display-oriented `read_file` helper, imposing that helper's 12000-character limit on a tool contracted to accept 100000 characters. This is a real implementation error. The final interrupted attempt was restarted with user authorization and completed in about 12 minutes; it was not stopped by the deadline.

Second-use failures also remain real:

- Both CSV-to-hash branches preserved the input and wrote correct path, byte count and SHA-256 fields, but saved a two-row preview with `truncated=true`. The requested default preview contains all three records and `truncated=false`. Both capabilities were invoked, and source remained unchanged. These are incorrect final artifacts, not the earlier evidence-parser false negative.
- Hash-to-format repeat 3 verified both capabilities but requested activation again after activation and reminder delivery. It stopped waiting for a reply without performing the final formatting, hashing and audit task. Neither time nor generated-token exhaustion caused this stop.

## Cost and limits of the evidence

The fourteen completed feature stages consumed about **5 hours 18 minutes** of recorded trial time, excluding model loading, gaming pauses and interrupted-attempt time. Known completed-stage sums are 19991738 input tokens and 186015 output tokens, but these are **partial**: the timed-out formatting trial lacks complete measurements for its final request. The detailed report retains measurement completeness separately for tokens and timing and includes interrupted attempts without treating them as model failures.

This is one full reminder treatment batch, with three familiar, prescribed extensions. It has no simultaneous full-growth control and does not establish that the reminder improved first-package acceptance, unfamiliar-task generalization or everyday default-profile performance. The reminder occurs after activation, so it cannot repair coding-stage defects. It helped support successful handoffs here but did not make final task completion reliable.

The ordinary editable seed and app defaults remain unchanged. Frozen source/environment checks passed after the run. All 22 launched attempts have cleanup receipts confirming their owned model process stopped, and the final runner, model, VM and dedicated inference listener were absent on inspection.

## Evidence

- [Closed outcome report](seed-v0.15.0-full-reminder-2026-10-28-results.md) and [machine-readable results](seed-v0.15.0-full-reminder-2026-10-28-results.json).
- Private raw plan, queue, request traces, source snapshots, receipts and candidate checks: `.data/qwen9b-full-reminder-20261028/study-final/`.
- [Earlier activation-only replay](seed-v0.15.0-handoff-replay-2026-10-28-results.json) and its [separate evidence-parser regrade](seed-v0.15.0-handoff-replay-2026-10-28-regrade.json). Original scores and records remain intact.
