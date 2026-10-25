# v0.7.0 handoff and early-verification comparison

Both frozen runtime arms produced 3/3 independently verified hashing extensions,
retained CSV behavior and activated. Both produced 0/3 correct final artifacts
and 0/3 complete workflows. All final audits contained two rows instead of the
required default five. No operator candidate repairs were made.

The revised arm wrote its plan before editing in all three attempts, but its
plans copied the whole original task, including the earlier `limit: 2` step and
development instructions. No revised attempt wrote the requested
`development/verify_task.py` through the observed file tools, and the exported
files contain no such script. Thus this batch does not establish benefit from
actually using early final-output assertions.

All three revised attempts timed out at 1800 seconds after activation, repeatedly
calling the working CSV tool with `limit: 2`. The first made that exact call
59 times. The seed already supplied an unchanged-reading progress hint, which
did not stop the behavior. Repeatedly presenting the stale plan as a remaining
task is a plausible contributing factor; the initial comparison does not isolate
that cause. The mandatory plan did not improve correctness and coincided with
substantial additional interaction cost.

| Measurement | v0.6.0 | v0.7.0 initial revision |
| --- | ---: | ---: |
| Scored attempts / actual launches | 3 / 3 | 3 / 3 |
| Verified extensions | 3 | 3 |
| Activated | 3 | 3 |
| Correct final artifacts | 0 | 0 |
| Complete workflows | 0 | 0 |
| Calls | 201 | 363 |
| Trial wall seconds | 1683.979 | 5400.865 |
| Known input tokens | 2003429 | 4097386, partial |
| Known output tokens | 26211 | 43538, partial |

Baseline usage measurements cover 201/201 calls. Revised usage covers 360/363;
three timed-out calls have missing measurements and trace completion is false.
Do not treat the revised partial sums as complete costs or compare costs among
successful workflows: there were none. The raw accepted flag was false for all
development submissions in this batch because they requested activation in
`waiting` status, as the task requested. All independent code checks passed.

Validation before inference: 337 ordinary tests, 46 skips, and the strengthened
real-VM activation test passed. Both overlaid starter suites passed all 50
protected cases, all supplied-parent checks and grader calibration passed, and
standard native model qualification passed first try in eight calls. Candidate
code executed only in disposable network-free VMs.

Model: Qwen3.5 9B Q6_K, 131072 context, 4096 responses, temperature 0.6,
thinking off, no LoRA. The exact original tasks, fixtures and graders were kept.
Each attempt shared 128 actions, 65536 generated tokens and 1800 seconds across
development, grading, retention and use. Model-written scripts were never run
on the host. Application edits remain local and uncommitted.

The next focused comparison tests handoff-only notes, then the same source with
the existing public `final_task` delivered explicitly after activation. It uses
no hidden expected answer and no new capability framework. Persistent-note
results above remain a historical reference, rather than being counted as fresh
paired controls in that follow-up.

- [Frozen plan](D:/AI_New/AP/evaluations/seed-v0.7.0-final-task-plan.md)
- [Results and model-written plans/verifiers](D:/AI_New/AP/evaluations/seed-v0.7.0-final-task-2026-10-23-results.json)
- [Execution manifest](D:/AI_New/AP/.data/task-handoff-v070-20261023/execution-01/execution-manifest.json)
- [Unmodified queue](D:/AI_New/AP/.data/task-handoff-v070-20261023/execution-01/queue.json)
