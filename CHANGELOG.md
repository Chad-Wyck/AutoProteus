# Release notes

Versions use `major.minor.patch`. Before launch, `0.x.0` introduces features and
`0.x.y` contains bug fixes. Components can exceed 9 or 99. Historical `0.0.x`
release and experiment labels remain unchanged.

## 0.6.0

- Use one shared seed prompt and normalized action interface. Move native and
  JSON response instructions into the protected controller; render both from
  the same guest-supplied tool catalog, including newly activated capabilities.
- Budget the effective model request after adding format instructions. Preserve
  human messages and the newest observation while dropping only old matched
  exchanges when needed; record adjustments in either mode.
- Qualify result retrieval with an exact structured receipt argument, followed
  by explicit completion with a free-form message. Keep three rounds, rejected
  call recovery, bounded repairs and strict rejection of incorrect receipts.
  Invalidate receipts from the previous qualification procedure.
- Add `--text-file ARGUMENT FILE` to guest development invocation, allowing raw
  source fragments without embedding them in argument JSON. Preserve workspace
  validation, text limits and existing tool execution; reject duplicate names.
- Keep independent outcome checks and activation requirements. Add regression
  and VM coverage; live model comparisons have not been run on this revision.

## 0.5.1

- Remove an obsolete prompt-wording assertion from the protected starter tests.
  Preserve stable opening instructions, action limits and free completion;
  check the two-request finish and actual saved output instead of prose.
- Allow cancellation of unacknowledged message offers once their host worker
  has stopped. Serialize with Resume, retain active-delivery protection and
  refuse cancellation of messages already acknowledged in saved history.
- Show cancellation and unconfirmed delivery accurately after interruption,
  including when worker liveness changes without a new session revision.
- Specify a paired v0.4.0/current-seed comparison for final CSV-task accuracy.
  Keep model training and adapter results separate from seed qualification.
  Regression coverage is added; test execution and model trials remain deferred.

## 0.5.0

- Add focused `seed.py check --test tests/test_NAME.py` repair checks, labelled
  separately from the full suite. Empty or entirely skipped selections fail;
  focused passes cannot clear recorded full-suite failures or invoke a tool.
- Shorten the shared model guidance and consolidate the upgrade recipe around
  contract-based tests, activation, actual final outputs and explicit completion.
  Include examples for valid rejection fixtures and executable final checks.
- Keep staged final-input delivery opt-in. No model-performance improvement is
  claimed for this revision; new regression coverage and live trials are pending.
- Separate protected artifact storage and worker transport from VM orchestration
  and the model broker. Preserve transfer limits, message framing, VM policy and
  existing imports for saved study drivers.
- Read the starter once per file-import batch and name the existing checkpoint
  quota calculations. Cover exact limits, saved harnesses and legacy imports.
- Include the extracted host modules in research-runner fingerprints. Prepare
  fresh study plans after this refactor; historical results remain unchanged.
- Index evaluation guides, runners and recorded findings. Read the interface
  version from the controller without displaying a stale fallback release.

## 0.4.0

- Allow live direction changes between actions and queued follow-ups after model
  completion. Persist pending, delivery-in-progress, delivered and cancelled
  states; keep existing action and host request limits across queued work.
- Preserve all human corrections under context pressure. Reject an irreducible
  request explicitly rather than silently dropping earlier instructions.
- Save protected, content-addressed inference evidence: effective instructions,
  tool declarations, actual provider messages/responses, usage and context
  omissions. Session journal downloads include these blobs; known provider keys
  are redacted and a storage-cap failure is explicitly recorded.
- Record guest-reported operation starts, results, committed checkpoints and
  saved results separately. Resume explains uncertain outcomes; no operation is
  automatically replayed. These receipts do not replace independent checks.
- Repair missing native tool-result envelopes with explicit unknown-outcome
  errors, match results by tool name and discard foreign reasoning metadata.
- Add an opt-in final-contract handoff comparison, repeating only the public
  final requirements after activation under the existing shared budgets.
  Edit feedback, syntax feedback and context treatments remain opt-in. No live
  model benefit has been established for these additions.

## 0.3.0

- Add public, source-bound file-tool submission tickets and an optional repair
  control. Share the evaluator's existing scope policy; syntax and recorded
  development failures remain distinct from hypotheses and independent grading.
- Clarify separate focused test files, Workspace.execute, scratch files outside
  the source bundle, and explicit completion after verified final outputs.
- Prepare separate opt-in submission-feedback, edit-context and verified-lesson
  comparisons. Repairs share existing budgets; hidden grading feedback remains
  private. Static context packets are bounded, source-hashed and refreshable;
  the curated lesson records evidence, hypotheses and unmeasured benefit.
- Qualify repeated tool exchanges and rejected-call recovery with the actual
  connection protocol and catalog. Bind receipts to available inference identity
  and settings; incomplete identities cannot reuse a saved receipt.
- Give connection qualification the agent's two bounded response-format repair
  attempts per decision, within the same overall deadline. Report first-pass
  versus repaired success; wrong valid actions and connection errors still fail.
- Validate the existing staged-input comparison's delivery and activation path
  while keeping the editable seed frozen for the next live comparison.
- Extend the existing verification display with source-bound declaration,
  activation and observed-use information, keeping scripted checks separate.

## 0.2.1

- Give protected history-retention fixtures fixed observation headroom above
  the actual prompt and advertised catalog, so legitimate tool additions do
  not invalidate their assumed context capacity. Assert the resulting input
  stays bounded and retains the original request.
- Add controls for enlarged catalogs, unbounded message output and refusal
  when tool instructions cannot fit alongside human input. Default inference
  settings, context policy and isolation boundaries remain unchanged.
- Preserve original model verdicts; any regrading and seed comparisons use
  new frozen evidence directories and the same corrected protected fixtures.

## 0.2.0

- Separate `seed.py invoke` from the development test suite. Support workspace
  JSON argument files to reduce shell quoting, and preserve `check --tool`.
- Split prompts, context construction and file-edit mechanics into small seed
  modules while preserving Workspace and the two-file capability recipe.
- Separate frozen study preparation/calibration from trial execution/reporting.
  Include the new runner module in trusted fingerprints and cache identities.
- Add an opt-in supplied-parent growth comparison that withholds final inputs
  until independent verification and activation. Keep its verdicts distinct
  from the existing strict visible-input preservation baseline.
- Keep edit previews, syntax feedback and context variants opt in. Live 9B
  qualification remains deferred; these changes establish no model success rate.

## 0.1.0

- Add optional workflow experiments for edit feedback, syntax feedback, older
  observations and focused development/use stages, with frozen plans and
  independent grading. Keep these treatments outside the default seed.
- Strengthen grader fault controls and provide practical offline task fixtures.
  Distinguish model-reported completion from scoped host checks in the interface.
- Fit native tool history against the actual provider representation while
  retaining human instructions, the newest exchange and host resource limits.
- Recover human provenance at the broker before translating tool results;
  literal `ACTION RESULT` requests survive pruning, Resume and activation.
- Key input calibration by its exact existing/absent capability requirements.
  Enforce a shared deadline through development, grading, retention and use;
  report shutdown overrun and cleanup separately.
- Preserve the six-model exploratory findings. New Qwen/OxCoder comparisons are
  prepared and validated without starting live-model trials.
