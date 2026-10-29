# Qwen 9B baseline with experimental public feedback

The completed unreleased starter study accepted **7/9 first packages**. All seven
passed first use, added and retained a second capability, and completed the final
task: **seven complete chains out of nine scheduled starts**. Six chains needed
no automatic correction. One CSV chain needed a correction in each use stage.

| First capability | Accepted first packages | Correct first use | Verified second extension | Correct second use |
| --- | ---: | ---: | ---: | ---: |
| Hashing | 2/3 | 2/2 | 2/2 | 2/2 |
| JSON formatting | 2/3 | 2/2 | 2/2 | 2/2 |
| CSV preview | 3/3 | 3/3 | 3/3 | 3/3 |

The five ordinary gates passed. Of fourteen activated-use stages, twelve passed
the published output verifier before feedback; two passed after one automatic
correction each. Final independent qualification separately checked behavior,
preservation, actual tool use, saved outputs and explicit completion. A public
verifier pass alone did not qualify a package or chain.

## Remaining failures

Both rejected third-repeat packages passed their feature behavior checks,
protected regressions and model-written tests. They failed the declared source
scope because scratch files were left inside `harness/`:

- Hashing: `development/args.json` and `test.bin`.
- Formatting: four JSON fixtures under `development/`.

These are valid package rejections, not grading false negatives. The command
traces show repeated `cd harness` invocations. The development CLI resolved
arguments and tool paths from the shell's current directory, causing missing
fixture errors and subsequent fixture copies into the source folder.

Both automatic corrections repaired CRLF characters lost in quoted CSV fields
while writing receipts. The original feedback correctly detected unequal rows,
but displayed equal expected/actual row counts without locating the changed cell.

## Conditions and accounting

Qwen3.5 9B Q6_K used the production native connection, 128K context, 4096 response
tokens, temperature 0.6, thinking disabled and no LoRA. Seeds were 104729,
130363 and 155921. Each first or second stage shared 128 actions, 65536 generated
tokens and 3600 seconds across development, grading, activation and use. The
activation reminder and public verifier were experimental options, enabled here;
application defaults were not promoted.

One unexpected outer-process exit interrupted the second formatting-to-hashing
attempt before its first response. The cause is unknown. Its source, partial
trace and observed recovery receipt were preserved; a separate attempt restarted
from the same frozen parent. No completed failure was retried. It is counted as
an interruption, not a capability failure. The owner, model and VM were absent
at recovery, and source/environment checks still matched.

There were 22 completed cells plus that interruption. The sixteen completed
feature stages recorded 833 model calls and about 3 hours 40 minutes of trial
work, excluding model loading, calibration and recovery delay. Token/timing
measurements were complete for those completed feature stages; this does not
make the interrupted attempt's costs complete. All seven final-use candidates
retained their verified source identities. The frozen source/environment check
passed at closure; the study owner, model, VM and inference listener were absent.

## Interpretation and next revision

The prior matched CSV pilot achieved 2/3 control workflows and 3/3 feedback
workflows after a separately documented activated-stage accounting regrade.
Only one pilot treatment required correction. Its original scores remain saved.
This full batch is qualification of a combined experimental configuration, not
a controlled attribution to a particular seed edit, reminder or feedback feature.
The tasks prescribe three familiar capabilities; unfamiliar-task discovery and
generalization remain unmeasured.

The authorized follow-up keeps acceptance rules and allowances unchanged. It
anchors development CLI paths to the running task workspace and adds bounded
public mismatch locations/characters. Neither change adds a new model-facing
tool. The verifier remains optional and never uses hidden failures for feedback.
A fresh comparable plan records the new seed, trusted runner and guest-runtime
identities; its results must be assessed separately.

## Evidence

- [Closed report](seed-next-public-feedback-full-2026-10-29-results.md) and
  [machine-readable report](seed-next-public-feedback-full-2026-10-29-results.json).
- [Pilot and separate audit](seed-next-public-feedback-pilot-2026-10-29-results.json).
- Private frozen plan, queue, candidates and traces:
  `.data/qwen9b-public-feedback-20261029/full/`.
- Audit: `.data/qwen9b-public-feedback-20261029/baseline-final-audit.json`.
