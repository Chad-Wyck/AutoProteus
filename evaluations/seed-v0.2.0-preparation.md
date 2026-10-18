# v0.2.0: easier development and smaller source files

This local revision separates tool invocation from testing and reorganizes the
editable source. It retains the protected controller, Workspace interface,
two-file extension recipe, action accounting and independent acceptance rules.
Qwen/OxCoder live 9B trials are deferred. These changes establish no improvement
in model success rate.

## Development without a passing suite

`python3 harness/seed.py invoke --tool NAME --arguments-file arguments.json`
loads a bounded UTF-8 JSON object from the workspace and calls a registered file
tool in the edited copy. It works while development tests are failing. Inline
`--arguments` remains available; the two options are mutually exclusive. Paths
are validated by Workspace, including argument-file paths. Terminal permission
is still required to launch commands; the invoker does not enable `run_command`.

Inspect the resulting file against a simple exact example, then run
`python3 harness/seed.py check` separately and repair concrete failures. The old
`check --tool ...` behavior is retained: tests must pass before invocation. None
of these commands grants independent approval. Invocation evidence is recorded
separately from direct native tool calls.

## Source organization

- `tools.py` retains Workspace, shared text helpers and the capability dispatch.
- `file_ops.py` contains existing section reads and exact-edit mechanics.
- `protocol.py` contains prompts and parsing, retaining “You are AutoProteus,”.
- `context.py` constructs the bounded provider view; full journals stay saved.
- `agent.py` retains orchestration; `storage.py` owns snapshots and persistence.

Existing parser imports through `agent.py` remain compatible. New capabilities
still need one implementation and one TOOL_SPECS entry. No extension framework,
skill archive or automatic reflection loop is introduced. Existing edit-preview,
syntax-feedback, masking, retrieval and usage-accounting experiments have been
updated to the new source layout and remain opt in.

Study input preparation/calibration now lives in `model_plan.py`, separate from
trial execution/reporting in `model_study.py`. Exact requirements still determine
calibration cache keys. Every new runner file is included in the trusted inventory;
shared grading deadlines and host limits remain unchanged.

## Deferred comparisons

The [workflow guide](workflow-experiments.md) describes the new `staged-inputs`
comparison. It withholds final input bytes until independent checks pass and the
controller activates the candidate. The ordinary strict baseline still provides
visible final inputs and requires preservation. These are different input
protocols; results must retain that distinction.

Fresh local plans are saved under `.data/v020-workflow-prepared-20261018/`.
Run one balanced comparison at a time when live testing is requested. Historical
supplied model-written parents retain their original source; comparisons using
them test workflow changes, not the new starter's source organization. Separate
first-pass feedback/navigation plans freeze the current starter. Candidate code
is never imported on the host. Scripted validation uses disposable VMs and no
language model. See the [validation receipt](seed-v0.2.0-validation.json) for the
tested scope and final fingerprints.
