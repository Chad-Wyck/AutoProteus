# Cancellation accounting and context-retention investigation

The default context policy is unchanged. The accounting correction is local;
the separately validated default-use grader fix was committed and pushed as
`2a71765`. The receipt-scope cue remains an unpromoted experiment. No model,
tokenizer, training job or VM was started for this investigation.

## Accounting defect and correction

`ModelClient.complete` can return promptly on cancellation or timeout while its
transport worker continues. The old token-budget observer ignored all events
after the caller closed. A worker could therefore record `provider_request`
after `call_end`, leaving zero charge and `usage_complete=true` despite unknown
generation. Two event-barrier regressions reproduced false completeness before
the fix; no model or network transport was needed.

The corrected host-only research budget:

- Reserves the response allowance while a closed caller's dispatch is unsettled.
  `pending_dispatch_calls` distinguishes that uncertainty from observed sent
  calls. Neither state is complete measured usage.
- Updates one charge per call identity when late events arrive. A late observed
  request changes the classification without charging a second time. A worker
  that settles without any observed dispatch releases its pending reservation.
- Keeps `reported_output_tokens`, `reserved_output_tokens` and their sum
  `charged_output_tokens` separate. A reservation is an enforcement charge,
  not an assertion about actual generated tokens.
- Binds late callbacks to their original call and original downstream observer,
  even after the client starts a later call. Call lifecycle changes are locked.
- Retains conservative paid-study reservations for uncertain dispatch, explicitly
  labelled `dispatch_uncertain`. This was tested with mocked transport only;
  pricing, credentials and remote service configuration were not changed.

Late provider responses do not release actions, retroactively update historical
reports, or turn a cancelled caller into a completed task. Without usage in the
caller's terminal receipt, the token budget conservatively retains the unknown
reservation even if a separate late raw response contains usage. Trace-derived
measurements may still expose that response independently. A saved summary from
before transport settlement remains a partial snapshot, not a live receipt.

## Where context is actually reduced

There are three distinct mechanisms, plus separate hard broker limits:

1. **Seed selection (`autoproteus/context.py`).** Both the original task and
   human follow-ups are required. Tool declarations, system text, activation
   state and optional todo/runtime notices consume space. Old non-human
   action/result groups are removed first; a last oversized view may shorten or
   omit observations and replace oversized actions. The complete journal stays
   on disk. The estimator prices serialized neutral messages at two UTF-8 bytes
   per token, reserving response tokens and another 128 tokens.
2. **Concise activation handoff (`guest/worker.py`).** After that selection,
   concise mode deliberately retains system instructions, human instructions
   and the activation boundary/tail. This is a workflow policy, not tokenizer
   overflow. The host can restore the activation notice if it fits. Recovery
   notices are placed after the boundary so this handoff retains them.
3. **Protected provider assembly (`controller/providers.py`).** Native envelopes,
   tool IDs and response-format instructions add bytes. The host applies its
   own two-byte estimate to the actual wire representation, removing old complete
   tool exchanges while preserving human messages and the newest exchange.

The broker separately caps inference at 2,048 messages and 1,500,000 serialized
message bytes; the worker frame cap is 4 MiB. These resource limits are not the
observed 32K token estimate and must not be removed to change history policy.

The existing `host_history_messages_omitted` field is exact `(role, content)`
multiset subtraction, not a semantic memory-loss measure. Rewriting, shortening
and concise handoff all create mismatches. Counts across successive calls repeat
the same history differences and cannot be added up as uniquely lost messages.

## Read-only evidence from the latest closed comparison

The new `context_retention_audit.py` joins saved seed request views, host call
snapshots, handoff events, actual provider requests and reported prompt usage.
It reads JSON directly, rejects running queues and never loads session stores
through recovery APIs. Reports contain counts and evidence hashes, not prompt
text. Unsupported Responses envelopes and missing usage are explicitly unknown.

Audited inputs: both arms of `.data/development-route-test-20261101-01/`.
These remain distinct arms; the receipt candidate's interrupted JSON cell is
resource-affected and is not evidence of model performance.

| Arm / extension stage | Largest reported prompt | Calls with signature mismatches | Wire-trim events |
| --- | ---: | ---: | ---: |
| Baseline, first SHA | 12,512 | 15 | 1 |
| Baseline, second formatting | 12,802 | 42 | 8 |
| Baseline, first formatting | 12,509 | 23 | 0 |
| Baseline, second SHA | 13,162 | 14 | 1 |
| Receipt candidate, first SHA | 12,512 | 9 | 1 |
| Receipt candidate, second formatting | 13,224 | 33 | 16 |
| Receipt candidate, first formatting, resource-affected | 13,152 | 22 | 8 |

Across these seven extension cells there were 258 observed calls, 158 calls with
signature mismatches and 35 wire-trim events. These are repeated observations,
not pooled accuracy or unique knowledge losses.

At 32,768 configured context tokens and a 4,096-token response reservation, the
input estimate allows 28,544 tokens, or 57,088 serialized bytes. One baseline
request contained 56,352 wire bytes: the host estimated 28,176 input tokens while
the backend reported 12,512 rendered prompt tokens. This demonstrates substantial
conservatism on that retained request. It does not tokenize the discarded
history, prove the whole original trajectory would fit, or establish why a task
failed. The representations differ, including chat-template framing.

Another baseline request went from 61 seed-selected messages to five at concise
handoff, then six at the host after activation-state restoration. That reduction
must not be attributed entirely to token budgeting. The audit records all three
counts separately.

Private versioned outputs and source/trace/journal hashes are in
`.data/context-retention-investigation-20261102/baseline-v2.json` and
`receipt-candidate-v2.json`. Earlier draft audit outputs remain preserved.
Original queues, prompts, results and model-written candidate files were not
changed or executed.

## Next controlled experiment, not launched

First qualify one opt-in estimator against the actual provider representation
at both selection stages. The existing usage-anchor experiment is a useful
starting point; provider/model/tool/source changes and prefix mismatches must
invalidate its anchor, with the current conservative fallback retained. An
exact host tokenizer is another possible estimator, but is not implemented or
loaded by this investigation. Changing only the host estimate cannot recover
observations already removed by the seed.

Keep concise handoff fixed while comparing estimators; investigate handoff as a
separate treatment if needed. Keep original human text, corrections, activation
state, operation receipts and valid recent call/result groups intact. Preserve
host byte/message/resource caps and independent verification. Freeze fresh plans
after the accounting/grader changes; old scientific fingerprints are historical.

Use one matched base-Qwen comparison later, measuring accepted first packages,
first use, second extensions, cumulative use and explicit finish. Record actual
prompt usage, both trimming stages, response reservations and partial cancelled
usage. No effectiveness, speed or expanded-history safety claim follows from
this offline investigation. No live comparison is queued.

## Validation and Git scope

The final ordinary suite ran **594 tests: 525 passed and 69 skipped**, with VM
opt-in disabled. This includes twelve token-budget controls and three new
context-audit controls. Existing provider, context, activation-use, growth and
receipt-experiment controls also passed. No live model, paid API or candidate VM
execution was used. The initial restricted run's loopback socket permission
errors are preserved separately; the successful rerun enabled local test sockets.
Logs are `regression.log` and `regression-loopback-enabled.log` under the private
investigation directory.

Only `controller/tool_evidence.py`, `evaluations/novel_features.py` and
`tests/test_novel_features.py` were included in pushed commit `2a71765`.
At investigation completion, accounting fixes, the audit tool and this note
remained local alongside the earlier receipt experiment. Subsequent publication
includes that work, retaining the receipt cue as an opt-in source builder rather
than changing the normal seed/helper. See the closed context-retention findings
for later live evidence; the default context policy remains unchanged.
