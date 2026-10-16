# v0.0.12: preparation and evaluation corrections

This release prepares opt-in Qwen3.5 9B comparisons and corrects their graders
and cost accounting. It does not establish improved model performance. No live
model trial was started during this preparation. Experiment helpers remain
outside the ordinary editable seed; the seed's release version advances to
0.0.12 and its existing behavior is preserved. Saved model preferences and VM
permissions are unchanged.

The navigation comparison, reusable procedure, current-task history retrieval,
usage-anchor policy and guest inspection helper have separate frozen plans.
Navigation alone is recommended for the first testing window: 18 balanced
attempts, up to 4.5 hours of task ceilings at the default limit, plus calibration
and independent grading. The menu exposes the other studies individually and
has no shortcut that chains multiple studies.

The JSON-key probe now checks valid multibyte JSON at exactly 100,000 characters
and immediately above that limit. It verifies input-byte preservation in both
cases. A deliberately byte-limited implementation is a separate negative
control: it must fail the valid character-boundary case. The correct reference
must pass both cases, while an absent tool remains another negative control.
These references execute only inside disposable VMs and are not supplied to
model trials.

Call traces have separate input-token, output-token, call-timing and transport-
timing coverage. Call IDs associate usage with sent inference requests; duplicate,
missing or invalid measurements cannot establish complete costs. Known sums are
retained with complete/partial/unavailable labels. Requests rejected locally
before transport have zero inference token cost; sent requests without usage
have unknown token cost. Host task/trial wall time remains a separate measure.
Matched successful attempts remain visible even when cost data is incomplete,
but each efficiency metric requires complete measurements on both sides.

The Linux CI failure was an appliance-test prerequisite: it attempted to locate
installed QEMU before testing a deliberately corrupted mocked download. The
fixture now supplies that prerequisite and exercises both platform branches,
asserting that corrupt bytes never reach installation or image construction.
Production installation checks are unchanged. SECURITY.md now documents the
host ceiling of `(min(actions, 200) + 1) * 3`, at most 603 model requests.

See [validation](seed-v0.0.12-validation.json) for platform results, source and
grader fingerprints, and calibration verdicts. Full local logs and prepared
plans remain in private `.data/` directories. Prepared inputs must be regenerated
after relevant source, runner, grader or configuration changes.

The procedure tasks cover related text-helper extensions. Future positive
results would establish assistance on those contracts. Retrieval and inspection
programs measure recovery and artifact-task efficiency separately. Promotion
requires further unseen capabilities and accounting for reading, context,
runtime and maintenance costs. Automatic skill extraction, a broader library,
finishing behavior, activation handoffs and eventual training remain separate
research questions recorded in the experiment documentation.
