# Local v0.0.14: Qwen3.5 9B first- and second-pass rerun

Date: 2026-10-17 (America/Regina). Local uncommitted changes on `4edc8ad`. The observed acceptance rates did not improve in this batch: 2/3 first upgrades and 1/2 complete second-pass workflows. Both second extensions passed independent verification and preserved the earlier capability; completion remains a separate requirement.

## Local changes

- The seed recipe and short shared guidance require checking omitted optional arguments against the user contract, applying defaults in code and keeping schemas consistent.
- After same-task activation and subsequent Resume, the protected controller supplies the active bundle identity and fulfilled activation state. The default seed budgets this as trailing runtime context, preserving the opening prefix and original human instructions. It adds no tool or host permission.
- Recognized malformed native arguments and oversized batches use the existing two-retry response repair path. Rejected responses execute no actions. Host request/response/action limits remain; only fixed hints reach the guest. Host observations retain bounded error details, redacted before truncation.

## Frozen live batch

Starter SHA-256: `4c5dbd99eeac318475bab5d4fe92ac5ffdb6f0b17bd418bd9533d306aacd0224`. The cached Qwen3.5 9B Q4_K_M checkpoint, managed Ollama, production adapter, 128K context, 4K responses, temperature 0.6, top-p 0.8, top-k 20, thinking off, flash attention and q8_0 cache match the previous profile. No call-ID rewriting, weight changes or saved preference changes. Upgrade limits remain 30 minutes, 65,536 generated tokens and 128 actions. Basic tasks have 240 seconds / 8,192 generated tokens. Each accepted first source receives one fresh second-extension task; development and activation share its allowance. Candidates execute only in disposable network-free VMs.

| Batch | Basic tasks | Verified first upgrades | Fully accepted first upgrades | Verified second extensions | Complete staged growth |
| --- | ---: | ---: | ---: | ---: | ---: |
| Previous v0.0.13 | 5/5 | 2/3 | 2/3 | 2/2 | 1/2 |
| Local v0.0.14 | 5/5 | 2/3 | 2/3 | 2/2 | 1/2 |

These are single batches with different model-generated candidates, not a controlled estimate of the effect of each change. They do not establish repeatability or a reliable route to 3/3 and 2/2. Familiar file-tool contracts also limit generalization claims.

| First upgrade | Accepted | Actions / reads | Model-task seconds | Reported generated tokens |
| --- | --- | ---: | ---: | ---: |
| sha256_file | True | 31 / 10 | 208.28 | 4285 |
| csv_preview | False | 70 / 38 | 449.08 | 11587 |
| format_json | True | 128 / 95 | 598.29 | 13830 |

CSV still fails omission of limit: its schema now marks limit optional, but its implementation validates args.get("limit") without applying the requested default. Its own suite passes because it does not exercise that call. An additional audit also confirmed an off-by-one truncation bug for exactly limit+1 records. The existing public invocation check also failed; the feature probe previously missed the limit+1 cases. The model-written candidate was left unchanged.

## Second-pass outcomes

| Parent → added tool | Verified and prior retained | Final status | Native use of both | Exact final artifacts | Complete workflow |
| --- | --- | --- | --- | --- | --- |
| sha256_file → format_json | True | paused | True | True | False |
| format_json → sha256_file | True | completed | True | True | True |

The hashing-parent continuation used both activated tools, then consumed its action allowance instead of finishing. The formatting-parent continuation completed. Runtime state was present in activated model requests, and verified source remained unchanged during final use. Separate fresh-use diagnostics, when present, remain separate from staged-workflow scores.

## Grader correction and validation

After inference finished, the CSV feature probe gained exact limit+1 checks at limits 1, 5 and 20, including unchanged input bytes. A deliberately faulty truncation reference must fail exactly those cases while all other behavior and its suite pass. Original frozen model results remain untouched. All three saved first candidates and both combined candidates were regraded without inference; the acceptance and verification outcomes were unchanged.

Final full Windows validation: **200 passed, 16 platform skips (216 total)**, including **all 23 real VM tests**. This includes bounded protocol repair with no partial actions, host quota retention, secret redaction, activation state across Resume, human-instruction preservation, input budgeting, and the new CSV negative control.

The first separate CSV audit script failed before producing its artifact; the guest import path was corrected and both control and unchanged candidate were rerun. Those probe records are preserved separately from model outcomes. No seed/controller code changed during inference; the post-run grader change and source regrading are explicitly recorded.

Private evidence is in `.data/qwen9b-v0.0.14-20261017/`, including initial and final source patches, trusted runner snapshots, provider traces, candidates, journals, grading and GPU samples. Full validation logs are `.data/v0014-full-vm*.log`. The [validation record](seed-v0.0.14-qwen9b-validation.json) retains settings, costs and separate original/regraded outcomes. All changes remain local; no candidate was promoted and no commit or push was made.
