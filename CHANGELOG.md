# Release notes

Versions use `major.minor.patch`. Before launch, `0.x.0` introduces features and
`0.x.y` contains bug fixes. Components can exceed 9 or 99. Historical `0.0.x`
release and experiment labels remain unchanged.

## 0.14.1

- Let foreground work reclaim an unassigned or retained idle VM. Keep the model
  resident, avoid immediate rewarming into an occupied slot, and preserve active work.
- Freeze repeatability task wording/fixtures across repeats with predeclared,
  opt-in per-request sampling seeds and portable case identities.
- Add outcome-only tasks and fresh-session reuse observations. Correct completion
  requires no extension; package checks and arbitrary feature semantics remain separate.

- Add prospective first activation/use scoring before second-extension tasks,
  with fresh inputs, source/result checks and separately labelled diagnostics.
- Share remaining actions at every activation; new tasks receive fresh budgets.
- Add a read-only closed-study report and timeline audit, preserving legacy
  scores and explicit measurement coverage.
- Prepare one opt-in source-outline comparison; the default seed is unchanged.
- Add an opt-in optional-planning comparison and record negative/variable results.
- Recognize ordinary Python Workspace-variable use, with bounded static evidence
  and separately saved reassessments rather than overwriting original verdicts.

## 0.14.0

- Make action, wall-time and generated-token limits explicit in research plans,
  independently of the optional action allowance in normal use.
- Provide a public, optional capability-submission preflight for discovery
  experiments. Check declaration structure without executing candidate code;
  keep independent behavior checks and activation authoritative.
- Add separate frozen final-task comparisons for a concise requirement
  restatement and shorter guidance, with exact-output and stale-override controls.
  Preparation and calibration start no live-model trials.
- Offer an optional practical model check in setup and Settings: exact files,
  a follow-up correction and missing-file recovery in fresh VMs. Save results
  with the tested profile and source; leave the connection usable after failures.

## 0.13.0

- Show expandable thinking entries in tool-call order, with a live spinner and
  provider-supplied reasoning previews. Keep previews out of prompts and preserve
  disclosure state while streaming. Providers without reasoning remain usable.
- Format all tool labels consistently, including new snake_case, kebab-case and
  camelCase names, without changing tool identifiers or arguments.
- Make normal-use action allowances optional and off by default; retain explicit
  evaluation budgets and independent host time/frame/transfer safeguards.
- Prewarm a clean VM when the selected local Ollama model becomes resident;
  adopt it for the first task and retain healthy sessions between replies.
  Report shared VM-slot waits separately from startup.

## 0.12.0

- Retain a session VM between ordinary replies while its local Ollama model is
  loaded. Reuse requires matching source, configuration and checkpoint identities.
  Stop, task/input/settings changes, activation and independent checks close it.
  Retention belongs to the host; graders keep their fresh-VM lifecycle.
- Track browser tabs with authenticated heartbeats, live connections and ordered close hints.
  Release task VMs and app-used local models 5 seconds after the last tab closes,
  with a five-minute heartbeat expiry for crashes and suspended tabs. Refreshes
  and other open tabs preserve work; saved files and model weights remain.

## 0.11.0

- Check Ollama model metadata before listing a model as available or connecting;
  stale entries with missing weights move into separate diagnostics.
- Refresh discovery when setup opens or the local service address changes, with
  a manual refresh button. Discover retained GGUF models in application and
  experiment caches, excluding vocabulary files and LoRA adapters.
- Add **Use downloaded model** to register a local GGUF with the local engine
  and qualify the connection. Reuse file bytes through a hard link when possible,
  with a checked local-copy fallback. Preserve the previous connection on failure.
- Report missing model-file failures separately from unreachable services.

## 0.10.0

- Use shorter final-task guidance after activation and keep activation state
  before fresh observations. New human requests restore development guidance;
  permissions, source checks and action limits remain controller-owned.
- Show explicit optional-argument overrides against declared schema defaults.
  Extend unchanged-result hints to model-added tools without suppressing calls.
- Replace the local model suggestion field with an installed-model dropdown and
  an option to enter/download another model. Remove the two preset model cards.
- Display ordinary native-mode text replies and wait for user input. Accept
  complete textual finish calls and neutral JSON actions at the host adapter;
  reject partial calls and retain explicit completion and independent grading.
- Harden Windows launcher exit handling and use hidden console Python so real
  startup failures leave readable diagnostics. No model study is claimed here.

## 0.9.0

- Raise the protected inference envelope to 2,048 messages while preserving byte,
  context, request, action and execution limits. Report a specific message-limit
  error instead of an unexplained invalid request.
- Add read-only controller observation and a local Evidence viewer for recorded
  instructions, tools, source identities, actions and operation receipts. Original
  records and independent-check scope remain separate from model claims.
- Distinguish failed snapshot writes from committed snapshots with failed summaries
  and uncertain journal writes. Keep committed work on post-commit failures; add
  generated lifecycle schedules and concurrent observer/save regression checks.
- Backfill historical findings into the append-only searchable experiment index.
  Historical reports are indexed without regrading or inventing pooled scores.
- Prepare an outcome-first capability discovery study: the model chooses its tool
  name/interface; protected held-out checks verify the fixed stock-reconciliation
  outcome. Keep all extra machinery outside the editable seed.
- Make fresh-default profile checks explicit and separate from experimental upgrade
  profiles. Connection compatibility does not establish reliable self-extension;
  existing optional treatments remain experimental pending matched comparisons.

## 0.8.2

- Enable public Internet access by default in normal VM mode and model setup,
  including older settings without a saved preference. Preserve saved opt-outs
  and reject invalid permission values. Host/private-network restrictions stay
  unchanged; offline studies explicitly disable access in their own profiles.

## 0.8.1

- Require an explicit Internet access choice during setup or in Settings. Missing
  and invalid legacy preferences stay offline; saved choices are preserved.
- Include a small offline mocked-bridge example with each editable source copy,
  and document a separate integration check in a fresh VM.
- Prepare an opt-in shorter-guidance comparison on an unfamiliar task. Keep the
  default instructions unchanged until measured; no live-model benefit claimed.

## 0.8.0

- Enable public HTTP/HTTPS access for research, downloads and API tasks through
  a host-controlled web bridge, reusable by edited seeds without adding a NIC.
- Add a built-in `web_request` tool and an Internet access preference, enabled
  by default. Preserve workspace-only downloads and host-owned network policy.
- Block local/private/reserved destinations, non-web ports, DNS rebinding and
  redirects into private services. Retain certificate checks, Stop, per-request
  deadlines and bounded request/response budgets. Host credentials and browser
  cookies are not inherited.

## 0.7.0

- Carry a task-specific, model-written final-use plan through activation using
  the existing `todo.txt`, clearly subordinate to human instructions.
- Prepare independent final-output assertions before implementing a seed
  extension, and run them on saved outputs after activation.
- Show the model-written plan at activation, then let new action results lead
  the conversation rather than repeatedly appending stale plan instructions.
- Apply requested defaults by omitting optional arguments instead of reusing
  an earlier step's explicit override.
- Keep the existing tools, host isolation and independent approval boundary.
  Qwen 9B completed 1/3 workflows with the refined seed alone and 3/3 with a
  supplied explicit final-use instruction; these familiar-task results do not
  establish general autonomous reliability. Early verifier adoption was not
  demonstrated. See the local experiment findings for source-bound evidence.

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
