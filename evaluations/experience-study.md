# Opt-in experience experiments

These comparisons prepare the Hermes-inspired ideas for local testing without
adding a skills framework, conversation database, automatic summarizer or model
training infrastructure to the normal seed. The protected controller still owns
VM access, model connections, credentials, quotas and independent verification.
Candidate code and all supporting programs execute only inside disposable VMs.

## Convenient launch

Prepare with the project's private Python:

```text
.runtime/python/python.exe -X utf8 evaluations/experience-study.py prepare --output .data/experience-studies-tonight
```

Open **Start tests.cmd** in the prepared directory. Its menu starts one selected
comparison, validates with scripted VMs,
or exits. Nothing loads a
model on prepare or check-only. There is no automatic background or overnight
run. The same commands work on Linux with `python3` and an already prepared
AutoProteus runtime; the Windows launcher is a convenience wrapper.

```text
.runtime/python/python.exe -X utf8 evaluations/experience-study.py run --input .data/experience-studies-tonight --group procedure --check-only
.runtime/python/python.exe -X utf8 evaluations/experience-study.py run --input .data/experience-studies-tonight --group procedure
```

Power users can select `navigation`, `procedure`, `history`, `context`, or
`programs`. Separate result directories and comparisons prevent attributing a
combined treatment's result to one feature. All use cached Qwen3.5 9B Q4_K_M,
64K context, 4K output, temperature 0.6, thinking off and the existing VM action
and time limits. No new weights are downloaded and app preferences are unchanged.

At three repeats, navigation has 18 attempts, procedure 18, history 6, context
18 and programs 6. Running all 66 attempts can exceed one night. Navigation alone
is one option: 18 attempts, up to nine hours of task ceilings
at the new default 1,800-second limit, plus calibration and independent grading.
Each attempt also has a 65,536-generated-token allowance; both ceilings are
recorded in its frozen plan and configurable at preparation. Select one study.
The menu shows the selected plan's count and task ceiling. Procedure and the
other studies remain separate opt-in runs; there is no chained-study shortcut.
Ctrl+C stops and preserves launched attempts; reopening resumes unlaunched cells.
Failed or interrupted attempts are not silently retried.

## What changes in each comparison

| Comparison | Treatment | Primary result |
| --- | --- | --- |
| Navigation | Existing `source_outline` copied-seed variant | Accepted upgrades on the existing development contracts |
| Procedure | One bounded human-authored file, read using existing tools | Accepted upgrades on three fresh contracts |
| History | Two copied-seed tools, `history_search` and `history_read` | Exact recovery of an omitted receipt and its historical version |
| Context | Provider-usage anchors in a copied seed and trusted experimental client | Accepted upgrades, context retention and inference cost |
| Programs | One supplied Python inspection helper through existing VM commands | Independently correct inspection artifacts |

The fresh contracts are `line_count`, `json_keys` and `text_counts`. Their graders
run independently in fresh VMs, checking boundaries, Unicode, preservation on
failure, escaping paths and actual public tool invocation. Existing protected
tests and meaningful added tests are still required. Positive reference code is
used for grader calibration and is never offered to a model trial. After these
tasks are used for development, validation needs another unseen set.

The JSON grader accepts valid multibyte JSON at exactly 100,000 Unicode
characters and rejects valid JSON above that boundary without changing bytes.
Calibration includes a deliberately byte-limited implementation that must fail
the valid Unicode boundary case, alongside the absent-tool negative and correct
reference. A parser error on malformed oversized JSON cannot satisfy this check.
Both traversal and symlink checks now target existing valid external JSON.
A separate boundary-bypassing reference must fail both checks. External bytes
must remain unchanged. The formatting grader uses the same valid-fixture rule.

The procedure is ordinary task data in `experience/upgrade.md`. Its complete
reading and prompt costs count. It summarizes lessons from checked v0.0.11 work
and can be ignored by the model. This measures help from a fixed recipe; it does
not establish autonomous learning or justify automatic procedure extraction.
The updated treatment supplies `experience/invoke_tool.py` for an early tiny
smoke test independent of the test suite. The procedure asks the model to read
the actual file back and compare exact expected contents before repairing
elaborate tests. Successful invocation alone is not feature verification.
This study measures that procedure/helper bundle; the separate growth study
supplies the same helper to both arms to isolate the procedure's contribution.

History exposes only the current task's live guest journal and a bounded inert
archive of its earlier records. The fixture first creates a real earlier tool
result with a scripted VM, removes its source file, accumulates enough history
to omit it from inference, then resumes in another VM. Both arms receive the
same archive; baseline file tools can read it. The historical source label and
passing result are scripted test data, not an actual accepted older upgrade.
The requested output must explicitly say `historical_only`. The host's full
journal stays intact. The guest archive can be changed by guest code, so it
cannot serve as protected verification evidence.

Search returns stable event IDs, provenance, source fingerprints and short
snippets; read returns exact character windows. Limits are 4 MiB scanned,
2,000 relevant records, 10 search matches and 10,000 characters per read.
Malformed or capped scans are labeled incomplete. Retrieval outputs are excluded
from later retrieval to prevent recursive journal growth. No arbitrary session
ID, host file path or new broker operation is accepted.

Usage anchors bind to the complete retained message prefix, model configuration,
system prompt and tool schemas. Added material uses the conservative estimator;
a 256-token margin is reserved. Rewinds, changed prefixes/settings/tools and
missing usage force fallback. The anchor is an estimate, not an exact tokenizer.
The host applies the same algorithm to actual converted provider messages,
independently of the editable seed. Broker byte, message, tool, request and VM
resource limits are unchanged. Ordinary ModelClient behavior remains the existing
conservative estimate; only the study's trusted `UsageClient` selects the variant.

The inspection program parses Python as data and returns a compact JSON table.
It rejects escaping paths, bounds file count/input size, never imports inspected
modules and runs only through guest commands. The baseline can write its own
equivalent program. This is an efficiency experiment, not a seed-upgrade test.

## Evidence and capability history

Each result has an opt-in host call trace, full session journal, source hashes,
independent checks and a learning record. Procedure availability and observed
file-tool loading are separate from following the procedure, which is unmeasured.
Capability creation, independent checker loading/use, task agent invocation
routes, behavior passes and full upgrade acceptance are separate fields. Shell
reads and command invocation strings are diagnostic observations, not security
proofs. Scripted preparation costs and real model task costs are distinct.

Compare inference efficiency on matched independently accepted task/repeat pairs.
Also retain all launched-attempt costs, failures, cutoffs, repairs, incomplete
captures and operator stops. Complete traces and complete cost measurements are
separate properties. Each input/output token total and call/transport timing has
its own coverage, known sum and complete/partial/unavailable label. Token coverage
counts sent inference requests; local validation failures with no wire request
have zero token cost, while a sent request missing usage has unknown cost.
Host task/trial wall time is recorded separately. Matched successful attempts
remain visible, with each cost metric marked comparable only when both sides
have complete measurements; partial sums do not establish an efficiency gain.
History/program artifact success is not reported as
an accepted seed improvement. Procedure prose cannot grant permissions or turn
model claims into trusted verification records.

The procedure tasks exercise closely related text-helper extensions. Positive
results establish assistance on these contracts, not general autonomous
self-improvement. Promotion needs further unseen capabilities and consideration
of reading, context, runtime and maintenance costs.

Prepared source, helper, runner and model identities are checked before running
and on resume. Changing a trusted file invalidates the preparation. The refreshed
navigation directory retains its original baseline/outline design but receives
the new host-runner fingerprints. Earlier standalone launchers are superseded.
No candidate is automatically activated or promoted into the normal seed.

## Retained next steps

After navigation and fixed-procedure evidence: test model-authored procedure
creation from accepted work, then useful reuse on unseen tasks. Charge extraction
costs separately and keep unsuccessful drafts. Add a small discoverable library
only if that evidence supports it. Reuse the existing hashes/checkpoints for
version history and rollback instead of creating a parallel storage system.

Also retain finishing after the last passing check, full-versus-concise activation
continuation, a reproducible supported inference profile, validation on another
model, and eventual fine-tuning/LoRA experiments before v1. These are separate
questions. Targeted retrieval precedes frequent model-written compaction; cache
reuse, extra summary calls and total time must all be measured.
