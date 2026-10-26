# Activation/use protocol v2 and offline measurement

This is an evaluation change. The editable starter and host permissions remain
unchanged. Existing plans, private evidence and published scores retain their
original protocol; changing runners invalidates their fingerprints. A friend
testing `d8e7175` should finish on that checkout. Use a separate checkout/output
folder for v2 rather than updating a running study.

## Four separately scored stages

1. Add the first tool and submit it for independent checking. The public task
   requests `needs_input` for activation; waiting is a valid submission.
2. Activate the checked source in the same task, deliver fresh inputs withheld
   during development, and ask the model to finish the already declared use task.
3. Start a fresh task to add a second capability to the frozen verified parent,
   preserving the earlier capability and its tests.
4. Independently check/activate that candidate and complete the two-tool audit.

The first-use goal is declared before development; activation does not provide
held-out answers, corrective coaching or a manually repaired candidate. Inputs
vary by repeat and are frozen in the host plan. Paired variants/models receive
the same case bytes. No first-use task input/receipt path may be created early.

For hashing, the agent saves the new tool's exact path/byte/hash receipt. CSV use
saves a default-five preview, including quoted CRLF and Unicode. Formatting must
change the fresh file to canonical JSON and save its path/byte receipt. The host
checks exact file content independently and observes a successful invocation on
the **actual fresh path**, with the expected tool result, after activation.
Calls made during development do not count. Direct calls and recognized guest
CLI/program invocations remain valid. Inspection and explicit optional-default
omission are diagnostics, not arbitrary additional route requirements.

The first stage retains its independent review. `first_package_accepted` is the
v2 ready-package result; the raw legacy `review.accepted` definition remains in
the review for provenance. `first_use.passed` separately requires correct files,
observed fresh use, unchanged activated source, explicit completion and budgets.
`first_accepted` in a v2 summary counts ready packages, not completed user tasks.

Invalid first packages are ineligible for a second edit. A valid package whose
first use failed can receive a labelled second-stage diagnostic from its frozen
checked source. First-use mutations are not promoted. A successful diagnostic
does not erase the first failure or earn complete-chain credit. A supplied parent
or a first-only experiment cannot establish a full autonomous chain.

Each edit-and-use task shares one action, wall and generated-token allowance.
Activation receives only the remaining actions. A second task receives a fresh
allowance. This also corrects the older baseline path's action reset at activation;
old results remain under their original policy rather than being rescored.

## One prepared efficiency experiment

The closed-trace audit found that the long accepted v0.14.0 hashing attempt made
75 successful reads after its first full passing development suite; 59 targeted
the registration file. Seventy post-check reads returned at most 100 characters.
This suggests testing precise source navigation. It does not prove that the
model confused line numbers and character offsets, nor that all reinspection
was unnecessary.

The single treatment is `source-outline`, an opt-in copied seed tool that parses
Python without importing it. It returns Unicode-character ranges for functions,
classes and top-level declarations such as `TOOL_SPECS`, with line numbers kept
separate. The normal seed gains no tool or instruction. No context masking,
shorter recipe or other intervention is combined with this treatment.

Prepare a six-attempt balanced pilot using one frozen profile:

```text
python evaluations/model_study.py prepare --profiles profiles.json --output .data/navigation-v2 --mode full --repeats 1 --first-only --experiment source-outline --timeout 3600 --output-token-budget 65536
python evaluations/model_study.py run --input .data/navigation-v2 --check-only
```

Use the bundled Python for your platform. Preparation and scripted calibration
start no live models. Run without `--check-only` only when ready for inference.
Compare first-package acceptance and first-use completion separately. Efficiency
comparisons require matched completed first-use successes with complete usage
and timing measurements; retain failed attempts and partial measurements too.
One repeat is a pilot. A benefit needs repeated/unfamiliar tasks and another model
before promotion into the starter. Second extensions are not requested here.

## Closed-trace audit and report

```text
python evaluations/trace_audit.py --input .data/finished-study --output .data/trace-audit.json
python evaluations/study_report.py --input .data/finished-study --output .data/study-report
```

These read closed exports as data, without a recovering `Store`, candidate
imports or replay. Actively running queues are refused. Exported absolute paths
are not followed; evidence is located within the supplied study folder. The
timeline separates first source/test edits, first/last full passing checks,
finishing, read paths, repeated observed content and small post-check reads.
A focused pass is not mistaken for a full passing suite. None of these metrics
proves causation or replaces independent acceptance.

The overnight results and the tested optional-planning revision are recorded in
[the findings](seed-v0.14.0-activation-use-2026-10-26-findings.md). A newly observed
Python-variable route needed an observer correction. To reassess first use from
a closed v2 export without rewriting its primary results:

```text
python evaluations/use_reassessment.py --input .data/finished-study --output .data/first-use-reassessment.json
```

This verifies saved artifact/candidate hashes and recorded stage/budget/finish
conditions. It does not replay candidates or alter independent feature reviews
or second-task verdicts. Raw and reassessed outcomes must be labelled separately.

The compact report preserves separate implementation, interface, candidate-test,
protected-regression, submission-scope, provider/format, allowance and use issues.
Labels may overlap. Incomplete/error attempt files cannot earn acceptance credit.
Legacy first autonomous use and complete chains are unmeasured, not zero. Token
enforcement charges remain distinct from measured usage. No historical primary
verdict is edited by either tool.
