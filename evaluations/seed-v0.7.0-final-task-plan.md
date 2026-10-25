# v0.7.0 task handoff and early verification comparison

Compare the frozen v0.6.0 runtime with the locally revised v0.7.0 runtime using
Qwen3.5 9B Q6_K, standard native transport, 131072 context, 4096 responses,
temperature 0.6, thinking off and no LoRA. Both arms retain the same supplied
human-reference CSV capability and the same portable 50-case protected suite.
The v0.7.0 activation-note behavior is additionally covered by ordinary and
real-VM regression checks before inference.

Run three paired repeats of the unchanged task fixtures from the completed
v0.6.0 comparison, in baseline/revised, revised/baseline, baseline/revised order.
Keep the original task text, initial two-row preview, final default-preview
requirement, inputs and independent graders unchanged. Neither a hand-written
verification script nor hidden expected outputs are supplied to the model.
The revised model must derive its task-specific plan and early assertions itself.

Each attempt shares 128 actions, 65536 generated tokens and 1800 seconds across
development, independent grading, retention, activation and final use. The batch
has a four-hour wall bound. The user's disk-reserve override remains in effect.
All model-written code runs only in disposable, network-free VMs. No candidate
repairs, silent retries or successful-attempt selection are permitted.

The primary revised-arm target is 3/3 correct final artifacts and 3/3 complete,
independently checked workflows. Report verified functionality, activation,
functional use, direct routing, output fields and explicit completion separately.
Keep raw completion-dependent acceptance flags distinct from verified code.
Report all launches and cost completeness, including infrastructure failures.

After this batch, inspect whether the model actually wrote its final-task plan
and verification script before editing and ran the latter after activation.
If the revised arm achieves 3/3, stop and report. Otherwise, select one narrowly
justified change from the saved failures: navigation, a submission reminder, or
a clearer apparent correction. Freeze new inputs and repeat a paired comparison
before adopting it. Keep each round separate. Allow at most two follow-up rounds
and eight hours overall, stopping earlier when further changes lack evidence.
Test success on these familiar tasks remains exploratory; qualification on new
capabilities is a later step.

Exact source, model, runtime, task, validation and grader identities are saved
under `.data/task-handoff-v070-20261023/`. The source changes and study results
remain local unless the user asks to commit or push them.
