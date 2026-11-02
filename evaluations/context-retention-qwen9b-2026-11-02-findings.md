# Qwen 9B context retention: fewer trims, no completed-chain gain

**Keep the default context policy.** The opt-in candidate retained more history
and reduced expense on matched successful chains, but completed **2/4** scheduled
growth chains versus the baseline's **3/4**. This small comparison does not
establish a repeatable benefit or general harm. It does establish that the
estimator engaged; this was not an unused intervention.

## Outcomes

The common baseline transport screen and five ordinary prerequisites passed.
Those are shared admission checks, not a separate candidate ordinary-task test.

| Independent outcome | Baseline | Context retention |
| --- | ---: | ---: |
| Accepted first extensions | 3/4 | 3/4 |
| Correct first use with explicit completion | 3/3 activated | 3/3 activated |
| Second extensions qualified, earlier capability retained | 3/3 attempted | 3/3 attempted |
| Correct final artifacts after second activation | 3/3 | 3/3 |
| Functional use of both required capabilities | 3/3 | 3/3 |
| Explicit completion after second activation | 3/3 | 2/3 |
| Complete functional growth chains | **3/4 scheduled** | **2/4 scheduled** |
| Complete chains with direct native capability calls | 1/4 scheduled | 1/4 scheduled |

Functional capability use can include an observed guest development/CLI route;
it is not silently rejected for lacking direct named-tool calls. Native routing,
correct files and explicit completion remain separate observations. Both arms
used native production transport throughout, including native `run_command`.

| Seed / first feature | Baseline first use / complete chain | Retention first use / complete chain |
| --- | --- | --- |
| 104729 / hashing | Pass / pass | Pass / fail: action allowance before finish |
| 104729 / formatting | Package rejected / second untested | Package rejected / second untested |
| 112648 / formatting | Pass / pass | Pass / pass |
| 112648 / hashing | Pass / pass | Pass / pass |

Both first-seed formatter candidates edited protected guest
`autoproteus/file_ops.py`, outside the requested two-runtime-file scope. They
were rejected before feature qualification; this is not evidence that their
formatters were semantically incorrect. The protected host files were not edited.
Their second stages remain gated and untested, not failed second extensions.

The extra retention failure implemented and retained both tools, activated them,
produced the exact formatted inventory and hash receipt, and invoked both tools
directly. It spent 55 actions in development, leaving nine for final use. It
then reached the shared 64-action allowance and requested another hashing check
instead of finishing. The task paused with correct artifacts but no explicit
completion. Its 529.7 seconds and 10,111 output tokens were below the time and
token ceilings. No human reminder, automatic repair or retry was supplied.

## Did context retention actually engage?

Across the seven executed feature stages in each arm:

| Observation | Baseline | Retention |
| --- | ---: | ---: |
| Largest reported rendered prompt | 15,345 tokens | 23,402 tokens |
| Additional host wire-trim events | 33 | 10 |
| Calls with host exact-message signature mismatches | 215 | 98 |

The host selected the provider-usage anchor in **256/278** candidate requests;
22 used conservative fallback. Guest journals retained 278 exact-request
receipts: 194 matched the seed's selected input without wire trimming and were
eligible to anchor its next estimate. Receipt eligibility is not itself an
observed next-call anchor selection. Concise handoff and host changes correctly
prevent a smaller wire prompt from anchoring a larger seed view.

Signature mismatches include removed, shortened and rewritten entries and the
deliberate concise activation handoff. These repeated-call counts are not unique
lost messages or knowledge. More retained context was measured; its causal
effect on any individual success or failure was not established.

## Expense among matched successes

Two whole chains succeeded in both arms: seed 112648's formatting-first and
hashing-first cases. Their first and second stages have complete call, token and
timing measurements. Totals exclude common prerequisites and fresh model loads.

| Two matched complete chains | Baseline | Retention |
| --- | ---: | ---: |
| Model calls | 178 | 153 |
| Logical input tokens | 1,654,752 | 1,611,367 |
| Output tokens | 27,060 | 24,494 |
| Model-call seconds | 1,496.5 | 1,176.5 |
| Shared task seconds, including checks/use | 1,670.7 | 1,345.4 |

That is **14.0% fewer calls** and **19.5% less task time** for these two matched
successful chains. One matched second stage was slower under retention.
Generated implementations, tests and histories differ; this is exploratory
workflow expense, not a demonstrated general inference-speed improvement.
Logical input totals include cached prefixes and are not compute or money.

The private audit also reports five matched successful *stages* separately;
those overlap the whole-chain pairs and are not additional independent trials.
All 20 launched cells had complete recorded usage. No unknown token reservations,
request timeouts or token-budget exhaustion occurred, so this study did not
exercise the cancellation race live. Its offline regression evidence remains
separate. No cost comparison excludes failures while claiming overall superiority.

## Frozen conditions, audit and closure

Existing Qwen3.5 9B Q6_K, no adapter; 32K context/4K response, temperature 0.6,
top_p 0.8/top_k 20, thinking off, q8 KV, one slot, automatic GPU offload,
batch 128/microbatch 64 and two CPU threads. Two fixed related families and two
paired request seeds were counterbalanced. Per-stage limits stayed 64 actions,
16,384 generated tokens and 600 shared seconds; requests retained 120 seconds.
Request seed equality is not proof of deterministic inference.

The original helper receipts and baseline prompt were used in both arms; the
receipt cue and all LoRAs were excluded. Only the opt-in estimation wiring and
shared helper differed. Default context handling was not promoted or changed.
The prepared-source IDs and plan identity remain in the preparation note.

All eight first starts and six eligible second stages ran once. Together with
six prerequisite cells, **20 cells finished execution and two were gated out**;
finished execution does not mean every task passed. There were no infrastructure,
resource or shared-deadline stops. The worker finished after **103.6 minutes**,
before its four-hour new-cell admission cutoff. That duration includes startup,
VM checks and idle reclamation, not continuous GPU compute.

Minimum sampled runtime RAM was 2.539 GiB, above the 2-GiB hard floor; minimum
sampled free VRAM was 2,269 MiB. These are sampled minima, not instantaneous
guarantees. Transient RAM below the pressure threshold did not satisfy the full
sustained-pressure stop condition. No guard was relaxed.

Read-only auditing rechecked saved artifact bytes, source hashes and activated
tool use for all twelve activated stages. All twenty runtime cleanup receipts
confirmed closure and empty adapter state before/after. Engine and weight asset
hashes, source, trusted checks, frozen plans and raw-result identities matched.
Candidate code was never executed on the host. CLI observations retain the
documented limitation that stdout evidence is not adversarial execution proof.

Final host verification found no owned supervisor, model, VM or listener on
47958; GPU utilization was zero. No further trial is queued. No training,
download, cloud call, promotion, merge, commit or push occurred.

Private closed reports, source/trace hashes and cleanup proof are under
`.data/context-retention-prep-20261102/final-audit/`: `closed-study.json/.md`,
`outcome-audit.json`, `supplemental.json`, `context.json`, `result-integrity.json`
and `host-cleanup.json`. Original queues, verdicts, journals and frozen sources
remain unchanged.
