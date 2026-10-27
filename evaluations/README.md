# Evaluations and research

This directory contains optional experiment runners, independent graders,
research notes and recorded findings. These tools run outside the editable seed.
Normal application setup does not require them.

Latest: [first-use, growth and optional-planning findings](seed-v0.14.0-activation-use-2026-10-26-findings.md), including separately preserved raw and reassessed use scores.

Next: [portable repeatability and outcome-choice studies](next-studies.md), prepared for faster hardware without changing the default seed workflow.

## Running a study

| Guide | Purpose |
| --- | --- |
| [Test your own model](local-model-test-handoff.md) | Copyable Windows/Linux instructions for first and second extensions on the current starter. |
| [Activation/use protocol and reports](activation-use-study.md) | First-use scoring, diagnostic growth, an opt-in navigation pilot and closed-trace reports. |
| [Model studies](model-study.md) | Prepare a frozen model comparison, screen first upgrades, then test growth from accepted parents. |
| [Workflow experiments](workflow-experiments.md) | Compare opt-in edit feedback, context handling and completion support. |
| [Navigation comparison](navigation-study.md) | Measure whether source navigation reduces repeated inspection. |
| [Experience experiments](experience-study.md) | Compare supplied procedures, history retrieval and inspection programs. |
| [Growth studies](growth-study.md) | Compare extension and later use while preserving earlier capabilities. |
| [Capability discovery](discovery-study.md) | Let the model choose an interface for a fixed outcome, with a public handoff preflight. |
| [Final-task completion](completion-study.md) | Separately compare requirement restatement or shorter guidance on unfamiliar defaults and scopes. |

Use a new private output folder under `.data/` for each frozen study. Reuse or
resume a plan only while its source, trusted runner and model identities match.
After a controller refactor, prepare a new plan instead of changing old records.
Study preparation and ordinary regression tests do not start live-model trials.

Research plans explicitly enable action limits, regardless of the normal app's
optional allowance. Frozen plans record action, shared wall-time and generated-
token budgets. Changing application preferences does not extend an experiment.
Regenerate plans after runner or grader changes; never rewrite historical scores.

## Code map

| Files | Responsibility |
| --- | --- |
| `model_plan.py` | Preparation, fingerprints and scripted input calibration. |
| `model_study.py` | Trial execution, checking, activation and reporting. |
| `generalization.py`, `*-probe.py`, `grader_faults.py` | Public contracts, independent checks and deliberately faulty controls. |
| `study_support.py` | Persistent queues, exact-identity caches and phase timing. |
| `run_budget.py`, `usage_budget.py`, `observations.py` | Resource allowances, token accounting and measurement coverage. |
| `workflow_variants.py`, `workflow_support.py` | Explicitly selected experimental treatments. |
| `controller/artifacts.py`, `controller/transport.py`, `controller/isolation.py` | Protected host storage, bounded worker messages, VM policy and broker. |

Run code written by a model only inside the configured disposable environment.
Host graders inspect candidate source as data and execute it through the worker.
See [the security boundary](../SECURITY.md).

## Recorded results

[Published regression and VM validation](../VALIDATION.md) includes exact
revision identities, pass/skip counts, original logs and checksums.

Useful starting points among the published reports:

- [Qwen 9B staged final inputs](seed-v0.3.0-staged-input-findings.md).
- [OxCoder submission-feedback comparison](seed-v0.3.0-feedback-findings.md).
- [Controlled seed comparison](seed-v0.2.1-seed-comparison.md).
- [Earlier multi-model screening](seed-v0.0.16-local-findings.md).
- [Bonsai extension and later reuse](seed-v0.0.15-bonsai-findings.md).

Reports distinguish tool behavior, verified upgrade packages, activation,
correct saved outputs and complete workflows. A model's completion claim alone
does not establish success. Measure efficiency among matched successful tasks;
keep failed attempts and partial usage measurements visible.

Training loss, successful export and ordinary-task checks do not qualify an
adapter for seed extension. Report base and adapter workflows separately, with
the exact seed, model, quantization and settings. Keep an adapter experimental
until its benefit repeats on complete tasks and unfamiliar capabilities.
The next [final-task comparison](seed-v0.5.1-final-task-plan.md) uses the base
model alone so seed changes can be evaluated without changing the adapter.

Historical filenames stay in place so existing links and evidence remain
usable. Earlier version labels follow an older numbering scheme: use report
dates and source fingerprints rather than filename sorting to establish order.
Local unpublished notes may also be present; this index links published records.

## Research notes

- [Multi-harness training](multi-harness-rl-research-2026-10-15.md).
- [Reusable procedures and history retrieval](hermes-agent-research-2026-10-15.md).
- [Inference engines](inference-engines-video-research-2026-10-17.md).
- [Context, verification and workflow proposals](project-research-review-2026-10-17.md).
- [Harness research round](research-round-2026-10-19.md).

Research proposals and prepared treatments remain experimental until measured
on a frozen seed with independently checked outcomes.
