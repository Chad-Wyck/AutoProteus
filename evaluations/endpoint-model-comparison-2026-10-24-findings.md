# Private endpoint model comparison — October 24, 2026

Two of the five requested models completed the same paired two-extension test. The endpoint then replaced its catalog, and the three requested Qwen3.5 IDs are absent. **No complete two-extension chain passed.** The Qwen3.8 Q8 model produced more independently verified first extensions, but only one eligible second stage.

| Advertised model | Arm | Hash package verified / 3 | Complete first workflow / 3 | Second attempts | Verified second extension | Complete chains / 3 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Qwen3.8 9B Q4_K_M | Current baseline | 0 | 0 | 0 | — | 0 |
| Qwen3.8 9B Q4_K_M | Activation history | 1 | 0 | 0 | — | 0 |
| Qwen3.8 9B Q8_0 | Current baseline | 2 | 1 | 1 | 0/1 | 0 |
| Qwen3.8 9B Q8_0 | Activation history | 2 | 0 | 0 | — | 0 |

The one eligible inventory extension failed `optional_argument_schema`. Its existing capabilities and final input were not replaced with a repaired or supplied parent. The remaining first-stage failures were either incomplete extension packages or failures of final use. Two Q8 first stages saved and inspected correct artifacts but did not invoke the new hashing tool after activation; pre-existing development output does not satisfy the full tool-use workflow. Correct saved data, independent package verification, actual activated-tool use and explicit completion are scored separately.

The Qwen3.5 Q4_0, Q8_0 and UD-Q8_K_XL models received no scored seed attempt. Their initial setup-only READY requests exhausted an overly small 64-token response allowance with no visible content. That is not evidence of coding inability. A separate setup continuation restored the ordinary 4096-token response allowance, but discovery then showed those IDs had disappeared. The completed Qwen3.8 trials were preserved and never rerun. The endpoint now advertises Swift, Cyber-Tiel and Gemory configurations; testing those is a scope change awaiting the human's selection.

## Method and reproducibility

The source was frozen from committed **v0.10.0**, `f160ec7b41ab8876acd17e79599d954b1b371d56`. Each model had three paired baseline/history chains in A/B, B/A, A/B order. Each fresh first stage had to add/register `sha256_file`, pass independent feature/package/protected checks, activate, save the exact receipt using the activated tool, inspect it and finish completed. Only a fully successful first workflow admitted the same session and exact grown seed to the inventory extension. That second stage had to preserve hashing and prior tests, verify/activate `inventory_files`, and use both tools to produce checked inventory/hash-audit artifacts with documented defaults and intact inputs.

Each extension shared 60 minutes, 128 actions and 65,536 generated tokens across development, grading, retention, activation and final use. The host requested 131072 context, 4096 response tokens, temperature 0.6, terminal access, the production native adapter and no guest internet. The hosted adapter directly sends model ID, temperature, output cap and native tools. Actual server context, weight hash, engine, hardware, KV precision, top-p/top-k, thinking, adapters and cache state could not be independently verified. These are advertised model configurations, not verified publisher checkpoint identities. No remote server administration or cache clearing was performed.

All candidate code and verifiers ran in local disposable network-free Windows WHPX VMs. The 58 trusted source hashes were preserved. Both starter suites, thirteen constructed semantic controls and four saved real-candidate controls passed. Actual VM/worker/broker delivery was calibrated for the v0.10.0 concise-handoff path: the baseline's protected fallback inserts activation state before the original task; the history arm preserves it beside the activation boundary. Both retain exactly one state and the latest observation at the tail. The inherited older tail-position assertion was replaced before live inference; protected feature graders were unchanged. The original completed semantic-control receipt was source-bound and reused, rather than repeating model trials.

The inherited resource guard initially stopped before any calibration or model call because D: had approximately 95 GB free, slightly below its 10%-plus-margin rule. The owned study's disk reserve was declared as max(20 GiB, 5% of the drive plus 256 MiB). Setup stops and pre-inference manifest revisions are retained. They are not counted as model-trial failures or retries. Source packs have identities `2b54281cac388a6d40b380332277ea97befd42cccd206c3db3fcc417f1fa12a1` and `6eadaf55696980ad86168f05c14359f066c04d74be76fea9cf7e29507f40de4c`.

## Saved results and limits

`results-so-far.json` retains each stage's actions, time, independent failures, activated-tool usage, token/measurement completeness and evidence hashes. Raw plans, calibration, provider requests/responses, journals, source packs, candidate reviews and checkpoints are under `.data/endpoint-five-models-20261024/snapshot/.data/five-model-endpoint/`. The separate setup continuation is under the adjacent `five-model-endpoint-continuation/`. The canonical request IDs were explicit; generic `default` aliases were never used.

First-stage success rates retain all three scheduled chains per arm. Second-stage denominators are conditional; not being eligible is not a failed second-stage attempt. The unavailable Qwen3.5 models receive no coding failure score. No matched successful two-extension chain exists, so lower elapsed time or token use cannot establish success-conditioned efficiency. Three repetitions are exploratory, with no default promotion or candidate repairs. The user-owned endpoint remains running; this study owns no inference service to shut down.
