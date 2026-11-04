# New independent experiment protocol

This is a prospective design. It does not authorize a run or imply its outcomes.
Register the exact manifest, budgets, cases and decision rules before inference.

## Hypothesis and arms

The primary hypothesis is that frontier-edited teacher T1 produces better student
edits than untouched teacher T0. Start every episode with a fresh copy of the same
student S0. Teachers receive identical tools and development feedback. Compare
their final artifacts S(T0) and S(T1) with S0 on sealed outcome questions. Include
a no-edit export/reload/requantization control. A norm-matched coordinate/shuffled
teacher control can test specificity; it is nonpromotable and must be selected
without behavioral outcomes. If not affordable, declare that limitation.

Teacher size, student size, precision and family are independent configuration
choices. Test 4B/0.4B or other sizes only where the chosen checkpoints exist and
have compatible qualified tooling. Historical Qwen3.5-4B/0.8B results do not
establish outcomes for those new pairings. Do not transfer tensor indices or
neuron semantics across architectures by assumption.

## Freeze before selection

Record repository commit; frontier provider/model identifier and access date;
teacher/student model IDs, exact revisions, license records and file hashes;
tokenizer/template hashes; engine commit/build/DLL hashes; conversion commands;
OS/GPU/driver; dependencies; helper schema; numeric policy; isolated execution
configuration; seeds; prompt and feedback schema; case/exposure inventory;
sampler and EOS semantics; output/context limits; case order; retry policy;
wall-time, token, forward-pass, candidate and expenditure ceilings; resource
policy; required outcomes and stop rules. Record unknown fields as unknown.

Split development, selection, confirmation, student outcome and ordinary
preservation cases. Keep complete editing episodes and checkpoint lineages in
one split. Use normalized text overlap and lineage checks to avoid leakage.
Do not present previously exposed cases as fresh. Keep final questions and golds
out of the teacher/frontier selection context. Use an independent evaluator.

## Stages and gates

1. **Engineering qualification.** Run CPU controls, actual isolated-VM positive
   and adversarial controls, tokenizer parity, native sampler controls, exact
   no-edit round trip and finite-value checks. Verify owned worker/VM cleanup.
   No model-written Python executes in the host interpreter. The supplied
   historical route requires a diskless unprivileged VM with no network or host
   mounts, and a closed-schema numeric host broker.
2. **Untouched development baseline.** Measure genuine failures with explicit
   function signatures and real shapes. Predeclare an accuracy endpoint. If
   baseline is at ceiling, stop this design; register a new harder screen later.
   Do not switch to a token endpoint after observing a tie.
3. **Frontier intervention.** Give the frontier development-only evidence and
   bounded tools. Record every candidate, rejection, rationale and its cost.
   Freeze one selected teacher before confirmation. Include frontier calls,
   failed probes and zero-sampling forwards in compute accounting.
4. **Numerical validation and preservation.** Reconstruct the patch from the
   immutable base, test exact unchanged bytes/blocks and no-edit conversion,
   measure canonical and deployed delta norms/counts, quantization spillover and
   finite/nonempty effects. Verify native fresh loading. Require a development
   gain with no loss and independently fixed confirmation/preservation criteria.
   Otherwise stop downstream spending and mark dependent work UNRUN.
5. **Matched student editing.** Use fresh contexts and fresh S0 copies, matched
   prompts/seeds/tools/feedback/caps for T0 and T1. Counterbalance arm order in a
   new study and record the order; historical fixed-order runs stay historical.
   Record checkpoint/restore operations and test receipts bound to exact candidate
   contents/settings. Freeze the final student after its last test. A final edit
   after testing invalidates coverage until retested.
6. **Independent outcomes.** Grade S0, S(T0), S(T1), and no-edit conversion on the
   same fixed sealed questions and preservation tasks. Report per-case paired
   wins/losses/ties, denominators, correctness and uncertainty across independent
   episodes/seeds. Predeclare sample size and the statistical criterion; four or
   eight familiar questions do not establish a general claim. Keep synthetic tool
   success, complete execution, submission, correctness and cost separate.

## Accounting, interruptions and claims

Use one aggregate ledger per study. Charge interrupted reservations and uncertain
tails conservatively; never reset clocks/budgets by copying an experiment folder.
Reruns or continuations need an explicit prospective rule, preserving prior
evidence. A timeout can be a completed truncated model output or an infrastructure
failure; report the actual classification and missing observations. Never replace
failed cases or count unrun outcomes as wrong answers.

Report sampled tokens, prompt tokens where available, zero-sampling forwards,
frontier usage, model-loading/conversion/VM time, wall time and monetary cost where
available. Compare token efficiency only on matched correct outcomes. Shared or
background GPU activity must be recorded; no idle-machine speed claim follows.

For a narrow success, the edited-teacher arm must improve held-out student
outcomes versus the untouched-teacher arm under the registered criterion,
preserve baseline-correct behavior and pass artifact/tool contracts. Compare with
S0 to distinguish useful editing from merely avoiding a teacher-induced regression.
Report inconsistent or negative effects. No self-edit stage follows automatically.
