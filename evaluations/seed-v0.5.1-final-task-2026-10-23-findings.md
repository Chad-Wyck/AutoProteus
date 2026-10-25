# v0.5.1 nightly preflight — 23 October 2026

**The regression and VM gates passed. The six paired seed-editing attempts did
not start because base Qwen failed production-connection qualification twice.**
There is no new upgrade or completed-workflow score, and no comparison of
v0.5.1 against v0.4.0 can be made from this run.

## Gates

| Check | Result |
| --- | --- |
| Ordinary suite | 323 tests: 277 passed, 46 skipped |
| Real disposable-VM suite | 23 passed |
| Each frozen runtime's protected starter suite | 50 passed per arm |
| Supplied CSV capability and public invocation | Both arms passed |
| Required absence of hashing | Confirmed in both arms |
| Grader calibration | Three reference features and public invocations passed; absent-feature controls, CSV truncation, formatting path bypass and all eight semantic fault controls rejected |
| Cancellation interface | Seven Node/stub checks passed, including a stopped worker with an unchanged saved revision; JavaScript syntax passed |
| Production native connection | Failed both qualification attempts |
| Scheduled extension attempts | Six not run; zero launched |

Starter, parent and grader gates were rerun before the second qualification
attempt and passed again. This does not constitute independent model evidence.
The VM gates include the corrected protected tests and interruption/recovery
checks. The interface check is not a full browser end-to-end test.

## Qualification failure

The frozen profile was base **Qwen3.5 9B Q6_K**, 131072 context tokens, 4096
response tokens, temperature 0.6, thinking off, standard production `ModelClient`
and the pinned PrismML llama.cpp runtime. Runtime inspection confirmed **no
adapters loaded**. Model and engine hashes matched the prepared assets.

Each qualification stopped in its first round after three model calls:

1. Correct `diagnostic_echo` call with the supplied random value.
2. Correct recovery from the deliberately rejected call.
3. A valid native `finish` call with `status="completed"`, but the wrong exact
   message representation.

The checker expects `message` to equal the receipt string, for example
`abc123`. Both responses instead contained the JSON text
`{"receipt":"abc123"}` as that message. The value inside the wrapper was
correct. Captured responses had no normalization error, truncation or observed
transport failure. The generic error class describes this as a protocol failure;
the saved evidence identifies the narrower exact-answer mismatch.

After the first failure, one fresh qualification was announced and performed
with unchanged settings and a restarted service. Its failure is retained beside
the first. No further retry, weaker check, candidate repair or alternate model
was used. Neither attempt completed the required three qualification rounds.
Together they used six model calls and 275 reported generated tokens; they are
diagnostics, not seed-editing trials.

## Operator and infrastructure observations

Before any inference, the private launcher initially rejected its own static
capability observation: the supplied reference parent combines tool dictionaries
using `|`, which the conservative observer reports as unmeasured. The launcher
was corrected to rely on the mandatory VM capability, public invocation and
absence checks. The frozen parent and application source were not changed.
That initial preflight failure and each exact launcher version are preserved.

The old arm remains the v0.4.0 runtime with the shared corrected protected-test
overlay, not a byte-identical v0.4.0 bundle. No model received the graders or
reference implementation. All executable feature and fault-control checks ran
inside disposable VMs. Source snapshots, tasks, host implementation and model
settings remained unchanged.

The model service and VMs were stopped, port 47841 was released, and GPU use
returned to the desktop baseline. Disk free space remained about 10.8%, above
the 10% plus 3 GiB guard. No training, merge, download, commit or push occurred.

## Next step

Clarify the host diagnostic instruction: the finish message must be exactly the
string in `result.receipt`, without an object wrapper or added text. Preserve
the random receipts, exact comparison, rejected-call recovery and three-round
requirement. Verify that narrow change before requalifying and admitting the
six frozen comparisons. This is a proposed change, not an implementation or a
claim that Qwen will pass it.

The experiment's acceptance criteria and final five-row requirement should
remain unchanged. These preflight failures do not establish whether the current
seed fixes the earlier two-row final-audit error.

## Evidence

- [Machine-readable results](seed-v0.5.1-final-task-2026-10-23-results.json)
- [Frozen plan](seed-v0.5.1-final-task-plan.md)
- Private inputs and all receipts: `.data/final-task-v051-20261022/`
- Ordinary log: `.data/v051-night-regression-tests.log`
- Real VM log: `.data/v051-night-vm-tests.log`
- First model qualification: `execution-20261023-qualified/`
- Announced fresh qualification: `execution-20261023-connection-recheck/`

Each qualification directory includes the exact launcher snapshot, execution
manifest, protected checks, grader calibration, provider traces, structured
failure receipt and shutdown record. Both durable queues contain no launched
extension attempts. Application commit: `70a98697e4facb8a120142623439874e97fc28ac`.
