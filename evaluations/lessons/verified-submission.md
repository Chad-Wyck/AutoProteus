# Focused seed submission (curated experiment, version 1)

Applicability: a directed file-tool extension has working behavior but still
needs tests, a clean source bundle, activation and a completed user task.

Procedure to try:
1. Add the implementation in Workspace.execute and its TOOL_SPECS entry.
2. Create tests/test_<capability>.py. Call Workspace(Path(directory)).execute(
   "tool_name", arguments); tool names are not additional Workspace methods.
3. Keep disposable input and argument files in development/, outside harness/.
4. Invoke the edited tool on one small example, inspect the actual output file,
   and compare its exact contents with the requested result. Test omitted defaults.
5. Run development checks. Repair the reported failure before changing unrelated
   code. Check whether the implementation or the test contradicts the contract.
6. Submit for independent verification and activation. Once activated, use the
   capabilities on the real task, verify outputs and explicitly finish completed.

Observed evidence: evaluations/seed-v0.2.1-seed-comparison-results.json and
seed-v0.2.1-seed-comparison.md, committed at e9cde9b. In the paired OxCoder Q6
study, current1 lacked a new test file; current2/current3 included scratch JSON
in the bundle. The old1 candidate activated and produced correct outputs but
did not finish. Two saved candidates completed separate fresh-use tasks after
the protected context-fixture correction. Source hashes and run references are
in those reports. Neither candidate is installed as the starter.

Hypothesis: a compact submission procedure may reduce these workflow failures.
Confidence and limits: the failures above are observed facts; this procedure's
benefit is unmeasured. These are closely related text-tool tasks. Reading or
following this file is not proof of usefulness, independent approval, or a
general self-improvement result. Do not copy an old implementation blindly.
