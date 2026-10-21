# v0.3.0: public feedback, precise source context and curated experience

This local revision follows the v0.2.1 fixture correction and paired OxCoder
comparison. It preserves the current seed layout. No candidate is installed as
the starter, no weights are trained, and no live-model benefit is established.

The initial [validation receipt](seed-v0.3.0-validation.json) records 247 ordinary tests
passed, 46 skipped, two scripted real-VM checks, JavaScript syntax and browser
preview checks. Three fresh paired plans match the current frozen inputs.
They use the existing OxCoder 9B Q6 profile with three repeats; their scripted
calibration still runs before live inference. No live trials were started during
that preparation. These original fingerprints are historical after later fixes;
prepare fresh plans rather than reusing them.

The release adds bounded format-repair parity to connection qualification and
additional staged-input delivery checks. See the separate
[release validation](seed-v0.3.0-release-validation.json) and
[Qwen staged-input plan](staged-inputs-v0.3.0-plan.md). The earlier
[OxCoder feedback results](seed-v0.3.0-feedback-findings.md) retain their original
verdicts and qualification failure; the new check does not retroactively qualify
that run.

## First comparison: public submission feedback

Prepare one balanced comparison with the same model, contracts and allowances:

```text
python evaluations/model_study.py prepare --profiles profiles.json --output .data/submission-feedback-study --mode full --repeats 3 --experiment submission-feedback
python evaluations/model_study.py run --input .data/submission-feedback-study --check-only
python evaluations/model_study.py run --input .data/submission-feedback-study
```

The treatment allows at most two public repair continuations before any hidden
grading. Each ticket identifies the source, public scope/test-file/syntax issues,
and the latest observed development-check failure when available. Hypotheses
are labelled. Earlier command output can refer to an earlier source version;
it is not an independent verdict. No candidate is repaired or activated by the
controller. Existing scope and acceptance rules still apply.

Continuations use the original running seed, saved files and user instructions,
not the unverified edited runtime. They share one cumulative action allowance,
generated-token budget and absolute deadline with development, all grading,
activation and final use. Explicit completion remains required. Original task,
each ticket, continuations, costs and independent results are saved separately.
There are no success-selected hidden retries. In the ordinary app the same
feedback is optional, with a review control and an explicit resume choice;
ordinary app Resume retains its usual fresh allowance.

## Compare source context and lessons separately

Use `--experiment edit-context` for a direct task packet. It includes qualified
symbols, real headers/defaults, imports and dispatcher/registration excerpts,
an existing invocation example, Unicode character positions, file hashes and
explicit omissions. The whole JSON packet is capped at 12,000 UTF-8 bytes;
support instructions are additional input measured by normal call traces.
Original human requirements remain separate and authoritative.

The guest helper parses source without importing it. After an included file
changes, discard its old excerpts. `python3 experience/context_packet.py`
regenerates current context; `--check experience/context.json` reports whether
the initial packet is stale without returning obsolete excerpts. Helpers and
packet fixtures stay outside harness/. The runner records final stale paths.
This tests supplying context, rather than offering another optional outline tool.

Use `--experiment verified-lesson` for one optional ordinary Markdown file with
an applicability cue, procedure, exact report references, evidence, hypothesis
and limitations. Both arms already receive the normal fixed upgrade recipe;
the treatment additionally offers this curated lesson with a read hint. This
is a human-curated experience experiment, not autonomous learning. Provision,
observed file reads, following (unmeasured), and independent task outcomes remain
separate. The file never claims its own causal usefulness.

All three treatments can use `--parent-source` and `--parent-tool` to compare
growth from one exact independently qualified parent. This avoids attributing
differences between separately generated parents to a continuation treatment.
Supplied parents receive no new first-upgrade credit. Historical plans remain
historical; prepare new plans after any source/runner change.

## What to measure

Rank independently verified functionality and completed workflows first. Keep
first-pass results, repaired submissions and reuse distinct. Compare calls,
tokens, reading, test repairs, time and costs among matched successes, retaining
partial-measurement flags. Inspect invented API errors in saved development
output; they are diagnostic evidence, not a new correctness score. Complete
one balanced comparison before another. Repetition and unfamiliar tasks are
needed before promoting either experimental support into the normal seed.

The app connection qualification is separate: it tests protocol exchanges and
recovery with the advertised catalog, not upgrade ability. Capability progress
similarly distinguishes declaration, checked source, activation and observed
model use. An independent checker using a tool is not model-chosen use.
