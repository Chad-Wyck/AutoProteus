# v0.3.0: OxCoder 9B staged-input comparison

**OxCoder 9B Q6_K wrote six independently verified formatter extensions and
produced correct final files in all six attempts. Consistent use of its added
capability after activation remains unresolved.**

This is a frozen, directed second-extension comparison from the same supplied
hashing-capable parent used in the Qwen comparison. It earns no autonomous
first-upgrade credit. Tests ran locally on 20–21 October 2026.

| Measure | Visible-input baseline | Staged final inputs |
| --- | ---: | ---: |
| Independently verified formatter extension | 3/3 | 3/3 |
| Earlier hashing retained | 3/3 | 3/3 |
| Declared input protocol satisfied | 2/3 | 3/3 |
| Verified source activated | 2/3 | 3/3 |
| Correct saved final files, secondary artifact audit | 3/3 | 3/3 |
| Complete workflow under frozen invocation detector | 0/3 | 1/3 |
| Complete workflow using direct native calls | 0/3 | 1/3 |
| Observed functional completion including additional Python route, posthoc | 1/3 | 1/3 |

Every candidate passed the 20 independent formatter cases, all 50 protected
seed regressions, the candidate's focused tests and public invocation checks.
All six also passed independent hashing retention and public hashing checks.
The five activated candidates retained their checked source unchanged.

The protocols differ: baseline compliance requires preserving the visible final
inventory until activation. Staged compliance requires leaving final inventory
and audit absent until the controller delivers the inventory after checking.
Correct artifacts produced before activation do not earn activated-workflow
credit. Withholding inputs and the focused transition instruction are a bundled
intervention, not separately identified causes.

## Per-attempt outcomes

| Cell | Verified | Activated | Frozen workflow pass | Saved files correct | Actions | Seconds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 01 baseline | True | True | False | True | 43 | 457.6 |
| 01 staged | True | True | True | True | 34 | 344.0 |
| 02 staged | True | True | False | True | 53 | 414.3 |
| 02 baseline | True | True | False | True | 72 | 520.0 |
| 03 baseline | True | False | False | True | 47 | 347.5 |
| 03 staged | True | True | False | True | 77 | 498.3 |

- Baseline 01 correctly invoked both capabilities after activation through
  guest Python: it imported Workspace, assigned an instance to w and called
  w.execute. It inspected correct artifacts and explicitly finished. This is
  useful functional growth despite the frozen scorer missing that spelling.
- Staged 01 used format_json and sha256_file directly after activation,
  produced the correct audit and explicitly finished. It satisfies both
  functional and strict native-use criteria.
- Baseline 02 and staged 02 produced correct outputs after activation but used
  ordinary Python JSON formatting instead of their new format_json tool.
  They used native hashing and finished, but did not demonstrate formatter reuse.
- Baseline 03 produced correct files during development, changed the final
  inventory before checking and never reached activation.
- Staged 03 produced correct files and finished after activation, using ordinary
  JSON formatting, sha256sum and hashlib rather than its two supplied tools.
  It also repeated hashing commands. All are functional task outputs; they do
  not demonstrate use of the new reusable capability.

No attempt reached its wall, generated-token or action ceiling. No candidate
repairs or task nudges were supplied by the operator.

## Invocation detector limitation

The frozen detector recognizes native calls, the development invocation command
and a narrow Python expression that constructs Workspace and calls execute in
one expression. It misses the common bound-instance spelling w = Workspace(...)
followed by w.execute(...), and commands preceded by cd /work/task &&.

An explicitly secondary, read-only audit parses saved command strings as data,
normalizes that exact literal workspace prefix, and observes unconditional
top-level calls through a variable assigned Workspace(...). It never imports or
executes model-written source. Baseline 01's saved zero-exit command outputs
corroborate the observed formatter and hashing calls, while independently
checked final artifacts establish task correctness.

The original verdicts remain unchanged. The supplementary functional count is
not a new native-route pass or an independent repetition. Baseline 03 also has
such call evidence, but it occurred before activation and receives no additional
completion credit. Observed command routes are diagnostic evidence, not a
security proof about hostile candidates.

## Frozen configuration and admission

- Repository commit: 4d3c8f3, v0.3.0. Editable starter and trusted runner files
  are identical to the Qwen comparison.
- Model: OxCoder 9B Q6_K, 7,359,267,840 bytes; weight SHA-256
  2a88e77a2d4623027b5387af4a8d6d060afe9746cfbf0be0e5384da21161ed40.
- Model repository: sizzlebop/OxCoder-9B-GGUF, revision
  468132cf1e1fde2b98da5c87fda2ca5f14f55a30.
- GTX 1080 Ti; verified PrismML prism-b10777-e3de715 CUDA 12.4 runtime;
  normal production native adapter, no tool-ID rewriting or JSON fallback.
- Context 131,072; responses 4,096; thinking off; temperature 0.6; top-p 0.8;
  top-k 20; Q8 KV cache; automatic GPU offload.
- Every attempt shares 128 actions, 65,536 generated tokens and 1,800 seconds
  across development, checking, activation and final use.
- Counterbalanced order: baseline/staged, staged/baseline, baseline/staged.
- Starter SHA-256:
  870a6b523a5d771cc931eca8b7a343e35d27a92aa35943cfcccf6a0d4f6dc304.
- Parent SHA-256:
  ad5fbe47ceede347406880a6378ee008d970e92b5481ab5ca5e17078c62fde33.

The parent contains an earlier OxCoder-written hashing implementation and focused
tests, assembled on the current starter and independently requalified. Every
attempt received exactly that source and a fresh task workspace.

Admission was frozen before inference: the benchmark and at least four of five
ordinary tasks control admission. App connection qualification is advisory and
performed once, without resampling until success. OxCoder passed the benchmark,
all five ordinary tasks, and the advisory connection diagnostic in eight
requests with one bounded format repair. This is recovered diagnostic success,
not first-pass protocol success or qualification of the default app settings.

The source, runner, model, runtime and helper fingerprints were checked before
inference; the starter, trusted runner and helper fingerprints were checked again
when preparing this report. No application source was changed or candidate
promoted during the study. Six attempts completed without interruption or retry.

## Costs and comparison limits

| Arm | Model calls | Reported input tokens | Reported output tokens | Median seconds |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 166 | 1,800,569 | 28,385 | 457.6 |
| Staged | 170 | 1,760,671 | 26,560 | 414.3 |

All call traces, input-token measurements, output-token measurements and call
timings are complete. Totals include failed workflows. Logical input tokens
include cached prefixes and do not measure uncached compute or financial cost.
The six growth attempts consumed 2,581.7 seconds, about 43 minutes; the whole
driver took about 45 minutes including admission and cleanup.

There are no matched original-attempt successes under the frozen workflow
criterion, so this batch establishes no matched-success efficiency advantage.
Even with the posthoc route observation, only the first pair has functional
successes on both sides; one pair does not support an efficiency claim.

The earlier Qwen Q6 study had the same six verified extensions, five correct
artifact sets and two strict staged workflows. OxCoder has six correct artifact
sets and one strict staged workflow. These results do not rank the models:
there are only three repeats per arm, one familiar task, one supplied parent
whose hashing code was originally OxCoder-written, sequential model runs and
different admission histories. Qwen also had a human interruption, explicit
fresh retry and an admission amendment after a failed reload diagnostic.

The narrower conclusion is that this model can write and verify the directed
extension reliably within this batch. Completing the task by reusing that
extension remains inconsistent. The evidence favors improving measurement and
testing completion behavior on unseen tasks before adding more seed machinery.

## Evidence and cleanup

- [Portable results](seed-v0.3.0-oxcoder-staged-input-results.json) preserve all
  six verdicts, independent checks, artifact audits, measurement coverage,
  diagnostic qualification and supplementary invocation evidence.
- [Qwen comparison](seed-v0.3.0-staged-input-findings.md).
- Frozen protocols, plans, fingerprints, journals, candidates, call traces and
  resource samples remain in .data/oxcoder-staged-v030-20261020/.
- The runner exited successfully and stopped its model and VM processes. A
  separate process check found no llama-server or QEMU process remaining.
- GPU memory returned to desktop use (about 1.5 GiB). The SSD retained about
  10.9% free space. No models were downloaded or removed for this comparison.
