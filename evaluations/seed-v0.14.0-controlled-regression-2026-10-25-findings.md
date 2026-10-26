# Controlled Qwen 9B seed comparison — October 25, 2026

**The comparison did not reproduce an overall acceptance regression.** The
current v0.14.0 starter earned 5/9 accepted first extensions, versus 4/9 for the
frozen v0.8.2 starter. This small difference does not establish reliable
improvement or equivalence. Efficiency among matched successes remains a concern.
All 18 prospective attempts finished without an interruption or selective retry.

| Fully accepted first extensions | v0.8.2 | v0.14.0 |
| --- | ---: | ---: |
| SHA-256 | 2/3 | 3/3 |
| CSV preview | 1/3 | 0/3 |
| JSON formatting | 1/3 | 2/3 |
| Total | 4/9 | 5/9 |

Of nine matched pairs, both starters passed three, both failed three, the older
starter alone passed one, and the current starter alone passed two. These are
first-extension/package results, not second-extension or full-growth workflows.
The previous 1/3 single batch remains an independent exploratory observation;
it is not pooled into this prospective comparison.

## What was held fixed

- The same retained Qwen3.5 9B Q6_K checkpoint, GTX 1080 Ti and pinned PrismML
  engine for both arms. No Ollama/Prism or 64K/128K change between arms.
- 131,072 context tokens, 4,096 response tokens, temperature 0.6, top-p 0.8,
  top-k 20, min-p 0, thinking disabled, Q8 KV cache and the production native
  adapter. No LoRA, custom call-ID adapter, task coaching or candidate repairs.
- Identical hashing, CSV and formatting contracts and task-level instructions.
  Three repeats per capability; capability order rotates and arm order alternates.
- Predeclared initial RNG seeds 104729, 130363 and 155921 per repeat, shared by
  matched pairs. Runtime receipts confirm every actual seed and 128K context.
  Different prompts still produce different trajectories; matching the initial
  seed does not imply identical random draws or deterministic outcomes.
- A fresh model-server process and context for every attempt. Connection
  qualification ran separately and passed in eight requests before trials.
- 128 actions, 3,600 shared wall seconds and 65,536 generated tokens per attempt;
  600-second provider request timeout. Candidate execution and all graders ran
  in disposable VMs, with terminal enabled and internet disabled.
- The same current feature/schema/boundary/public-invocation graders, with
  positive/negative controls calibrated before inference. Both original starter
  suites, scripted write/read/finish/command checks and the common protected
  regression floor passed before admission.

Exact source identities:

| Arm | Frozen source SHA-256 |
| --- | --- |
| v0.8.2 | `443ac88ee62ac0ee5c495ab93e9b32059c6f1f12fbb3a6058ce322cd45272eef` |
| v0.14.0 | `944dde7bd0e5185699c292b929d0fd4042031266872fc29a8af4c38a84b88465` |

The earlier starter is the frozen baseline from the v0.8.2 guidance study, not
one of its model-edited candidates. Current source is checkpoint `8808584`.
Neither starter received a supplied capability. Application source and saved
settings were unchanged throughout this comparison.

Both seeds retain their original bundled suites and instructions; those are
part of the tested starter. The protected host floor uses the same portable
50 tests for both arms, rather than imposing later loop-feature requirements on
an older starter. All candidates passed that common floor. Feature grading
also requires the candidate's own complete suite. These controlled scores do
not assert that v0.8.2 satisfies every modern release test or reproduce its
historical grader scores.

## Individual attempts

Times include guest work and independent grading, but exclude server loading,
asset verification and connection qualification. All attempted cells remain in
the results, including unsuccessful completed submissions and a paused run.

| Repeat | Capability | Arm | Accepted | Actions | Read actions | Minutes |
| --- | --- | --- | --- | ---: | ---: | ---: |
| 1 | Hash | v0.8.2 | Yes | 33 | 10 | 7.7 |
| 1 | Hash | v0.14.0 | Yes | 107 | 90 | 15.6 |
| 1 | CSV | v0.14.0 | No | 84 | 31 | 26.2 |
| 1 | CSV | v0.8.2 | Yes | 63 | 18 | 23.3 |
| 1 | Format | v0.8.2 | No | 108 | 75 | 18.6 |
| 1 | Format | v0.14.0 | No | 59 | 11 | 18.4 |
| 2 | CSV | v0.14.0 | No | 56 | 14 | 15.9 |
| 2 | CSV | v0.8.2 | No | 39 | 6 | 13.3 |
| 2 | Format | v0.8.2 | No | 128 | 112 | 21.6 |
| 2 | Format | v0.14.0 | Yes | 27 | 5 | 8.9 |
| 2 | Hash | v0.14.0 | Yes | 45 | 12 | 8.9 |
| 2 | Hash | v0.8.2 | Yes | 37 | 19 | 7.5 |
| 3 | Format | v0.8.2 | Yes | 76 | 20 | 17.6 |
| 3 | Format | v0.14.0 | Yes | 62 | 25 | 21.7 |
| 3 | Hash | v0.14.0 | Yes | 47 | 21 | 9.8 |
| 3 | Hash | v0.8.2 | No | 49 | 26 | 9.2 |
| 3 | CSV | v0.8.2 | No | 65 | 19 | 17.0 |
| 3 | CSV | v0.14.0 | No | 82 | 32 | 19.7 |

## Failures remain distinct

- Current CSV attempts failed exact-limit/truncation, quoted-field or valid
  Unicode boundary cases. The last rejected valid Unicode inputs as invalid
  UTF-8 and also retained development files inside the submitted seed.
- The two unsuccessful older CSV candidates raised errors when `limit` was
  omitted instead of applying the default. Their own suites had passed.
- The first older formatter failed the exact output-limit boundary. Its second
  formatter left a failing candidate suite and reached the 128-action allowance.
- The first current formatter modified protected `autoproteus/file_ops.py`,
  outside this task's declared two-file scope. Feature execution was withheld;
  this result does not establish that its formatting behavior was incorrect.
- The last older hashing candidate passed its feature, public invocation and
  candidate-suite checks, but left `harness/test_file.bin` outside the allowed
  submission scope. This is a packaging/instruction failure rather than broken
  hashing behavior. It remains a failed acceptance observation.

No trial reached its wall or generated-token ceiling. Provider traces recorded
no provider-error categories. There were no human fixes, corrective prompts,
unrecorded retries or promoted candidates.

## Efficiency among matched accepted successes

There are three pairs in which both arms were accepted and call/token/timing
measurements were complete: repeat-1 hash, repeat-2 hash and repeat-3 format.

| Sum over those three pairs | v0.8.2 | v0.14.0 | Current difference |
| --- | ---: | ---: | ---: |
| Model calls | 149 | 217 | +45.6% |
| Reported generated tokens | 24,925 | 33,409 | +34.0% |
| Trial seconds, including grading | 1,966.195 | 2,776.777 | +41.2% |

Much of the call difference comes from the first current hashing attempt:
90 read actions and 108 model calls, versus 10 reads and 34 calls for the older
seed. This was not universal: the third current formatter used fewer calls
than its older counterpart, while generating more tokens. These observations
justify investigating wasted interactions; three matched successes do not
establish a universal speed regression or its cause. Automatic GPU offload
settings were fixed, but identical per-layer residency was not independently
guaranteed across server restarts.

## Interpretation and evidence

Keep v0.14.0 as the working seed. This comparison gives no acceptance-based
reason for a wholesale rollback. It also gives no basis for claiming reliable
self-extension: CSV is weak in both arms, packaging errors still matter, and
full cumulative use was not measured here. A focused navigation/finishing
experiment and practical CSV boundary verification are better next questions
than adding general seed machinery.

The batch ran from 14:28 to 19:22 Saskatchewan time on October 25, about 4 hours
54 minutes including calibration and model setup. It continued while the chat
was usage-limited. The owned server stopped afterward and the VM slot was
verified free. No application code changed.

[Machine-readable results](seed-v0.14.0-controlled-regression-2026-10-25-results.json)
include every outcome, failure detail, source identity, matched-pair cost and
private evidence path. Full local plans, scripts, calibration/qualification,
raw provider calls, runtime commands/assets/preflight receipts, candidate
sources and independent VM checks remain under
`.data/controlled-regression-v014-20261025/`. All primary attempts are retained
in `live/queue.json`; no completed failure was replaced or discarded.
