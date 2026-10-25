# Qwen 9B matched historical replay and edit-feedback pilot — October 24, 2026

**The current seed reproduced 3/3 independently verified extensions on the earlier
CSV-to-hashing task. Both old and current runtimes completed 0/3 final workflows.**
The newer directory-inventory failures did not establish a regression on this
familiar hashing extension. This replay supplies no reason for a wholesale rollback.

| Three matched repeats | Old v0.4.0 runtime | Current runtime |
| --- | ---: | ---: |
| New hashing behavior passed | 3/3 | 3/3 |
| Independently verified packages, including scope/tests/public use | 2/3 | 3/3 |
| Existing CSV retained | 3/3 | 3/3 |
| Final input preserved during development | 2/3 | 3/3 |
| Independently activated | 1/3 | 3/3 |
| Correct final audits among activated attempts | 0/1 | 0/3 |
| Complete workflows out of scheduled attempts | 0/3 | 0/3 |

These are **supplied-parent directed extensions**, not autonomous two-upgrade
chains. Both parents received the same human reference CSV capability, its test
and the portable common 50-case protected overlay. They are controlled overlaid
runtime bundles rather than exact shipping releases. The normal root starter
remained unchanged throughout the frozen runs. Three repeats are exploratory;
this cannot establish broad self-extension reliability or a universally better seed.

## What actually failed

The first old-runtime candidate passed hashing, public invocation and regressions,
but put audit.json inside harness/, outside the declared file-tool edit scope.
Its demonstration used a separate scratch sample there. The second old candidate
had a verified package but changed the final sample.txt during development, so
activation was withheld. The third old candidate activated and saved two rows.

All three current candidates passed independent package checks, retained CSV,
preserved the original inputs, activated, used both tools directly and explicitly
finished. Each audit had the correct path, byte count, SHA-256 and truncation
flag. **Rows alone failed: two were saved instead of the required default five.**
The activated old candidate made the same mistake. Coding the extension and
completing the original task remain distinct outcomes.

## Separate one-pair edit-feedback pilot

After the primary replay, one additional baseline attempt was paired with a
copied-seed variant returning bounded context after successful source edits.
Both used task 1 and the same current supplied CSV parent. Extra pilot observations
are not pooled into the primary three-repeat success rates.

| One attempt per condition | Baseline | Edit feedback |
| --- | ---: | ---: |
| Independently verified extension | 1/1 | 1/1 |
| Activated | 1/1 | 1/1 |
| Correct final audit / complete workflow | 0/1 | 0/1 |
| Total model calls | 26 | 130 |
| Known generated tokens | 4,881 | 12,150 |
| Trial seconds, including checks/use | 400.616 | 1,008.269 |

The baseline again saved two rows. The treatment spent 17 development actions,
then used all 111 remaining actions after activation. Its final stage called
csv_preview(path="sample.txt", limit=2) **107 times**, never saved audit.json and
paused at 128 total actions. No 60-minute or generated-token ceiling was reached.
This is a concrete coordination failure, not evidence that more editing feedback
improves completion. One pair cannot establish that edit feedback caused harm.
Keep it opt-in and do not promote it based on this pilot.

## Fixed setup, costs and limits

Qwen3.5 9B Q6_K, no LoRA, 131072 context, 4096 responses, temperature 0.6,
top-p 0.8, top-k 20, thinking off, Q8 KV cache and the pinned PrismML CUDA 12.4
engine on the GTX 1080 Ti. Native calls used the production ModelClient without
custom call-ID rewriting. Network access was explicitly disabled for these tasks.
All candidate execution and grading ran in disposable Windows/WHPX VMs.

The exact earlier public tasks and fixture bytes were reused, with alternating
old/current order. Each attempt shared 3600 seconds, 128 actions and 65536 generated
tokens across development, independent checks, activation and final use. Slot
state was explicitly erased between attempts. Automatic GPU offload flags were
fixed; per-layer residency was not independently guaranteed. Connection
qualification passed in eight requests with no format repair. No operator
candidate repair, final-task coaching or model-trial retry occurred.

| All-attempt primary costs | Old runtime | Current runtime |
| --- | ---: | ---: |
| Model calls | 102 | 95 |
| Reported input tokens | 1,152,308 | 962,737 |
| Reported generated tokens | 17,349 | 16,669 |
| Trial seconds | 1,516.265 | 1,478.209 |

All eight upgrade/pilot traces have complete call/usage capture, with no dropped
records or observer failures. Total: 353 calls, 51049 generated tokens and
4403.359 trial seconds. Input-token totals include cached prefixes and are not
uncached compute. Model loading is separate and not reported by every provider
call. There are no matched complete workflow successes, so the lower current
aggregate cost is **not** a success-conditioned efficiency result.

Parent suites/CSV behavior and semantic grader controls passed before inference.
A scripted schema-control admission check and its first recheck expired waiting
for the shared VM lease, before any action/model request. Both timeouts remain;
a sequential recheck detected the intended schema defect before model admission.
An earlier user-requested startup stop happened before model readiness and before
any trial. It is archived separately, not counted as a model failure. On resume,
source/runner/appliance identities were verified and completed checks reused.

## Software and evidence

The local v0.9.0 changes add the protected message-limit correction, read-only
observation/evidence display, explicit persistence outcomes, generated recovery
schedules, historical evidence indexing and separate discovery/profile studies.
Relative to the prior v0.8.2 working tree, the editable seed gained no new tools
or instructions; its version changed. Older uncommitted additions are documented
under their earlier versions. Larger library/training/Mac projects remain deferred.

Final ordinary regression suite: **388 tests, 339 passed, 49 skipped**. The real
VM suite ran **26 tests: 25 passed, one live-public-web check skipped**. JavaScript
syntax checks and git diff whitespace validation passed. A later research-runner
fix converts missing/malformed discovery handoffs into explicit unverified
submission outcomes; it did not alter these frozen tasks or rescore any candidate.

Frozen sources, profile, original tasks, trusted runner copy, raw calls, reviews,
checkpoint bytes, interruption records and cleanup are retained under
`.data/refinement-v090-20261024/`. All owned test model services finished and stopped.
See the matching results JSON for exact identities and per-attempt metrics.
