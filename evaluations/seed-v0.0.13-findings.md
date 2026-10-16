# v0.0.13: corrected graders and bounded growth experiments

Date: 2026-10-16 (America/Regina). These are evaluation and protected-host changes. The default seed toolset, prompts and loop are unchanged; its version advances to 0.0.13. No model-written candidate was promoted.

## Graders and budgets

Both JSON graders now create valid external JSON before traversal/symlink checks and verify preserved external bytes. Deliberately boundary-bypassing implementations must fail both escape checks; the Unicode byte-limit negative control remains. Real VM positive/negative controls passed. All three saved accepted candidates still pass serial regrading, with unchanged source hashes. These are reassessments, not additional model attempts. Original verdicts and frozen plans remain saved.

New comparison plans default to 30 minutes and 65,536 generated tokens per attempt. Host counters include reasoning and repair responses, cap each request to the remaining allowance, preserve the standard wire adapter, and record conservative enforcement charges separately when usage is missing. Protected request, command and worker limits remain. Verified upgrades and autonomous completion are distinct fields; the old accepted alias keeps its full-workflow meaning. Legacy generalization forks record a budget per VM stage; the new paired growth study shares a single token allowance and wall-time budget across development and activation.

## Normal connection transfer

The same receipt-verified Qwen3.5 4B Q4_K_M GGUF was imported as `autoproteus-qwen35-4b-q4km:experimental`. The test used managed Ollama and production ModelClient, without nine-digit ID rewriting or another inference adapter. Its optional host budget wrapper is covered by a payload-equivalence test. App preferences were not edited.

Settings: 131,072 context, 4,096 response tokens, temperature 0.6, thinking off, native tools, 128 actions; imported model parameters top-p 0.8, top-k 20, min-p 0, repeat penalty 1, presence penalty 0. Engine and model digests are in the validation JSON. This is an experimental transfer check, not qualification of the default model or proof of repeatability.

| Task | Verified upgrade | Completed autonomously | Model-task seconds | Generated tokens |
| --- | --- | --- | ---: | ---: |
| sha256_file | True | True | 607.17 | 21665 |
| format_json | False | False | 832.14 | 17611 |

SHA-256 completed and passed all checks. JSON formatting passed all independent behavior cases, but its added test suite failed and it stopped at the action cap. Neither hit the wall-time or generated-token ceiling. The normal connection therefore supports a concrete accepted upgrade, with reliability still unproven. These settings/runtime differ from the custom screening, so these observations do not establish a causal runtime comparison.

## Procedure and cumulative growth

The optional procedure now asks for an early invocation, actual file read-back and an exact simple expected example. A guest-only invoker runs independently of failing tests. It does not confer independent approval. Its successful observed calls count as development use, separately from native routing.

The paired study freezes the exact earlier accepted SHA seed. Both arms get the same invoker; only the treatment gets the optional procedure. Three alternating repeats test adding formatting, preserving hashing/tests, activation and an audit using both tools. All source packs, trusted hashes, journals and costs are retained privately; there are no operator candidate repairs.

| Arm | Finished attempts | Independent second-tool behavior passed | Verified second extensions | Functional cumulative growth | Direct-route success |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline | 3 | 1 | 1 | 0 | 0 |
| procedure | 3 | 0 | 0 | 0 | 0 |

`3-baseline` produced an independently verified second extension and retained hashing. It changed inventory.json during development, violating the required activation order; activation was therefore withheld. This is verified code growth, but not a completed staged workflow.

This is a small comparison on previously studied capabilities. It cannot establish broad self-improvement or justify automatic promotion. No attempt hit the time or generated-token ceiling; four stopped at the existing action cap. The summary budget_stops field counts time/generated-token stops; action-cap pauses remain in the per-attempt status. Matched full successes, when present, retain separate cost measurements; missing usage is not zero.

## Separate fresh-task reuse diagnostic

After the paired batch, the exact verified combined candidate from `3-baseline` received a new audit task. The candidate was not repaired. Its original staged-trial verdict remains unchanged. The fresh task asks it to format a new Unicode JSON file, hash the final bytes, write an audit receipt and inspect both artifacts.

Functional reuse: **True**. Source unchanged: True. Observed routes: {"development": [], "direct": ["format_json", "list_files", "read_file", "sha256_file", "write_file"]}. Model-task time: 27.42 seconds; reported generated tokens: 989. This diagnoses whether the exact capabilities can be used after loading on a fresh task; it does not establish autonomous activation or repeatability.

## Validation

Windows: **194 passed, 16 platform skips (210 tests total)**, including **all 22 real VM checks**. The VM coverage includes boundary-bypass controls, invocation with a failing suite, and host token exhaustion preserving a checkpoint. All five regenerated study groups passed scripted check-only calibration without loading a model. Linux-host validation is left to CI; Linux guest execution is covered by the local VM tests.

A first concurrent regrading attempt stopped while waiting for the single VM lease, with no public-tool execution. It is retained and labelled unusable as an infrastructure result. The replacement serial run passed all three candidates.

An initial full-suite run found one scripted navigation fixture missing the new plan budget field. The fixture was corrected, the original log retained, and the complete suite rerun successfully. No model candidate was changed to resolve either validation issue.

Private evidence: `.data/v0.0.13-standard-profile/`, `.data/v0.0.13-regraded-screening-serial/`, `.data/experience-studies-v0.0.13-ready/`, `.data/growth-study-v0.0.13/`, and `.data/v0013-*.log`. The compact [validation record](seed-v0.0.13-validation.json) separates model outcomes from infrastructure and scripted checks.
