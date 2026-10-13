# Local GPU model findings — 13 October 2026

**Qwen3.5 9B was the most promising configuration tested.** It passed all ten ordinary tasks and, after two small compatibility changes in a copied seed, wrote a working `file_summary` tool. That tool passed all 16 independent feature checks, all 28 unchanged starter tests, and a fresh-worker public-tool call. It nevertheless stopped at the action limit without adding its own focused tests or completing the requested report, so it was **not accepted as a completed autonomous upgrade**.

Across four models, the completed experiment contains **50 ordinary-task runs and 14 upgrade trials**. There were **no fully accepted upgrades and no candidate promotions**. Two Qwen trials stopped at a chat-template error rather than a capability test. The original starter, host controller and browser files remained byte-for-byte unchanged throughout every batch. Compatibility changes existed only in separate frozen copies.

## Ordinary tasks and initial upgrade trials

| Model / quantization | Protocol | Ordinary checks | Accepted upgrades | Main observation |
| --- | --- | ---: | ---: | --- |
| Qwen3.5 9B / Q4_K_M | Native, reasoning enabled | 10/10 | 0/2; template-blocked | Good task execution; long source inspection exposed a missing-user-turn compatibility error. |
| Granite 4 H-Tiny 7B / Q6_K | Native | 9/10 | 0/2 | Fast ordinary tasks; upgrade runs claimed completion without changing runtime source. |
| Qwen2.5-Coder 14B / Q4_K_M | Native | 0/10 | 0/2 | Returned bare tool JSON as text, rather than the native calls expected by this runtime. |
| Qwen2.5-Coder 14B / Q4_K_M | JSON fallback | 10/10 | 0/2 | Protocol worked; replacement modules broke imports and existing seed behavior. |
| Existing Qwen3 4B Instruct / Q4_K_M | Native | 8/10 | 0/2 | Could attempt source edits and run tests, but its final append implementation rejected valid calls. |

The 14B native failures should not be interpreted as an inability to perform ordinary tasks: the same weights passed all ten through the seed's existing JSON protocol. These profiles must remain separate.

Granite's ordinary failure omitted the requested em dash from the exact Unicode file. The 4B ordinary failures involved the nested-directory task and the requested JSON data transformation. These were saved-artifact failures, not failures inferred from a model's prose.

Native ordinary batches took 211.63 seconds for Qwen3.5, 107.58 for Granite, 203.78 for the failed 14B native format, and 188.26 for the existing 4B. The successful 14B JSON batch took 242.32 seconds. Those totals include ten VM launches, transfers, prompt processing and responses; they are not generation-speed measurements.

## Compatibility findings and Qwen follow-ups

| Copied Qwen seed | Summary trial | Append trial |
| --- | --- | --- |
| Original v0.5 snapshot | Template error after 37.41 seconds; no source edits | Template error after 42.40 seconds; no source edits |
| Original user turn retained after pruning | 48-action limit after 265.01 seconds; no source edits | 48-action limit after 236.26 seconds; no source edits |
| User turn retained, copied source normalized to LF | Working tool, 16/16 feature checks; paused after 300.31 seconds | Source-inspection loop; paused after 165.07 seconds without edits |

**A native template needs a real user turn.** The original task was still present in the system prompt, but history trimming could leave only an assistant call and its tool result. The downloaded Qwen template then returned HTTP 500 with `No user query found in messages.` Retaining the original request as a user message removed that error. The tested change is two lines in the copied agent's message construction; it introduces no planner or new tool.

**Mixed line endings obstruct exact edits.** The working project contained both LF and CRLF inside individual Python files. For example, `tools.py` had 165 newline characters, 96 of them CRLF; `providers.py` had 45 newlines, six CRLF. Qwen repeatedly proposed a 293-character replacement whose code matched when line endings were normalized, but whose LF text could not exactly match the original CRLF block. Five recorded rejected patches had that same property. Normalizing only the copied seed's `.py` and `.md` source allowed subsequent implementation and registration edits to succeed. Ordinary workspace file semantics, including CRLF preservation, were unchanged.

These follow-ups were fresh stochastic attempts, not replayed generations. The byte comparison establishes why the recorded exact edits failed; the small number of runs does not establish a precise causal effect on overall model success.

The working summary candidate changed only `autoproteus/tools.py`, `autoproteus/providers.py` and `README.md`. It preserved the original agent, storage, entry point and tests relative to its compatibility-patched starting copy. The independent checks verified byte/character/line/word counts, empty files, Unicode, CRLF, a file without a final newline, the exact 100,000-character boundary, oversized files, invalid UTF-8, directories, missing files, traversal, absolute outside paths, symlink escapes, cancellation, schema registration and both description formats. Its full suite still contained only the 28 original tests: **no new focused test file and no `feature.md` were produced**.

Its source is preserved as an inert, unpromoted review copy under `.data/local-model-tests/working-summary-candidate/`; the complete frozen source, diffs and check evidence are retained alongside the trial.

## Why the other candidates were rejected

- **Granite:** Both upgrade runs finished without runtime source changes. A completion message and a feature report did not supply the requested tool.
- **Existing 4B:** The summary attempt wrote tests but did not implement the tool. The append attempt completed after 402.85 seconds and passed the 28 protected starter regressions. Its new branch converted the path to a `Path`, then required that object to be a string, rejecting every valid call. Further code also attempted to write bytes to a text stream. Its own positive append test still failed, and independent valid-use and fresh-worker checks failed. Rejection therefore does not rest on the preliminary test-helper filename filter.
- **14B JSON:** The summary run stopped waiting for input after 195.46 seconds. Replaced modules could not import correctly; the protected suite failed with `ModuleNotFoundError: No module named 'harness'`. The append attempt ran 14 failing test commands, cycled through reads without repairing the imports, and reached 48 actions after 752.28 seconds. Neither exported seed passed protected regressions or independent invocation.

No human repaired model-written runtime implementations or tests. The human-written reference implementations used to calibrate the grader are excluded from all model results.

## Hardware, weights and method

All inference ran locally on the user's **GTX 1080 Ti, 11 GiB VRAM**, with an Intel i5-11600K (six cores, 12 threads), 34,132,537,344 bytes of system RAM, and Windows 11 Home 10.0.26200. Driver 581.29 reports compute capability 6.1. Initial desktop GPU allocation was about 2.4 GiB. No paid provider, cloud inference, driver installation or hardware change was used.

Ollama **0.40.2** was the existing portable engine. Executable SHA-256: `9eaec399fd941073f8ddfbd56e0447f77fca5c006b26b8b1874a7fb12719b2a0`. Models ran sequentially, with one loaded model and one inference slot. All candidate commands, imports and tests ran in AutoProteus's isolated Linux VMs. Host drives and general network access were unavailable to candidate code. Host process cleanup was verified after the final batch; all benchmark-owned inference runners and VMs stopped.

Ollama reported full GPU offload for the 9B, Granite and 4B configurations. At 16,384 context tokens, the 14B reported a 12,415,160,809-byte loaded footprint, of which 9,563,327,692 bytes were on the GPU—approximately 77%. **The 14B test used system RAM as well as VRAM.** Peak sampled total GPU use was 10,860 MiB, including other desktop use. Temperatures varied, with a sampled peak of 86°C; timing is not a controlled dedicated-GPU comparison.

| Download source | Exact weight bytes | SHA-256 |
| --- | ---: | --- |
| [Qwen3.5 GGUF publisher](https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF), `Qwen_Qwen3.5-9B-Q4_K_M.gguf` | 6,169,341,984 | `d784ce9eda1a5a7b51e8f705a9e6310844bf4f173654d115823c775fdea56d43` |
| [IBM Granite official GGUF](https://huggingface.co/ibm-granite/granite-4.0-h-tiny-GGUF), `granite-4.0-h-tiny-Q6_K.gguf` | 5,710,939,232 | `08ba6d279731929c644683969324801dddd15cf1b2bd345e91311a4e5e988798` |
| [Ollama Qwen2.5-Coder 14B](https://ollama.com/library/qwen2.5-coder:14b) | 8,988,110,784 | `ac9bc7a69dab38da1c790838955f1293420b55ab555ef6b4615efa1c1507b1ed` |
| Existing [Ollama Qwen3 4B Instruct](https://ollama.com/library/qwen3:4b-instruct) | 2,497,280,480 | `85e4a5b7b8ef0e48af0e8658f5aaab9c2324c76c1641493f4d1e25fce54b18b9` |

The Qwen Hugging Face revision was `182be2fd6c7bc44887d88a91cb03ff009cc9f549`; IBM's was `08d5a8a9741dd5c1a95d2d39e25253226aa1464e`. Downloaded blobs were independently SHA-256 checked against pinned metadata. Ollama manifests and tag digests are preserved in the JSON evidence. The optional Qwen vision projector was downloaded automatically but no vision tasks were performed. Weights remain cached in `.data/models/`.

Common settings were 16,384 context tokens, 4,096 response tokens, temperature 0.6, a 300-second request timeout, and a 60-second guest-command timeout. Ordinary tasks had terminal access disabled, 32 actions and 180 seconds; upgrades enabled guest commands, with 48 actions and a 900-second deadline. Thinking was requested when the engine advertised it. The 4B Instruct model emitted no thinking content despite that flag. There was one fresh attempt per task/configuration, no fixed sampling seed, and no human-provided implementation hints or code repair.

Acceptance required a completed run, the actual feature report, runtime and documentation changes, a new focused test, preserved existing tests and execution loop, passing protected regressions, a passing full candidate suite, independent valid-use/edge-case checks and a fresh-worker public call. The grader first rejected absent tools and accepted separate reference implementations for both features. An unknown-tool error cannot earn invalid-input credit.

The preliminary 4B scope filter excluded an additional new Python test helper. A follow-up allowed that helper and ran the full independent checks on identical candidate bytes; rejection was unchanged. The feature probe also pins the task's 100,000-character limit independently of candidate-defined constants. Neither correction produced an accepted candidate.

## Practical next steps

The evidence supports **testing Qwen3.5 9B further for seed development** on this machine, with the verified user-turn retention and consistent source line endings. It does not support replacing independent review with model self-reported success. The 14B coder's JSON mode is usable for ordinary tasks, but its larger size did not yield a reliable upgrade here.

The next seed changes can stay small: retain the original user turn after history trimming, enforce consistent LF endings for editable Python/Markdown source, and verify protocol compatibility when preparing a model. A follow-up should test whether additional context or a bounded continuation helps Qwen complete the missing tests and report. Neither was tested here, so no successful outcome or GPU fit is claimed for a larger-context configuration.

No planner, progress-gate framework, extra seed tools or production model default was added. This remains a small-sample capability and compatibility experiment, not a model ranking or a host-isolation security proof. Results are not numerically comparable with earlier CPU cloud tests or previous seed snapshots, temperatures and reasoning settings.

## Reproducibility

The [machine-readable results](seed-v0.5-local-results.json) contain all 50 ordinary cases, 14 upgrade trials, model placement, exact settings, fingerprints, reviews, grader calibration and limitations. The [fixed upgrade tasks](local-upgrade-tasks.json), [independent guest probe](local-feature-probe.py) and [VM benchmark driver](local-model-benchmark.py) are saved with the project. Private journals, frozen source, candidate diffs, model metadata and GPU samples remain under `.data/local-model-tests/`.

| Frozen source | SHA-256 |
| --- | --- |
| Original working v0.5 snapshot | `18b476a82b95fffdee974e093f0c63c2882001c30727bfe029e202758d9538ad` |
| Copied seed with original user turn retained | `9d3cc397948871a7e655f75dfc5dfe0103dd33af0d555fc0727ed925416475e4` |
| Copied seed with user turn retained and LF source | `4d8bb685b5da6e716f182373cf2b9af07bf554118b3d56e8a65b015b199fb3c0` |

These identify uncommitted working-tree snapshots, not a published v0.5 commit. The main matrix ran from 06:04 to 06:32 Saskatchewan time on 13 October; final copied-source checks ended at 07:14. No commit, push or deployment was performed.
