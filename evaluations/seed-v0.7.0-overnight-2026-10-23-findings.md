# Overnight Qwen 9B seed refinement: completed assessment

**Qwen completed 3/3 full workflows when the final request explicitly instructed
it to omit the optional preview limit. The refined seed alone completed 1/3.**
These are different conditions. This study does not establish consistent
autonomous completion from the seed alone.

Eighteen actual attempts across three frozen comparisons all produced
independently verified hashing extensions, retained the supplied CSV capability
and activated. The initial CSV capability was supplied from a human reference;
this is directed second-extension evidence, not autonomous creation of both
features or model-selected capability discovery.

| Condition, three attempts each | Verified extension | Correct artifacts | Complete workflow |
| --- | ---: | ---: | ---: |
| v0.6.0 runtime reference | 3/3 | 0/3 | 0/3 |
| Initial v0.7.0 persistent final-task plan | 3/3 | 0/3 | 0/3 |
| Model plan shown once at activation | 3/3 | 1/3 | 0/3 |
| Same source + original public final clause repeated | 3/3 | 0/3 | 0/3 |
| One-time plan + general default-argument rule | 3/3 | 1/3 | 1/3 |
| Same source + explicit public argument-omission instruction | 3/3 | 3/3 | 3/3 |

Rows belong to different conditions and some are historical references across
separate batches. Do not pool their results into a current-default success rate
or attribute differences between batches to one change. Each batch's fresh
paired arms and source identities are documented in its individual report.

## What was learned

The requested early planning and verification changes were implemented using
the existing task-plan file and development-script convention. The model wrote
plans before editing in all 15 revised-source attempts, but copied earlier
two-row instructions and development steps into them. It never exported the
requested early final-output verification script in those 15 attempts. Receipt
of verification guidance is not evidence of adopting that procedure.

Repeatedly appending the stale model-written plan after new tool observations
coincided with three 30-minute timeouts and repeated successful two-row preview
calls. The first such attempt made the same CSV call 59 times. An existing
unchanged-reading progress hint did not stop it. The follow-up therefore tested
a smaller context correction rather than adding another navigation tool or
reminder: show the plan once on activation and let subsequent results lead.
Files, full journals and all original human requirements remain available.

One handoff-only attempt produced a correct audit but exhausted its actions
without finishing. Its functional-workflow failure is appropriate. Five others
finished with two rows. Repeating the existing final clause, which still said
"default preview," did not fix the argument selection.

The last comparison made default application concrete. A general model-agnostic
rule alone still failed to change any of the three direct CSV calls: all
supplied `limit: 2`. One nevertheless saved five rows, so its existing functional
score passed. That score verifies files plus observed required tool use; it does
not prove every receipt field came from a particular call. The direct-argument
observation is reported separately.

The explicit follow-up instead said to supply only `path` and omit `limit`.
All three models did so, used both tools and completed correct audits. The
follow-up did not contain the numeric default, an expected hash, file contents
or a verification script, and independent grading was unchanged. It did add a
clearer public user instruction, so its success must remain distinguished from
seed-only autonomous success.

## Local changes retained

The working tree is a local, uncommitted v0.7.0 candidate based on `532e36b`:

- Record the final-use plan in existing `todo.txt`, with explicit model-authored
  provenance and human instructions taking precedence.
- Show that plan at activation, then stop appending it after each assistant
  action. A new genuine activation receives a fresh handoff. A human message
  resembling an activation marker does not reset this behavior.
- Prepare final-output assertions before implementation and run them after
  final use. This remains requested guidance; live adoption was not demonstrated.
- Apply a requested default by omitting that optional argument rather than
  reusing an earlier step's override. The rule is general; the live model did
  not consistently follow it without a concrete final instruction.

No new seed modules, capability framework, provider-specific branches, model
weights or tool interfaces were added. Editable runtime Python grew by 1075
bytes, from 53454 to 54529. The seed README is 10414 characters, still within the
12000-character whole-file read limit. Model settings, independent verification,
VM policy and host permissions were preserved.

The retained `context.py` and `protocol.py` bytes exactly match the final tested
model variant. Live tasks used supplied CSV parents with common protected
fixtures, so this does not qualify the unextended starter or normal installation
defaults. Final root seed identity:
`db12975dfd60e02ae342be6b5ba3cf3d634d092c4824a0e4f96692dfdb032f51`.

## Validation, resources and limits

Final ordinary regression suite: **338 tests, 46 skipped, 292 passed**. The
strengthened real-VM activation test also passed. It checks carried files and
the prepared verifier, first-request plan visibility, later omission, stable
opening instructions, preserved human corrections and the complete journal.
The unit tests additionally cover bounded notes and human text imitating an
activation marker.

Each batch passed both common 50-case starter suites, CSV positive/public checks,
hash-capability absence checks and independent grader calibration before model
calls. Both follow-ups also passed their scripted one-time-context VM probes.
All three standard native qualifications passed first try in eight calls each.
These are infrastructure checks, separate from model capability outcomes.

All 18 attempts are retained; there were no model-trial retries or operator
candidate repairs. One follow-up driver import error occurred before any model
request or trial launch and has a separate preflight receipt. Every model-written
candidate and script executed only inside a disposable, network-free VM. Host
analysis only read saved bytes, logs and JSON.

The model and sampling were fixed: Qwen3.5 9B Q6_K, 131072 context, 4096 responses,
temperature 0.6, thinking off, no adapter, standard native connection. Each
attempt shared 128 actions, 65536 generated tokens and 1800 seconds across all
stages. The user's disk-reserve waiver was honored. Batches completed within
their four-hour bounds and the family within its eight-hour bound. Long
interruptible waits conserved assistant usage while local runs proceeded.

There were 1011 trial calls and 24 separate qualification calls. Trial wall time
summed to 12298.779 seconds, about 205 minutes. Known trial input usage is
11267344 tokens and known output usage 146390 tokens, measured on 1008/1011
calls. These are partial totals: three timed-out calls in the initial revised
arm left incomplete traces/measurements. Keep timing completeness flags as well;
having a known sum does not establish complete timing. Per-round costs, original
verdicts and all source identities are in the machine-readable results.

The original task required a default five-row audit after an earlier explicit
two-row step. Five artifacts were correct across the different conditions;
four full workflows completed. Thirteen failures had the wrong row count; one
had correct files but failed to finish. All inputs and verified sources were
preserved, and all other checked receipt fields were correct. These pooled
counts are an audit of every attempt, not a model qualification rate.

## Decision

Stop this bounded study here. We now have evidence of complete workflows under
an explicit public final instruction, plus evidence that the refined seed alone
remains unreliable. Coding the extension was not the blocker in these runs.
More source-navigation machinery or another generic progress warning would not
directly address the dominant final-argument mistake, and an existing warning
already failed to stop repetition.

Before promoting these local changes as a reliable default, test unfamiliar
tasks and changed optional parameters without supplying a prepared final-step
clarification, and qualify another model. Improvements to requirement handling
and actual verifier adoption remain open. No further model trials were started
after the final six-run comparison; no changes were committed or pushed.

- [Complete machine-readable audit](D:/AI_New/AP/evaluations/seed-v0.7.0-overnight-2026-10-23-results.json)
- [Initial comparison](D:/AI_New/AP/evaluations/seed-v0.7.0-final-task-2026-10-23-findings.md)
- [One-time handoff comparison](D:/AI_New/AP/evaluations/seed-v0.7.0-handoff-followup-2026-10-23-findings.md)
- [Final default-argument comparison](D:/AI_New/AP/evaluations/seed-v0.7.0-default-followup-2026-10-23-findings.md)
- [Final source and regression receipt](D:/AI_New/AP/.data/v070-final-validation.json)
- [Final host cleanup receipt](D:/AI_New/AP/.data/v070-final-host-check.json)
