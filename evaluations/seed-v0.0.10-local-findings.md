# Local Qwen3.5 9B seed experiments — 15 October 2026

Qwen can now produce useful, independently checked seed extensions. Reliability
still varies: one prospective batch achieved three accepted summaries in three
fresh attempts, while the final broader validation accepted three of six
attempts. These results do not establish reliable general self-improvement.

The shared helpers, checkpoint fixes, instructions and evaluation changes are
**Codex-authored**. Qwen authored the candidate tools and their new tests.
No candidate was promoted into the protected starter or executed on the host.

## Method

- Windows host, GTX 1080 Ti with 11 GiB VRAM; inference used the existing managed
  Ollama 0.40.4 and cached
  `hf.co/bartowski/Qwen_Qwen3.5-9B-GGUF:Q4_K_M`.
- Independently checked main weight SHA-256:
  `d784ce9eda1a5a7b51e8f705a9e6310844bf4f173654d115823c775fdea56d43`.
- Commands, candidate tests, independent probes and public-tool verification ran
  inside disposable network-free Linux VMs under WHPX. Native execution and
  hosted providers were not used. Saved app preferences were not changed.
- Each feature attempt began from its batch's frozen source and a fresh task.
  “First pass” allows the model to test and repair its own work within that run;
  it does not mean its first patch was correct. No operator repaired candidate code.
- Each attempt had 128 actions and 30 minutes. Acceptance required a completed
  run, runtime changes in the allowed files, a new focused test file, unchanged
  protected code, protected regressions, the entire candidate suite, independent
  boundary checks and fresh-worker public invocation. Documentation changes were
  optional. Finishing, format retries and normal cap enforcement were preserved.
- Changes and sampling settings were explored sequentially. This was not a
  randomized ablation study: source, context, sampling and the transport changed
  between some batches. The table is evidence, not a causal ranking.

## Fresh feature attempts

The two tasks added `file_summary` and `append_text`, including UTF-8 character
limits, byte counts, CRLF, path validation and rejected-write preservation.

| Frozen variant | Context / response | Temperature / thinking | Accepted |
| --- | --- | --- | --- |
| Original v0.0.9 baseline | 32K / 8K | 0.6 / on | 0/2 |
| Cutoff recovery and clearer recipe | 32K / 8K | 0.6 / on | 0/2 |
| Same recovery and recipe | 32K / 8K | 0.2 / off | 0/2 |
| Experimental separate extension registry | 32K / 8K | 0.2 / off | 0/2 |
| Original extension interface, more context | 48K / 4K | 0.6 / on | 1/2 |
| Separate repeats of that profile | 48K / 4K | 0.6 / on | 1/6 |
| Shared read helper, repaired checkpoint transport | 48K / 4K | 0.6 / on | 3/6 |
| Explicit character units and shared read/write API: pilot | 48K / 4K | 0.6 / on | 1/2 |
| Same API: larger-context pilot | 64K / 4K | 0.6 / off | 2/2 |
| Same API/profile: separate repeatability batch | 64K / 4K | 0.6 / off | 3/6 |

That is **11 accepted attempts out of 32**, across different experimental
conditions. This pooled number is not the final seed's success rate. The read
helper batch accepted all three summaries and none of its three append tools;
the final batch accepted two summaries and one append tool. Its other attempts
modified a protected test file, encountered a provider/runtime interruption, or
timed out. The successful pilot therefore did not generalize to six clean repeats.

The 64K profile fit entirely on the GPU according to the engine's placement
report: `size == size_vram == 7964196862`, with a 65,536-token context. This is
one measured model/hardware combination, not a universal setting recommendation.
Global defaults and thinking preferences remain model independent.
The prepared starter's fingerprint is
`bea9b0c7b10cccc08812816b070cce7283679326cdfac86f695afe9b8140b0d4`,
identical to the frozen text-API source used in those last three batches.

Some failures belonged to the harness. A baseline summary implementation passed
the independent feature checks but its run ended on an output cutoff. A later
attempt hit a disappearing temporary-file error. Repeated full-state transfers
also exhausted the wire quota. Two later runs stopped with connection-category
provider errors; engine logs showed output-budget exhaustion near those times,
but the exact provider exception was not retained. Their cause is unresolved.
The new diagnostic client preserves future errors and the actual supplied tool
schemas privately. None of these interruptions should be treated solely as a
model coding failure.

## Further growth and actual use

Two accepted summary candidates received an audit task requiring a missing
append capability. The first exploratory task contained conflicting completion
instructions; its failures remain recorded. The staged version separated
implementation/testing from activation and final use.

Both staged candidates produced working append implementations while retaining
the original summary capability. One initially failed the scope grader because
it reused a disposable `sample.txt` carried over from its earlier seed. The
grader now permits text fixtures and documentation to change while protecting
existing test code, the loop and the runtime edit scope. The unchanged candidate
then passed the independent checks. Its original rejection is preserved, with
the corrected assessment recorded separately; this is not another fresh attempt.

After activation, both candidates completed the audit with correct JSON, exact
log bytes and unchanged input. They used the command-line development interface
instead of the requested direct public calls. The strict cumulative-use check
therefore **remained failed**. Explicit activation feedback fixed the earlier
repeated restart request, but did not eliminate that routing habit.

In two subsequent fresh tasks, the unchanged combined seed directly called both
new native tools, with terminal access enabled and disabled. Both produced the
correct summary. Only the terminal-disabled task passed the complete artifact
check: the other appended a literal escaped newline instead of the requested
newline. This confirms that new tool schemas reach the model and are usable,
while leaving a concrete reliability limitation. It does not rescue the failed
cumulative-use verdicts or prove repeatable unattended growth.

## Changes retained for v0.0.10

- Reuse bounded `Workspace.read_text` and `Workspace.write_text`; preserve CRLF
  and make the Unicode character limit explicit. Keep `WRITE_LIMIT` as a
  compatibility name. No task-specific tools are preimplemented.
- Keep the original implementation/definition interface. The extra extension
  registry did not help and was not adopted.
- Discard incomplete responses and share the existing bounded format-repair
  loop with recognized output cutoffs. No partial action executes.
- Transfer changed history tails and validate the reconstructed state without
  increasing transfer/state limits or dropping the saved journal. Ignore hidden
  transient test directories and tolerate files disappearing during export.
- Tell a resumed agent when its edited seed is active, list its available tools,
  and distinguish direct use from pre-activation development checks.
- Package and independently protect the shared-helper tests as well as the
  original regressions; fingerprint the complete protected test bundle.
- Preserve settings/source/task identities and improve experiment diagnostics.

The final Windows suite passed: **158 tests, 16 platform-specific skips**,
including real VM boundary, recovery, long-history and cumulative restart tests.
Linux guest execution was exercised; a Linux-host or macOS run was not performed.
Final grader calibration rejected absent tools and accepted known-correct tools
and fresh-worker public invocations. Benchmark engines and VMs were closed.

The compact [results](seed-v0.0.10-local-results.json) retain all 32 original
feature verdicts and the separate growth/usage outcomes. Exact source packs,
candidate diffs, journals, full reviews and historical snapshots remain under
`.data/qwen-overnight-20261015/`. These findings accompany v0.0.10.

The practical gain is a simpler reusable text API and removal of real harness
interruptions. Qwen can make small seed improvements; consistent, broad
autonomous improvement remains unproven.
