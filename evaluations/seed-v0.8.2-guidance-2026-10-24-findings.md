# v0.8.2 guidance comparison — October 23–24, 2026

A frozen comparison of the current seed against a shorter two-surface upgrade recipe. Each attempt adds `inventory_files(path=".", recursive=False)`, then uses its activated tool on a different directory and saves/inspects the exact final JSON. Both profiles use Q6 weights, 128K context, 4K responses, temperature 0.6, thinking off, the standard native adapter and no LoRA.

These are the **original frozen-grader scores**. A supplementary registration audit below found missed contract defects; the original pass count must not be read as full qualification.

| Model | Guidance | Original grader pass | Correct final artifact | Complete workflow |
| --- | --- | ---: | ---: | ---: |
| Qwen3.5 9B Q6 | baseline | 3/3 | 3/3 | 2/3 |
| Qwen3.5 9B Q6 | short-guidance | 0/3 | 0/3 | 0/3 |
| Empero Qwen3.8 Distill 9B Q6 | baseline | 1/3 | 0/3 | 0/3 |
| Empero Qwen3.8 Distill 9B Q6 | short-guidance | 1/3 | 0/3 | 0/3 |

Each attempt shares 60 minutes, 128 actions and 65,536 generated tokens across development, protected regression checks, held-out feature checks, fresh-worker public invocation, activation and final use. Feature credit also requires a new focused test and preservation of protected files. Workflow credit requires preserved inputs and activated source, observed new-tool use, correct saved JSON, observed inspection and explicit completion. Correctly passing the default explicitly is valid; omission is a separate diagnostic.

The starter arms passed their protected 52-test suites. Calibration reused the exact frozen-source and grader receipts: the positive control passed and five deliberately faulty/absent controls failed. No new ordinary application suite was run during this study.

Fourteen new 60-minute attempts were recorded. The original Qwen task-2 shorter arm was interrupted by a Windows atomic-file replacement error. Its mate was declared exploratory before its result was known. Both arms were replaced with one fresh short/baseline pair; all originals and costs remain in the JSON. Live-file monitoring could have contributed to the interruption. A proposed shared-delete reader failed a real-host replacement check, so monitoring switched entirely to the runner stdout stream.

The excluded baseline mate failed the 200-file limit. Across **all four Qwen baseline exposures**, the original grader passed **3/4** and workflows completed **2/4**. The primary matched 3/3 pass count therefore does not establish perfect repeatability.

The 12-run local runner continued and finished while the assistant was usage-limited. The replacement pair and analysis were completed after the user resumed the chat. The earlier 30-minute runs remain separate and are not pooled.

## Attempt evidence

| Model | Task | Guidance | Original pass | Final artifact | Workflow | Actions | Minutes | Main issue |
| --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| Qwen3.5 | 1 | baseline | yes | yes | no | 128 | 22.6 | action allowance reached |
| Qwen3.5 | 1 | short-guidance | no | no | no | 67 | 14.9 | invalid_recursion_0, invalid_recursion_1, invalid_recursion_None, invalid_recursion_'false' |
| Qwen3.5 | 3 | baseline | yes | yes | yes | 41 | 8.5 | — |
| Qwen3.5 | 3 | short-guidance | no | no | no | 128 | 18.3 | over_200 |
| Empero | 1 | baseline | no | no | no | 82 | 16.8 | existing regressions failed |
| Empero | 1 | short-guidance | no | no | no | 90 | 13.3 | default_path |
| Empero | 2 | short-guidance | yes | no | no | 128 | 12.7 | action allowance reached |
| Empero | 2 | baseline | no | no | no | 62 | 13.8 | default_nonrecursive_bytes_sort_and_symlinks, explicit_false, recursive_true |
| Empero | 3 | baseline | yes | no | no | 128 | 15.6 | action allowance reached |
| Empero | 3 | short-guidance | no | no | no | 51 | 22.5 | protected file changed |
| Qwen3.5 | 2 | short-guidance | no | no | no | 51 | 8.1 | over_200 |
| Qwen3.5 | 2 | baseline | yes | yes | yes | 57 | 12.2 | — |

## Supplementary closed-candidate audit

After the live runs, short scripted VM checks audited all five originally accepted candidates. These checks used no further model inference, ran outside attempt budgets and did not change frozen primary scores. The human reference passed; an intentional `>= 200` off-by-one implementation failed the exact-limit checks.

All five candidates accepted exactly 200 files and rejected 201, for both default and recursive calls. However, two Qwen baseline candidates (tasks 1 and 3) and the Empero short-guidance candidate (task 2) advertised `path` as required in their public schema. Their implementation accepted an omitted path, but their advertised interface contradicted the requested optional default. Static inspection of the saved registration source confirms the mismatch. The original grader missed this defect.

| Model | Guidance | Original pass plus all supplementary checks | Complete workflow plus all supplementary checks |
| --- | --- | ---: | ---: |
| Qwen3.5 9B Q6 | baseline | 1/3 | 1/3 |
| Qwen3.5 9B Q6 | short-guidance | 0/3 | 0/3 |
| Empero Qwen3.8 Distill 9B Q6 | baseline | 1/3 | 0/3 |
| Empero Qwen3.8 Distill 9B Q6 | short-guidance | 0/3 | 0/3 |

The additional schema audit narrows fully checked Qwen baseline workflows to **1/3**, or **1/4** when counting every baseline exposure. This is a posthoc diagnostic, not a newly preregistered comparison. Future grader versions should include optional-argument schema checks and the successful exact-file-count boundary before new trials are frozen.

## Limits and interpretation

The JSON distinguishes action, wall-clock and generated-token ceilings for every attempt. All 12 primary attempts finished below 30 minutes despite the 60-minute allowance; none reached the generated-token ceiling. One attempt in each model/guidance group reached 128 actions. A larger wall allowance does not by itself demonstrate a benefit: this restart used fresh trajectories. Failed contracts include defaults, strict boolean handling and the 200-file limit. A basic public invocation can succeed while boundary checks or protected regressions fail.

One Qwen control wrote the correct final JSON on its fourth activation-stage action, read it once, then repeated the same inventory call 46 times before exhausting the action allowance. The final prompt still contained successful tool results. Activation context is repeated in the prompt; whether that contributes to the loop remains an untested hypothesis.

A complete Qwen control needed 32 development actions and 9 final-use actions, about 6,350 generated tokens and 8.5 minutes. Useful unassisted extension is possible here; repeatability remains the qualification gap.

Only 0 pairs completed successfully in both arms. Efficiency comparisons are limited to such matched successes with complete usage/timing measurements. Full and partial aggregate costs remain separate in the JSON.

Reported input-token sums include prompt/cache tokens; they do not directly measure GPU work or money spent.

These are three repetitions on one unfamiliar directed capability. They do not establish cumulative second-feature growth, autonomous selection of a needed capability, or the best possible settings for either model. Empero is an unofficial distillation, and its reasoning-enabled profile was not tested.

The recommendation is to retain the current guidance for now. The shortened bundle did not improve this comparison. The next focused investigation should address requirements retention and finishing after correct output exists, while strengthening grader coverage; this study does not establish the cause of those failures. No experimental guidance or candidate was promoted into the application seed.

Private evidence: `.data/guidance-comparison-v082-60m-20261023/` and `.data/guidance-comparison-v082-60m-recovery-20261023/`. Raw calls, source packs, checkpoints, VM check sessions, model/runtime identities, receipts and the prospective recovery declaration are preserved. The report JSON provides per-attempt evidence paths and checksums.
