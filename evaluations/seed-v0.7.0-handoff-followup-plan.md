# Focused follow-up to the unsuccessful persistent-plan experiment

The completed initial comparison verified and activated all six candidates but
completed no correct workflows. All three revised attempts repeatedly performed
the earlier two-row preview until their wall deadline. They wrote stale full-task
plans and did not prepare their early final-output verifiers.

Use the same Qwen 9B Q6 profile, original tasks, fixtures and independent graders.
Compare three paired repeats of two conditions, alternating order:

- **handoff-once**: the revised seed shows its model-written plan at activation,
  then stops appending that stale plan after every new assistant action. Files
  remain available and every original human requirement/correction is retained.
  A newly activated version can receive a fresh one-time handoff.
- **focused-final**: exactly the same source, with the existing public
  `final_task` supplied as the current user request after activation using the
  evaluator's existing final-contract treatment. This repeats a clause already
  present in the original task, unchanged; it supplies no hidden answer or
  numeric limit from the grader. Score this structured-task condition separately.

The initial persistent-plan batch is historical evidence; it is not a fresh
paired control here. Showing notes once versus persistent notes is therefore
an exploratory cross-batch comparison. The fresh paired comparison isolates
the additional public final-task message with identical source on both sides.

Before inference, both parents must pass all common protected tests and parent
feature checks. A scripted real-VM probe must show notes on the first activation
request, omit them after a new assistant action, retain human text, ignore a
human message imitating an activation marker, and show notes for a genuinely new
activation. The probe is infrastructure validation, not model success.

Keep 128 shared actions, 65536 generated tokens and 1800 seconds per attempt,
with a four-hour batch bound and at most eight hours across tonight's family of
experiments. Count every launch; do not repair candidates, silently retry or
relax final artifact grading. The disk-reserve override remains in effect.
All model-written code executes only in disposable, network-free VMs.

If handoff-once achieves 3/3 correct artifacts and workflows, consider adopting
the small context correction after regression checks. If only focused-final
succeeds, report the supplied task-structure dependency rather than claiming
default autonomous reliability. Otherwise assess the recorded failure before
spending resources on another change. Do not add navigation tools or more
reminders merely because they were earlier suggestions.
