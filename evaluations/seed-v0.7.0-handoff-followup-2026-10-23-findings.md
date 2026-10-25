# Handoff-only notes and the existing public final instruction

The two fresh arms used the identical copied seed, source SHA-256
`812290b5a520d2b96321aec5286ca4a7f1bfcb7b79e516b1819445df3878de90`.
The single source correction stops appending model-written todo notes after the
first assistant action following activation. The file remains available; a new
genuine activation receives notes again. Internal provenance distinguishes the
activation marker from literal human text. Original human requirements and
corrections remain protected.

| Result | Handoff once | Same source + existing public final task |
| --- | ---: | ---: |
| Actual/scored attempts | 3 | 3 |
| Verified extensions | 3 | 3 |
| Activated / retained CSV | 3 / 3 | 3 / 3 |
| Correct final artifacts | 1 | 0 |
| Complete workflows | 0 | 0 |
| Calls | 184 | 90 |
| Output tokens | 33641 | 14698 |
| Trial seconds | 2185.522 | 1027.115 |

The correct-file attempt preserved the input, saved five rows, used both tools
directly and preserved the verified source. It exhausted 128 actions and paused
without explicit completion, so full workflow failure is correct. Its 24 CSV
calls and repeated-reading hints show that showing the plan once did not
eliminate all repetition. The other five attempts explicitly completed but
saved the earlier two-row preview.

All six plans were written before the observed first seed edit. No exported
`development/verify_task.py` existed in any attempt and no command to run it was
observed. The early-verification instruction therefore remains unvalidated as
an adopted model procedure. All output-token measurements cover every call.
Other completeness flags, original verdicts and source identities remain in the
machine-readable results; do not infer complete costs from only this table.

The public final instruction was already a clause of the initial task and was
repeated verbatim using the evaluator's existing final-contract treatment.
It still said "default preview" and supplied no numeric limit or hidden answer.
Its three failures do not show that a more explicit argument-omission instruction
would fail; the last bounded follow-up tests that distinction.

Both parents passed the 50-case protected suite, positive/public CSV checks,
hash-tool absence checks, and the scripted context probe. Grader calibration and
the standard model connection passed before inference; qualification took eight
calls. A driver initialization import error happened before any model request
or trial launch and is retained in the preflight-error receipt. There were no
model-trial retries or operator candidate repairs.

The initial persistent-note batch is historical reference, not a fresh paired
control. This batch cannot establish a causal reliability gain from the source
correction, and its familiar CSV/hash tasks do not establish generalization.
The fresh paired arms isolate repeating the existing public final instruction
with identical source. All code execution and grading stayed in disposable VMs.

- [Plan](D:/AI_New/AP/evaluations/seed-v0.7.0-handoff-followup-plan.md)
- [Results and exported model notes](D:/AI_New/AP/evaluations/seed-v0.7.0-handoff-followup-2026-10-23-results.json)
- [Manifest](D:/AI_New/AP/.data/task-handoff-once-v070-20261023/execution-01/execution-manifest.json)
- [Driver preflight error, before model calls](D:/AI_New/AP/.data/task-handoff-once-v070-20261023/preflight-errors.json)
