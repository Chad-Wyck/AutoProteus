# Qwen 9B overnight baseline and focused revision

**The revision fixed two concrete usability issues, but this comparison did not
demonstrate improved workflow reliability.** The baseline completed seven of nine
scheduled chains; the revised starter completed five. All attempts and original
scores remain saved, including one baseline infrastructure interruption.

| Independent outcome | Baseline | Revision |
| --- | ---: | ---: |
| Ordinary tasks | 5/5 | 5/5 |
| Accepted first packages | 7/9 | 6/9 |
| Correct first use, among accepted packages | 7/7 | 5/6 |
| Verified second extensions, retaining earlier behavior | 7/7 | 6/6 |
| Correct second use | 7/7 | 6/6 |
| Complete chains / scheduled starts | 7/9 | 5/9 |
| Complete chains needing no automatic correction | 6/9 | 5/9 |

The revision's second-stage totals include one **diagnostic branch** from an
accepted parent that failed first use. Its second extension and use passed, but
it cannot earn complete-chain credit. Unaccepted first packages received no
second-stage attempt.

## What changed

1. **Consistent development workspace.** The protected worker supplies the task
   root to the guest CLI. Tool paths, argument JSON and text-file arguments now
   resolve there even after `cd harness`. Standalone CLI calls without that task
   environment keep their existing current-directory behavior. Shell redirections
   still follow the shell's working directory. The worker bootstrap was rebuilt
   from verified cached appliance inputs; permissions and VM resources did not change.
2. **Bounded public feedback.** The experimental verifier can identify the first
   differing JSON location, type, length or character. Traversal is bounded and
   whole expected rows are not returned. Its pass predicate and hidden qualification
   are unchanged. This addresses baseline receipts that lost a CR in quoted CSV
   fields while retaining the expected row count.

These are model-agnostic changes. No new model-facing tool or mandatory planning
procedure was added. Public verifier feedback remains opt-in and was enabled in
both batches. The guide remains below its 12000-character whole-file read limit.

Validation before the follow-up: **531 ordinary tests ran, with 66 skips; all
passed**. All **55 protected starter tests** passed inside a VM. The workspace VM
test confirmed that invocation from `harness/` reads root argument/text files,
writes the result in the task workspace and leaves the candidate source unchanged.
The public-feedback VM checks also passed. Outside-workspace file and argument
paths remained rejected in the CLI tests.

## Acceptance by first capability

| First capability | Baseline accepted | Revision accepted | Baseline correct first use | Revision correct first use |
| --- | ---: | ---: | ---: | ---: |
| Hashing | 2/3 | 3/3 | 2/2 | 3/3 |
| JSON formatting | 2/3 | 2/3 | 2/2 | 1/2 |
| CSV preview | 3/3 | 1/3 | 3/3 | 1/1 |

Baseline hashing and formatting rejections involved scratch files placed inside
the declared source bundle. Their behavior checks and model-written tests passed.
The command traces documented cwd-dependent CLI errors and fixture copies into
`harness/`. Those were valid source-scope rejections, not grader false negatives.

The revised batch failed differently:

- **CSV repeat 2:** `text.splitlines()` discarded CRLF inside quoted fields.
  Independent `quoted_5` and `quoted_20` checks failed. It also left six CSV
  fixtures inside the source bundle. Its own 72-test suite passed.
- **CSV repeat 3:** `truncated` was true whenever the preview filled its limit,
  even when no additional record existed. The exact-one-record and Unicode
  exact-one-record checks failed. Its own 74-test suite passed; source scope was clean.
- **Formatting repeat 3:** it modified protected `autoproteus/file_ops.py`.
  Feature grading was withheld by the edit-scope guard. Its feature correctness
  is unmeasured, not an independently demonstrated implementation failure.
- **Formatting repeat 2 first use:** saved files were ultimately correct after
  automatic public feedback, but the model used ad hoc Python instead of invoking
  its registered `format_json` capability. All activated-stage actions were
  inspected; this is a genuine use failure. Its later diagnostic second extension
  does not retroactively repair that failed first-use stage.

## Public assistance versus qualification

Baseline public output checks passed initially in **12/14** activated stages;
the remaining two passed after one automatic correction each. Both corrections
were in the same CSV chain, so six of seven complete chains needed no feedback.

Revision public output checks passed initially in **11/12** stages. Its one
correction fixed formatting and the byte receipt, but did not cause use of the
required tool. Thus all twelve final artifact checks passed while only eleven
activated stages met independent use qualification. Every complete revised chain
needed no automatic correction.

The new CSV character/location diagnostic was validated with scripted tests
using the observed errors. This live batch did not exercise it on a CSV receipt
error: the corrected revision case concerned formatting and bytes. A model-level
benefit from the richer CSV diagnostic is therefore **unmeasured** here.

The earlier matched pilot recorded control **2/3** versus feedback **3/3** complete
directed growth workflows. One pilot grade was corrected offline because it
forgot a successful hash call made before the automatic correction run. Original
scores are preserved; no candidate was repaired or rerun for that regrade. Full
qualification uses an explicit activation boundary spanning all correction runs
while excluding development. The pilot is not a first/second-chain qualification.

## Comparison and cost limits

Both full batches used the same pinned Qwen3.5 9B Q6_K profile, native production
adapter, 128K context, 4096 response tokens, temperature 0.6, thinking disabled,
three sampling seeds and fixed case pack. Both enabled the same reminder and
experimental feedback setting. Each first or second task shared 128 actions,
65536 generated tokens and 3600 seconds. Exact source, trusted-runner and guest
runtime identities are preserved separately. Matching seeds do not guarantee
deterministic inference.

The baseline had 16 completed feature stages, 833 calls and about 3h40 of recorded
trial work. The revision had 15 stages, 718 calls and about 2h31. These totals
cover different amounts of successfully qualified work and are not an efficiency
ranking. Loading/calibration and the baseline interruption are outside those
completed-stage totals; its partial attempt remains visible separately.

Across the **four chains complete in both batches**, recorded calls were
**465 versus 368** (20.9% fewer); output tokens were 75260 versus 61422. Those
completed-stage measurements were complete. This small descriptive subset does
not establish a causal efficiency gain, and wall-time conditions were not controlled.

No model-written candidate was edited by Codex. One baseline outer-process exit
interrupted an unfinished attempt before its first response; the cause is unknown.
It was retained and separately retried, while completed failures were not retried.
The revision ran without infrastructure interruptions. No resource stops occurred.

This is one before/after comparison of familiar prescribed capabilities, not
qualification of the fresh default profile, unfamiliar extension discovery or
general-purpose 9B reliability. The directly tested CLI fix is useful, but further
seed instruction growth or promotion of experimental feedback is not supported
by these counts alone.

## Evidence and closure

The audit rechecked **26 activated stages** against saved final bytes and actual
tool-use journals. All matched recorded qualification, including the missing-tool
failure. Accepted submitted source hashes were verified against actual final
quarantined source bytes. Both frozen trusted-runner archives and every owned
cleanup receipt were checked. The final revised source/environment check passed;
the runner, model, VM and port 47848 listener were absent on inspection.

- [Comparison data](seed-next-overnight-comparison-2026-10-29-results.json).
- [Baseline findings](seed-next-public-feedback-full-2026-10-29-findings.md) and
  [closed report](seed-next-public-feedback-full-2026-10-29-results.md).
- [Revised closed report](seed-next-workspace-revision-2026-10-29-results.md).
- Private evidence, frozen plans and validation logs:
  `.data/qwen9b-public-feedback-20261029/`.
- Detailed source/artifact audit: `final-comparison-audit.json` and
  `final-artifact-and-use-recheck.json` inside that directory.

Changes remain local and uncommitted. No default model settings or verifier
policy were promoted, and no additional model study is part of this goal.
