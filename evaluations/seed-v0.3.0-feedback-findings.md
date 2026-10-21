# v0.3.0: OxCoder submission-feedback comparison

20 October 2026, America/Regina. Local results; no application source changes or
push during this study.

**All six formatter extensions passed independent checks and retained hashing.
One completed the required activation-and-use workflow. No repair ticket was
delivered, so this batch does not establish a benefit from submission feedback.**

| Measure | Baseline | Feedback enabled |
| --- | ---: | ---: |
| Independently verified new extension | **3/3** | **3/3** |
| Existing hashing preserved | **3/3** | **3/3** |
| New test file, permitted scope and protected regressions | **3/3** | **3/3** |
| Preserved final input until activation | **0/3** | **1/3** |
| Activated, used both tools, verified outputs and explicitly finished | **0/3** | **1/3** |
| Public repair continuations delivered | **0** | **0** |
| Exact final files in a separate, post-hoc artifact audit | **3/3** | **3/3** |

The artifact audit does not change the official workflow verdicts. In five
attempts the model completed the file operations through development commands
before requesting activation, violating the explicit ordering requirement.
Those working extensions and correct files remain useful evidence, separate
from successful use after controller activation.

## Frozen setup and scope

- Cached **OxCoder 9B Q6_K**, PrismML `prism-b10777-e3de715` CUDA 12.4,
  GTX 1080 Ti, standard production chat-completions adapter. No tool-ID rewriting.
- Context 131,072; Q8 KV cache; automatic GPU offload; flash attention;
  thinking off; temperature 0.6, top-p 0.8, top-k 20. Exact launch arguments and
  verified runtime/model hashes are retained.
- Three repeats per arm, ordered baseline/feedback, feedback/baseline,
  baseline/feedback. Each attempt received the same user task and supplied
  hashing-capable parent, then had to add `format_json` and finish an inventory
  audit. This is a directed second-extension comparison.
- Each complete development/grading/activation/use attempt shared 128 actions,
  65,536 generated tokens and 1,800 seconds. Responses retained 4,096 tokens.
  No attempt exceeded its wall deadline. One baseline used all 128 actions and
  then explicitly finished through the existing free final response.
- The parent was assembled from the current v0.3.0 starter/guidance and the
  unchanged implementation/registration/focused-test bytes of the first accepted
  hashing candidate from the prior matched study. It passed protected
  regressions, hashing feature/public checks, and formatter-absence checks before
  inference. It earns **no autonomous first-upgrade credit** in this study.

Root seed SHA-256: `870a6b523a5d771cc931eca8b7a343e35d27a92aa35943cfcccf6a0d4f6dc304`.
Supplied parent: `ad5fbe47ceede347406880a6378ee008d970e92b5481ab5ca5e17078c62fde33`.
The root source, trusted runner and human helper fingerprints remained unchanged.
No model-written candidate was installed as the starter.

## Outcomes and remaining bottleneck

Every candidate passed all 20 formatter checks, including Unicode character
boundaries, exact output limits, invalid-input preservation and workspace
boundaries, plus hashing retention, public calls and protected regressions.
Every candidate added a separate focused test file and met source-scope rules.

The five incomplete workflows changed `inventory.json` during development and
finished `completed`, rather than preserving that input and requesting
activation. The controller correctly withheld activation. The completed run,
feedback repeat two, preserved the original input, requested activation, passed
checks, then called both tools directly and wrote the correct formatted file
and audit receipt. Its candidate source stayed unchanged after activation.

The post-hoc audit independently compared final saved bytes and receipt fields
for all six sessions. All matched the requested canonical Unicode JSON and its
SHA-256. This shows useful task output even in the five ordering failures; it
does not demonstrate that those five candidates completed a later activated
workflow. Guest-reported development calls also lack exact runtime-source
hash binding at each call and are not security proofs.

Feedback was enabled but dormant: all three submitted candidates passed its
public source/test/syntax checks and had no eligible latest development failure.
The feedback currently omits task-stage prerequisites such as preserving the
real input until activation. With zero delivered repair interventions, the
observed 1/3 versus 0/3 cannot be attributed to feedback.

## Connection diagnostic finding and protocol amendment

The newly added app connection qualification rejected OxCoder before any upgrade
trial. A separate traced diagnostic also failed: the model echoed the supplied
values, recovered from the deliberate rejection, and correctly finished two
rounds, then returned plain text instead of the third native `finish` call.
The traced failure occurred on request seven. Both failures are retained.

Before any candidate rollout, an amended protocol made this strict diagnostic
advisory for both models and retained the public study runner's unchanged
benchmark/basic-task admission gate. The original protocol is preserved, and
the amendment records its original hash and reason. No source, model parameters,
protocol, grading requirement or candidate was changed. No JSON fallback was
used. The diagnostic was not repeated until it passed.

OxCoder subsequently passed both benchmark requests and **all five ordinary
tasks** through the standard native connection. Those outcomes qualify the
study's stated gate, **not the new app connection qualification**. The diagnostic
does not currently use the agent's bounded format-repair loop; aligning their
behavior is a worthwhile follow-up before treating it as a default admission
test. This finding is separate from the feedback comparison.

## Time, usage and conditional runs

The six attempts totalled **45.9 minutes**, including their grading and cleanup.
Initial server launch through final shutdown took **56.9 minutes**, including
calibration, the failed qualification, reload, traced diagnosis and ordinary
tasks. The prior multi-hour figures were maximum allowances, not expected time.

All six provider traces and reported input/output-token and call-time
measurements are complete. The upgrade attempts used 350 inference requests
and 51,761 reported output tokens. Logical input-token totals include repeated
and potentially cached prefixes; they are not uncached compute or dollar costs.
There were no matched full-workflow successes, so no efficiency advantage is
claimed. One baseline's 103 reads also makes aggregate cost comparisons fragile.

The predeclared confirmation rule required at least 2/3 completed feedback
workflows and a lead of two over baseline. The observed 1/3 versus 0/3 did not
qualify. **Qwen confirmation and conditional fresh first/second-extension chains
were therefore not run.** The source-context and lesson experiments remain
separate, unrun comparisons.

These are three-repeat observations on one familiar prescribed capability and
one parent. They do not establish broad generalization, autonomous capability
selection, or repeatable first-and-second-pass growth from the untouched starter.
The stronger functional results than earlier submission failures are encouraging;
historical differences do not isolate the effect of the new guidance.

## Suggested next comparison

Retain the compact seed and test public **stage-aware submission feedback**:
report changed protected task inputs and an incorrect submission status before
hidden grading, using only declared requirements. The already implemented
withheld-input experiment offers a separate way to test whether removing that
coordination burden helps. Keep hidden answers private and retain the same
shared allowances. The connection diagnostic also needs bounded-repair parity
with ordinary agent use. No such application changes were made during this run.

## Evidence and cleanup

- [Portable per-attempt results](seed-v0.3.0-feedback-results.json) include source
  identities, grading cases, usage coverage, public tickets, stage verdicts and
  the explicitly labelled post-hoc artifact audit.
- Full plans, original/amended protocols, provider traces, journals, candidates,
  protected calibration and exact runtime commands remain under the private
  `.data/night-v030-20261020/` directory. The successful two-tool candidate is
  also saved there as `successful-two-tool-source.json` for later review/reuse.
- Under the earlier authorized cleanup policy, checksum-verified unused Q4
  copies of Nemotron, LFM and Ornith were removed to restore the SSD reserve.
  About 17.5 GB was recovered; their metadata and earlier findings remain.
  Qwen, OxCoder and the higher-precision LFM copy were retained.
- All owned model servers and VMs stopped. Final free space is approximately
  **113.0 GB (11.03%)**. This run added findings and private study data; the
  pre-existing local application changes remain uncommitted and unpushed.
