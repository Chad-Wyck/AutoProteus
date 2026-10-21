# v0.3.0: Qwen 9B staged-input comparison

**Qwen3.5 9B Q6 completed 2/3 staged-input workflows and 0/3 visible-input baseline workflows.**
This is an exploratory directed second-extension comparison from one supplied
hashing-capable parent. It earns no autonomous first-upgrade credit.

| Measure | Visible-input baseline | Staged final inputs |
| --- | ---: | ---: |
| Independently verified formatter extension | 3/3 | 3/3 |
| Earlier hashing retained | 3/3 | 3/3 |
| Declared input protocol satisfied | 0/3 | 3/3 |
| Verified source activated | 0/3 | 3/3 |
| Complete verification, activation and final-use workflow | 0/3 | 2/3 |
| Strict native-call route plus complete workflow | 0/3 | 2/3 |
| Correct saved final files in secondary audit | 3/3 | 2/3 |

The input protocols differ: baseline compliance requires preserving the visible
inventory until activation. Staged compliance requires leaving final inventory
and audit absent until the controller delivers the inventory after checking.
Artifact correctness is reported independently of those ordering requirements.
Correct files produced during development do not earn activated-workflow credit.

All six candidates passed all 20 formatter feature cases and retained hashing.
The baseline produced correct final files in all three attempts, but did that
work before activation. The first two staged attempts completed through native
calls after activation. The third activated successfully, then repeatedly read
the unchanged inventory until exhausting 128 actions; it never formatted the
final inventory or created audit.json. Its final run paused rather than finished.

## Frozen configuration

- Commit: cbc238b56037e5e119070289b5dcc839ff408941 (v0.3.0).
- Model: Qwen3.5 9B Q6_K, SHA-256 073a9275e65d9c8cd2819cf5f77b99fbaa6e87ba591da6bbaa86ec073a64bfef.
- GTX 1080 Ti, verified PrismML CUDA runtime, normal production native adapter.
  No tool-ID rewriting or JSON fallback.
- Context 131,072; responses 4,096; thinking off; temperature 0.6;
  top-p 0.8; top-k 20; Q8 KV cache; automatic GPU offload.
- Each attempt shares 128 actions, 65,536 generated tokens and 1,800 seconds
  across development, independent grading, activation and final use.
- Counterbalanced order: baseline/staged, staged/baseline, baseline/staged.
- Parent implementation and focused hashing tests were written by OxCoder in
  an earlier accepted attempt, assembled on the current seed and independently
  requalified. All arms use its exact unchanged bytes.

Starter SHA-256: 870a6b523a5d771cc931eca8b7a343e35d27a92aa35943cfcccf6a0d4f6dc304.
Supplied parent: ad5fbe47ceede347406880a6378ee008d970e92b5481ab5ca5e17078c62fde33.
Source and trusted runner fingerprints remained unchanged during the study.

## Per-attempt outcomes

| Cell | Verified extension | Activated | Complete workflow | Saved files correct | Actions | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01_sha256_file_baseline | True | False | False | True | 101 | 1073.1 |
| 01_sha256_file_staged-inputs | True | True | True | True | 31 | 488.0 |
| 02_sha256_file_staged-inputs | True | True | True | True | 36 | 596.7 |
| 02_sha256_file_baseline | True | False | False | True | 46 | 641.5 |
| 03_sha256_file_baseline | True | False | False | True | 34 | 541.0 |
| 03_sha256_file_staged-inputs | True | True | False | False | 128 | 1759.7 |

## Admission, pause and resumption

Original admission passed both benchmark requests and all five ordinary tasks.
App connection qualification passed in eight requests with one bounded format
repair; this was recovered success, not first-pass protocol success.

A human-requested gaming pause interrupted the first baseline attempt during
final use. Its candidate had already passed extension and retention checks and
been activated. Preserve that partial attempt and its costs without scoring it
as a semantic failure. The runner made an explicit fresh baseline attempt from
the same parent; completed ordinary tasks were reused. There are six completed
growth attempts plus 1 separately retained interrupted attempt.

The six completed attempts consumed about 85 minutes including grading and
cleanup. The interrupted attempt adds about 26 minutes, recorded separately.
The human gaming pause is excluded from those totals.

An additional qualification added on reload failed: after one format repair
Qwen used a valid native finish call but returned the previous round receipt
instead of the latest receipt. That failed reload stopped before another growth
attempt. Its trace and verdict remain unchanged.

Before resumed growth, a recorded admission amendment continued the already
admitted study after re-verifying identical weights, runtime, command, settings
and frozen inputs. The extra per-reload diagnostic became advisory; it was not
repeated until success. Ordinary app policy was not changed. This departure
makes the resumed results exploratory rather than confirmation under the
original resume gate. Reliable app qualification remains unestablished.

## Costs and interpretation

- Baseline, completed attempts only: 184 model calls, 31,664 reported output tokens, median 641.5 seconds. Complete token/call-timing measurements: True.
- Staged inputs, completed attempts only: 201 model calls, 28,059 reported output tokens, median 596.7 seconds. Complete token/call-timing measurements: True.

Interrupted-attempt measurements and all candidate records are included in the
portable results. Totals above cover completed attempts only. Logical input
tokens include cached prefixes and are not uncached compute or financial cost.
There were no original-only matched completed-workflow successes, so no
matched-success efficiency advantage is claimed.
The runner retains original-only matched comparisons; a replacement attempt
cannot silently substitute for an original matched-success efficiency pair.

The intervention changes input delivery and its transition instruction. It
does not isolate either element, increase model coding ability, or establish
generality beyond this familiar formatter task. Three repeats, one model and
one supplied parent are insufficient to claim reliable autonomous growth.

The useful next qualification is another model and unfamiliar task families,
then fresh first-and-second chains. Any normal-app workflow change should keep
checking and activation in the protected controller and be measured separately
from additional editable-seed instructions.

## Evidence and cleanup

- [Portable results](seed-v0.3.0-staged-input-results.json) contain every completed
  result, independent feature checks, retention, provider-measurement coverage,
  original interrupted-attempt measurements, secondary artifact audits, and
  the admission amendment.
- [Prepared plan](staged-inputs-v0.3.0-plan.md) records the original comparison.
- Full frozen plans, traces, journals, candidates, reload receipts and failed
  diagnostic remain under .data/staged-inputs-v030-20261020/.
- Model server and owned VMs stopped; final SSD free space 11.015%.
- No model-written candidate was installed as the starter or imported on the host.
- No LoRA training or macOS implementation was started.
