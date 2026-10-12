# First patch: completion and harness improvement evaluation

Tested on 12 October 2026 with Ollama 0.40.3, a two-CPU quota, 8 GiB RAM, and no exposed GPU. The model was Ornith 1.5 9B at Q4_K_M. These are single runs at temperature 0.6, not estimates of general model reliability.

Native replies without tool calls previously became `needs_input`, including replies reporting successful work. The patch requires explicit `finish` calls and uses the existing two-retry repair loop. Checklists are optional ordinary `todo.txt` files written with `write_file`; the dedicated `update_todo` tool has been removed. The hosted connection probe uses a temporary JSON configuration and preserves the saved native preference.

| Evaluation | Before | After |
| --- | --- | --- |
| Native tasks: correct artifacts and completed status | 5/10 | 10/10 |
| Native tasks: artifact checks alone | 10/10 | 10/10 |
| Native requests / executed actions | 51 / 46 | 53 / 40 |
| Native checklist writes | 5 | 2 |
| Native elapsed time | 37.64 min | 34.84 min |
| JSON follow-up: nested directory, precise edit, recovery | 3/3 | 3/3 |
| JSON follow-up format repairs | 2 | 0 |

The native comparison used the same full 9B alias, 4,096-token context, 2,048-token response limit, default thinking, and disabled terminal. Four patched tasks produced a reply without a tool call and recovered after one repair each. Six additional exact-byte comparisons passed, including preservation of the original and copied files. The JSON subset used the text-only alias with 8,192-token context and 2,048-token responses; it is a subset, not a full JSON benchmark. Timing and action differences may vary with sampling.

The final regression suite passed 31 tests, with one Windows credential-encryption test skipped on Linux. The deterministic demo passed. The hosted probe regression reproduced a failure before the compatibility fix and passed afterward, including a native configuration with the JSON-mode preference enabled.

The new `--self-improve` evaluation asks the model to choose one useful feature, edit its harness copy, add a focused test and documentation, and explain independent acceptance checks. Changed runtime/test files and a feature description establish artifact readiness. They do not establish functionality: an artifact-ready submission reports `passed: null`, `REVIEW`, and exit code 2. Independent functional checks, the unchanged trusted regression suite, and inspection of preserved safeguards are required before separately activating a copy.

| Feature attempt | Outcome |
| --- | --- |
| JSON, 8K context, 4K responses | Operator paused after 17.22 min and 14 inspection actions; source reads were shortened to previews. No submission or source edits. |
| Assisted JSON retry, 16K context, 4K responses | Full source chunks became available, but three malformed actions omitted the `arguments` object. Stopped with an error after 7.41 min. No source edits. |
| Fresh native attempt, 16K context, 4K responses | Reached the one-hour limit after 18 inspection actions, without format errors. No submission or source edits. |

The retries included a reminder that offsets are byte positions. The model nevertheless used small, overlapping offsets such as 161, 300, and 380 when inspecting the agent loop. None of these attempts produced a feature candidate, so functional feature checks could not run. The model left the running seed unchanged. No model-authored changes were promoted.

The text-only model fit a 16K context: peak combined inference-process RSS was 6.55 GiB in the native feature attempt, with no out-of-memory event. The initial evaluation sampling peaked at 7.07 GiB. Memory capacity was sufficient for these profiles; source work was slow on the CPU quota.

The next small improvement should make file navigation and editing easier:

- Support bounded reads with clear position semantics and an explicit continuation position. The current tool offers a byte offset but no requested read length, while shortened output suggests reading a smaller section.
- Add one exact-match text replacement operation that rejects missing or ambiguous targets. It would preserve surrounding code and avoid generating an entire module for a small edit.
- Use a response schema for the JSON fallback so syntactically valid JSON cannot place tool arguments in the wrong location. Keep native tools as the primary path for models that support them.

Repeat the feature evaluation after those changes before adding more planning machinery or claiming autonomous self-improvement. Short-task completion improved in this run; useful model-driven harness improvement remains unproven.

The live runs used snapshot `bcce30d41a0d466315fc216e25f09b3964cf392a1a02972010c54a470aea7693`, based on repository commit `a49109cc7b0de20d02ec6a68ad8ca51c436cacbf` plus the completion/checklist patch and initial evaluator. Final adjustments to the hosted probe, fingerprint coverage, and their tests were checked separately; agent/provider/tool behavior used by the live task comparison stayed unchanged. Full new traces, profiles, resource samples, and a patch are retained in the workspace artifact bundle.
