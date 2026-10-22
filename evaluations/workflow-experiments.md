# v0.0.16: optional interaction and completion experiments

v0.4.0 also adds `--experiment final-contract` with `--parent-source` and
`--parent-tool`. Both arms use the same independently checked supplied parent,
visible inputs and public growth instructions. Only the treatment repeats the
verbatim final-task paragraph after activation, including default arguments and
required artifacts. It does not supply hidden answers or change the source.
Actions, generated tokens and the deadline remain shared across development,
verification, activation and final use. Reuse-only tasks are excluded. Report
verified feature behavior separately from completed final workflows.

Live steering, protected inference history and recovery receipts are application
changes; their benefit for small models remains unmeasured. No studies were
started for this release. Existing frozen plans have stale fingerprints: prepare
fresh plans before testing. Edit and syntax feedback remain opt-in treatments.

For current preparation and the source refactor, see
[v0.3.0](seed-v0.3.0-preparation.md). Earlier plan receipts are historical; prepare
fresh plans against the current controller before live inference.

These experiments are prepared for later testing. No live-model benefit is
established. The default seed's editing and context behavior stays unchanged;
each source treatment is a copied seed. Isolation, credentials, approval and
independent acceptance remain controller responsibilities. No training or
additional model installation is required.

The local [validation receipt](seed-v0.0.16-validation.json) records regression
and real-VM checks, all eight fault controls, and calibration of six frozen
plans. These are preparation checks; no live model trials were started.

Run one comparison at a time. First run the existing
[navigation comparison](navigation-study.md) using a newly prepared directory.
Then compare one treatment below using the same model, settings and contracts.
Use another model and unfamiliar task families before changing the default.

## Paired edit and context treatments

Use the local model profile format in [the runner guide](model-study.md):

```text
python evaluations/model_study.py prepare --profiles profiles.json --output .data/edit-feedback-study --mode full --repeats 3 --experiment edit-feedback
python evaluations/model_study.py run --input .data/edit-feedback-study --check-only
python evaluations/model_study.py run --input .data/edit-feedback-study
```

Replace `edit-feedback` with one of:

| Treatment | Only changed behavior |
| --- | --- |
| `edit-feedback` | Successful exact `edit_file` returns at most 1,000 characters around the changed span, character positions, line number and an explicit truncation flag. The receipt and exact-match restrictions remain. |
| `syntax-feedback` | Successful `edit_file` on `.py` adds a bounded Python syntax diagnostic. It parses inside the guest without importing or executing the edited program. Invalid intermediate syntax is saved and reported; no automatic rollback or full test suite. |
| `masked-history` | Bulky old tool result bodies are replaced with explicit omission envelopes. Retain recent exact results, actions, recorded outcomes and human instructions. The full journal remains on disk. Existing context trimming still supplies the final bound. |
| `submission-feedback` | Up to two bounded public repair tickets before hidden grading; shared action/token/wall allowances, no automatic repairs or approval. |
| `edit-context` | A directly supplied, source-hashed static context packet and an optional guest refresh/check script. |
| `verified-lesson` | One opt-in curated lesson file with evidence and explicit uncertainty, alongside the ordinary fixed recipe. |

Masking defaults to eight recent observations and a 512-character threshold;
these are experimental settings, not supported optimal values. Configure with
`--mask-keep N --mask-threshold N`. Test missing-result recovery and repeated
reads. The helper does not add journal search; the separate history experiment
tests retrieval. Older action arguments can still be large. Measure real prompt
processing, generation and total time: changing older messages can invalidate
prompt-cache reuse. Do not estimate cache hits from input-token totals.

Each pair shares a frozen model profile, baseline, contracts and budgets. Arm
order alternates by feature/repeat. Three features times three repeats times two
arms is **18 first-upgrade attempts**, with up to 18 additional growth attempts
if every first upgrade qualifies. At 30 minutes each, task ceilings can reach
18 hours before grading/basic checks; these are maxima, not expected duration.
Use `--repeats 1` for a pilot, label it exploratory, and complete a balanced
comparison rather than launching all treatments together.

Both first upgrades must independently qualify before their own descendants
run. These descendants have different model-written parents; their results do
not isolate a continuation-context effect. Use the exact-parent study below
for that question. Paired growth stages share one action, generated-token and
wall allowance; independent grading consumes the remaining wall allowance.
Every grading worker receives that same absolute deadline. Expired checks are
recorded as not run. Worker shutdown and evidence-saving delays after expiry,
plus final cleanup time, are reported separately; they do not authorize another
check or activation.
Ordinary app Resume behavior is unchanged.

## Focused completion with one exact supplied parent

Export a candidate-source JSON bundle; never import candidate code on the host.
The runner independently checks the parent's regressions, named feature and
public invocation before either arm runs. A supplied parent earns no autonomous
first-upgrade credit. Its source, task, fixtures and inference profile are frozen
and identical for both arms.

```text
python evaluations/model_study.py prepare --profiles profiles.json --output .data/phase-growth --mode full --repeats 3 --experiment phases --parent-source candidate-source.json --parent-tool format_json
python evaluations/model_study.py run --input .data/phase-growth
```

The baseline receives the existing staged growth task. The treatment appends a
development/check/submission objective and a focused final-use instruction after
independent verification. Original requirements and complete journals survive.
The controller freezes and checks submitted code; a ready message never approves
it. Both arms use concise activation already present in the project. Neither
receives extra time, output tokens or actions for switching stages.

Reports separately record submission, requested activation, verified source,
actual activation, retained capability, exact final artifacts, tool-use route
and explicit completion. Failed checks or exhausted budgets prevent activation.
Incomplete workflows keep their verdicts even when their code is functional.

First isolate use of an unchanged, already verified cumulative seed with
`--reuse-task task.json`. Example task shape:

```json
{
  "name": "format-and-audit",
  "task": "Use format_json on input.json, inspect its exact contents, and finish. Do not edit the seed.",
  "required_tools": ["format_json"],
  "fixtures": {"input.json": "{\"z\":1,\"a\":2}"},
  "checks": [{"path": "input.json", "equals": "{\n  \"a\": 2,\n  \"z\": 1\n}\n"}]
}
```

Every required known tool receives independent input calibration. Reuse requires
correct checked outputs, unchanged seed bytes and observed use of the required
tools. It is reported separately and never counted as an added capability.
Then run the fresh second-extension comparison without `--reuse-task`.

## Verification and practical tasks

### Optional withheld final inputs

Select `--experiment staged-inputs --parent-source candidate-source.json
--parent-tool sha256_file` (or `format_json`) to compare the strict visible-input
baseline with a different input-delivery protocol. Both arms use the same exact
independently checked supplied parent and shared budgets. Three repeats produce
six second-extension attempts; supplied parents earn no first-upgrade credit.

The treatment supplies a disposable `development/example.json`; final
`inventory.json` bytes stay outside the guest. After implementation, regression,
feature, public-call and retention checks pass, the controller checks that no
final input or audit has been submitted prematurely. It copies the final input
through the existing artifact boundary and activates the checked source in a
fresh VM. Exact final bytes, receipt, explicit completion and actual use of both
capabilities are still required. Failed checks or exhausted allowances prevent
delivery and activation. No runtime permissions change.

This measures whether separating development from final use helps completion.
It includes input-delivery instructions and does **not** demonstrate compliance
with preserving a visible input. Reports label the two input protocols separately;
do not pool them as the same strict success rate. CSV parents and reuse-only
tasks are rejected for this experiment. The phase, navigation and feedback studies
remain separate comparisons. Do not launch all of them as one testing batch.

The main grader calibration now includes an explicit fault matrix: omitted
defaults, required optional schema arguments, booleans accepted as integers,
Unicode byte/character confusion, exact-limit rejection, false write-success
receipts and destructive rejected writes. Each faulty bundle must fail named
contract cases while its existing regression suite still passes. Broken imports
or unrelated failures cannot satisfy these controls. Existing traversal,
escaping-link and one-extra-row controls remain. All execute only in guests.

The optional [offline task pack](offline-tasks.json) covers multi-file totals,
source-preserving corrections and interruption/recovery. Select it with
`--task-pack evaluations/offline-tasks.json`; it replaces the ordinary task pack
for that frozen plan. Results describe these local tasks, not an external
benchmark or generalization to unseen tasks. Preserve a separate unseen task
set for qualification. Temporary guest programs remain available through
explicit terminal permission; the existing `programs` experiment compares a
supplied inspection helper. No new plugin or persistence framework is added.

Queue summaries retain every launch and explicit retry. Paired cost comparisons
use original attempts accepted on both sides, with per-metric completeness.
Failed/interrupted costs remain in totals; unknown measurements are not zero.
Reuse, supplied-parent growth and autonomous first/second growth are different
evidence. Prepare new plans after runner/grader changes; old evidence is never
rewritten.

The app now labels model-reported completion separately from host seed checks
beside saved files. Checks cover the listed tasks and frozen source. Changed
source is marked stale; native checks are labelled unprotected. An ordinary saved
file is not certified merely because a seed comparison passed.
