# v0.14.1: fixed growth and outcome-only local studies

Qwen3.5 9B Q6_K produced **one independently verified first package in six
attempts**. Its diagnostic second extension passed verification and correctly
used both capabilities, but the parent bypassed its new tool during first use,
so **no complete growth chain passed**. Separate outcome-only tasks passed
**3/4 first tasks and 2/4 fresh follow-ups**, without any seed extension.

The strongest new observation is repeated unchanged editing: the second and
third CSV attempts made **59 and 65 calls respectively with identical old and
new text**. These are observed calls, not an established explanation for every
failure or evidence that a proposed remedy works.

## Frozen conditions

- Git: `c2c7d13501b165130bcc13994ba0be0344cb58a1`, v0.14.1.
- Starter SHA-256:
  `ebbbddc665b4f5eadfb9beb6bc47b3bd99bfaf3aa414b7f20980a00c212469de`.
- Qwen3.5 9B Q6_K weights SHA-256:
  `073a9275e65d9c8cd2819cf5f77b99fbaa6e87ba591da6bbaa86ec073a64bfef`.
- Windows/WHPX guest execution; GTX 1080 Ti, 11 GiB. Model-written code ran
  only in disposable guests. Closed-export auditing treated candidate files as data.
- Pinned Prism llama-server/DLL assets; native protocol through the standard
  controller adapter, 131072 context, 4096 response tokens, temperature .6,
  thinking off, top-p .8, top-k 20, min-p 0, repeat penalty 1,
  Q8_0 K/V cache, batch 256, microbatch 128, one slot, automatic GPU offload.
- Each edit/use task shared 128 actions, 3600 seconds and 65536 generated-token
  enforcement units across development, checking and activation/use. A second
  extension received a fresh task allowance. Runtime loading was separate and recorded.
- Fresh inference server per attempt. Fixed repeats requested sampling seeds
  104729, 130363 and 155921 on **every model call**; outcome tasks used 104729.
  Matching initial server seeds and actual seeded request payloads were checked.
  This differs from earlier experiments that initialized a server RNG once per
  attempt; it is not a matched seed-version regression comparison. Seed control
  does not establish determinism.
- No operator repairs, coaching, selective retries, mid-study source changes or
  promotion into the application. All recorded attempts were retained.

The standalone production-connection qualification passed first try: eight
requests, no format repairs. Its automatic identity receipt was incomplete and
not reusable; engine and weights were instead pinned and observed by the private
runner. This does not turn that receipt into portable hardware qualification.
Scripted calibration and all five ordinary tasks passed before upgrade trials.
Internet was disabled for these offline tasks. This research profile does not
qualify the application's smaller fresh-default model/configuration.

## Fixed growth: activation-use-v2

Same task wording and input bytes across repeats; fresh workspaces and
predeclared request seeds. Both first-use and cumulative second-use requirements
were fixed before inference.

| Seed | First extension | First package | First use | Second extension/use |
| --- | --- | --- | --- | --- |
| 104729 | format_json | Rejected: changed protected `file_ops.py` | Ineligible | Ineligible |
| 104729 | csv_preview | Rejected: Unicode limit and omitted default | Ineligible | Ineligible |
| 130363 | csv_preview | Not accepted: 128 actions, candidate tests not passing | Ineligible | Ineligible |
| 130363 | format_json | Accepted | Correct files, new tool not used | Hashing verified; both tools used correctly; diagnostic only |
| 155921 | format_json | Not accepted: one-hour deadline, 125 actions | Ineligible | Ineligible |
| 155921 | csv_preview | Not accepted: one-hour deadline, 94 actions | Ineligible | Ineligible |

Totals: first packages **1/6** (formatting 1/3; CSV 0/3), correct first use
**0/1**, second verification **1/1**, correct cumulative second use **1/1**,
complete chains **0/6 scheduled**. Five second attempts were ineligible, not
five tested second-extension failures. The one second attempt was diagnostic
because its parent failed first use. Native-only routing was not required for
functional second-use credit; its strict-route score remained false.

The accepted formatter was advertised in 28 recorded inference requests, but
the model made no native formatter call. First-use observations contain only
list/read/write operations and no recognized development invocation. It saved
the correct formatted input and receipt, inspected them and completed. Correct
artifacts therefore did not establish use of the extension.

The first CSV candidate rejected valid exact-limit multibyte input as exceeding
100000 bytes and rejected an omitted `limit`. Its own suite passed. The scope
failure in the first formatter is separate from semantic correctness: feature
qualification was withheld under the published two-file submission contract.

The two later CSV attempts repeatedly submitted identical replacement text.
The tool returned successful replacement receipts for unchanged files. The
second attempt made 59 unchanged edits among 69 edit calls; the third made 65
among 76. The third formatter instead spent time repairing test expectations
around formatted-output expansion. Checks not launched after a deadline are
unmeasured; failure labels in the mechanical report should not be read as proof
of failing protected regressions when those checks were skipped for lack of time.

## Outcome-only choice: outcome-choice-v1

These tasks prescribe results, not tool names or source edits. Every task is
starter-solvable. Later tasks use different paths and bytes in fresh sessions;
only checked seed capabilities could carry over, not old scratch files/history.

| Task pair | First | Later | Exact failed output difference |
| --- | --- | --- | --- |
| Exact copy | Pass | Pass | None |
| JSON settings copy | Pass | Pass | None |
| Multi-file CSV index | Fail | Fail | Embedded quoted-field CRLF became LF |
| JSONL summaries/problems | Pass | Fail | `records` contained arrays instead of integer counts |

Thus **5/8 task outcomes and 2/4 two-task pairs passed**. All eight preserved
every input, explicitly completed and remained within allowance. The CSV
outputs otherwise matched the expected structure/counts; the strict score still
fails because parsed field content changed. The later JSONL problem report was
correct; the two summary `records` fields had the wrong type/value.

No seed edits, checked new packages, new registered tools or temporary Python
helpers were observed in any of these eight tasks. These results establish
neither autonomous extension discovery nor later extension reuse. They also do
not establish that extending was necessary or desirable for these goals.

## Cost, interpretation and next experiment

About **4 hours 9 minutes** elapsed from connection qualification to cleanup,
including loading and calibration. Closed-attempt totals below exclude the
standalone eight-request connection qualification and include each study's
inference benchmark; fixed growth also includes the five ordinary tasks.

| Study | Calls | Actions | Known output tokens | Usage coverage | Sum of attempt seconds |
| --- | ---: | ---: | ---: | --- | ---: |
| Fixed growth | 626 | 611 | 168507 | Partial: 624/626 calls | 14034.348 |
| Outcome choice | 84 | 74 | 10097 | Complete: 84/84 calls | 584.945 |

The two deadline-interrupted calls lack complete usage. Their conservative
budget charges are not measured generation. Provider-reported weighted decode
rates were approximately 19.3 tokens/s for fixed growth and 21.9 for outcomes,
over measured responses only; these are not end-to-end task rates or a controlled
speed comparison between workloads.

Keep this baseline frozen. A focused next comparison could return an explicit
unchanged-edit result when old and new text are identical. Measure escaping the
loop and accepted outcomes under the same limits; do not assume success or add
a general reflection framework. Keep exact artifact errors, scope compliance,
actual new-tool use and task completion as separate observations. No application
changes were made in this testing turn.

## Evidence and reproduction

Local evidence root: `.data/qwen-v0141-night-20261027/`.

- `profiles.json`, `runtime-protocol.json`, per-attempt `runtime/engine.json`
  and `runtime/runtime-preflight.json`: requested settings and pinned assets.
- `qualification.json`, `qualification-calls.jsonl`: standalone transport check.
- `fixed-growth/`: frozen plan, case identity, calibration receipts, queue,
  sessions, provider traces and per-attempt results, including failures.
- `fixed-growth-report.md` / `.json`: read-only mechanical report.
- `outcome-choice/summary.json`, `outcome-results.json`, per-attempt exports:
  separate task/extension observations.
- `closed-audit.json`: blob-hash/length-checked exact output differences,
  identical-edit counts, seeded request transport and cost completeness.
- `cleanup.json`: owned inference server stopped. Dedicated port 47843 had no
  listener after completion; GPU returned to desktop-level residency.

Preparation and portable-case procedure:
[next-studies.md](next-studies.md). Actual profiles/plans are environment-bound;
prepare fresh ones on another host rather than altering the saved plans. The
private orchestration and closed-data audit are `.data/run-v0141-night-20261027.py`
and `.data/audit-v0141-night-20261027.py`; no model checkpoint, candidate or private
session export is committed with this report.
