# Seed refinement findings — 12 October 2026

The editable seed is substantially smaller. The protected host still owns isolation, model connections, setup, the interface, and recovery. Neither model-authored feature candidate was promoted.

## Seed size

| Frozen editable copy | Files | Bytes | Runtime Python lines, excluding tests |
| --- | ---: | ---: | ---: |
| Original, revision `b8fed5a` | 18 | 176,859 | 1,291 |
| Refined | 8 | 56,858 | 582 |

The transferred copy is 68% smaller by bytes. Host server, configuration, runtime adapters, browser assets, and benchmark definitions no longer enter the editable copy. `SEED.md` becomes the guest's `README.md`. Existing provider formats remain handled by the controller.

## Local-model task checks

Each model ran ten fixed tasks twice against each frozen version: 80 total cases. Success required the requested saved-file contents and completed execution. Missing files, incorrect bytes, setup errors, and timeouts count as failures.

| Cached local model | Original | Refined |
| --- | ---: | ---: |
| Qwen3 1.7B | 13/20 | 16/20 |
| Qwen3 4B Instruct | 15/20 | 17/20 |

Both batches used native tool calls, 8,192 context tokens, 2,048 response tokens, temperature 0.2, 32 steps, and a 180-second task deadline. Terminal access was disabled. The scripted demo was not counted as a model result. No hosted-provider requests were used.

These counts do **not** establish a reliable capability improvement. The sample is small and the two versions ran in separate batches. Three original 4B cases failed during VM source/input setup while VM tests overlapped. Two refined 4B cases timed out during model startup contention with orphaned managed runners. Warm-up, cache, and machine conditions were not controlled. Timing and reported-step totals are retained as diagnostics, rather than evidence of efficiency gains.

Subsequent fixes serialize VMs across project processes, verify every input's SHA-256 before loading it, keep one managed model loaded, and end the managed engine's child processes when its owner closes. Real VM and process lifecycle checks verify these behaviors. A fresh, interleaved comparison after these fixes would be needed to evaluate performance differences more confidently.

## Self-improvement trials

Qwen3 4B Instruct chose the feature in each trial. Candidate code and all executable checks ran inside the VM; the host reviewed source bytes and independently checked exported results.

1. **Task context preservation:** The model replaced much of the agent loop, invented unavailable interfaces, and reached the 64-step limit without running its tests. The unchanged protected suite failed to import the modified code. Rejected.
2. **File summary tool:** A narrower request preserved the agent loop and added a tool, description, documentation, and a new test file. The protected suite passed all 23 tests. Four independently written checks passed for summary counts, an empty file, traversal rejection, and invalid-range rejection. However, its own new test file imported a nonexistent `Agent` interface; the full candidate suite failed. The model service failed during the subsequent attempt to continue, leaving the run incomplete. Rejected.

The second trial used 16,384 context tokens, 4,096 response tokens, and up to 48 steps. Both trials had guest commands enabled and a 900-second deadline. Saved preferences were unchanged. A small functioning addition with broken tests and incomplete execution is insufficient for acceptance. Neither trial demonstrates a completed autonomous upgrade.

## Review workflow

The source panel now provides **Check edited seed**. It freezes the starter, candidate, connected-model settings, and trusted task definitions. A protected driver first runs unchanged starter tests against both versions. Failure stops the comparison before model tasks. Otherwise, both versions run the same tasks in fresh VMs, with order alternating between repeats. The interface shows verified task outcomes, regression output, failure details, and bounded source diffs. Stop saves an incomplete report, and saved reports survive restart.

Checks never activate a candidate. New features require separate independent checks and review. Candidate modules can influence test behavior and output; protected test execution is diagnostic evidence, not proof of honesty or security. The host isolation policy remains outside every editable copy.

Final validation passed all 68 host and guest regression tests with real VM checks enabled, including host-file invisibility, network isolation, credential separation, corrupt-input rejection, frozen comparisons, Stop and starter recovery, and managed engine child-process cleanup. JavaScript syntax and repository whitespace checks passed. The saved rejection report was also reopened and inspected in the browser after restarting the app.

## Reproducibility

The sanitized [machine-readable results](seed-v0.3-results.json) contain each case, configuration, content fingerprints, trial verdicts, and limitations. Private source snapshots, candidate diffs, journals, and full reports remain under `.data/`; they are not committed. Fingerprints use sorted relative filenames and hashes of exact file bytes, independent of list order.

| Frozen version | Source SHA-256 |
| --- | --- |
| Original | `4a68545d1e47a50bd9a7f5ee57c393aa9eb0327c15d740c98c5b54d7c1c8d4b3` |
| Refined benchmark copy | `73b25062876f57c8eb71e3581930901db1d870573ee1921520bb4c68898351d9` |

The refined benchmark snapshot predates a small test-fixture change that lets protected guest tests use a writable temporary directory. That change did not alter seed runtime behavior. Source changes after either frozen snapshot must be evaluated as a new version.
