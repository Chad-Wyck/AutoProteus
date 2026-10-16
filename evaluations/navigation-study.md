# Navigation comparison prepared for local testing

This experiment keeps the normal AutoProteus seed and saved preferences unchanged. It uses cached Qwen3.5 9B, a frozen baseline, and one copied seed variant that adds `source_outline(path)`. There is no model training, new model download, automatic promotion, or change to VM permissions.

The variant lists top-level Python functions/classes and class methods, including qualified names, line numbers, character starts and bounded lengths usable with the existing `read_section`. It parses source without importing or executing it. Input uses the existing 100,000-character read bound; output is limited to 60 definitions and approximately 6,000 JSON characters. Decorators, Unicode and CRLF retain usable character positions. The original reading tools remain available. The variant adds its dispatch, description, small helper and a documentation note; prompts, context policy and action limits stay the same.

## Prepare and run

From the repository with its private Python/runtime prepared:

```text
.runtime/python/python.exe -X utf8 evaluations/navigation-study.py prepare --output .data/navigation-study
.runtime/python/python.exe -X utf8 evaluations/navigation-study.py run --input .data/navigation-study --check-only
```

Preparation freezes source packs, the trusted runner files, task contracts, model settings and alternating run order. On Windows, **Start tests.cmd** in the output folder starts the model trials when double-clicked. On Linux, use the prepared Python interpreter or `python3` with the same runner commands. The `--check-only` command runs scripted VM fixtures and protected regressions without loading an LLM. A changed starter or runner invalidates a prepared plan; prepare a fresh directory after edits.

The same experiment can be started directly:

```text
.runtime/python/python.exe -X utf8 evaluations/navigation-study.py run --input .data/navigation-study
```

The plan contains **18 attempts**: two harnesses, three development contracts, three repeats. They cover SHA-256, CSV preview and JSON formatting. Harness order alternates. These contracts have been tested before, so any selected improvement still needs validation on new tasks and another model.

Both harnesses use Qwen3.5 9B Q4_K_M, 65,536 context tokens, 4,096 response tokens, temperature 0.6, thinking off, native tools, 128 actions, a 300-second request timeout and a 900-second ceiling per attempt. Terminal commands are enabled only inside the VM. The runner requires cached weights and KVM/WHPX; it supplies no native fallback. The full batch may take several hours on the GTX 1080 Ti.

Ctrl+C stops the current run and preserves results. Starting the same prepared plan again continues remaining schedule cells. Launched attempts, including interrupted ones, remain in the ledger and are not silently retried. Model digest and engine identity are pinned at the first run and checked on resume and before each trial. No model-written candidate runs on the host.

## Evidence and interpretation

Acceptance remains the primary measure: verified functionality, unchanged protected tests, meaningful added tests and completion. Reports retain those components separately. Efficiency comparisons use matched task/repeat pairs accepted under both harnesses. Trace completeness is separate from input-token, output-token and timing coverage. Known sums are explicitly complete, partial or unavailable; a missing usage count on a sent request is not zero. Local rejection before any wire request has zero inference token cost. Matched successes remain visible, but each cost metric is comparable only when both sides have complete measurements. Totals also include failed and interrupted attempts. Host task/trial wall time is tracked independently from call/transport timing.

New metrics count overlapping read intervals, returned context bytes, first recorded runtime edit, passing development checks and subsequent actions. Commands conservatively invalidate coverage because they may rewrite files. Reading coverage concerns observed file tools; shell reads are not inferred. A passing development check is diagnostic feedback, not independent approval.

Opt-in provider recording happens in the existing host adapter, after message conversion and before response normalization. It captures validated outgoing payloads, parsed raw response frames, finish/error outcomes, durations and usage. Call IDs associate cutoff/repair traffic with journal events. A host checkpoint comparison counts history entries absent from the submitted neutral context; it does not establish why the seed omitted them. The real outgoing messages and tool schemas remain visible in the trace.

Recordings stay under each private trial directory, capped at 32 MiB. HTTP headers and endpoint URLs are excluded, and occurrences of the known provider key are redacted. Task text and file contents can still appear in private traces. Quota, recorder failures and unfinished transports mark capture incomplete without changing model behavior. Recording is disabled during ordinary app use. These are diagnostic traces; they do not supply the exact sampled token IDs/probabilities needed for the proposed RL pipeline.

## Offline replay before new trials

```text
.runtime/python/python.exe -X utf8 evaluations/navigation-study.py replay --input .data/v0.0.11-generalization-pilot --output .data/navigation-replay
```

The initial replay of the saved v0.0.11 trials found 92 actions after the 9B hashing attempt's last passing development check, with no subsequent runtime edit recorded through the file tools. Its reads included 12,990 overlapping characters out of 49,331 returned. The staged audit had 119 reads and three searches, with 9,310 overlapping characters out of 30,823 returned. These observations motivate the comparison; they do not show that an outline will improve completion. The replay invokes no model.
