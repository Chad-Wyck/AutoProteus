# AutoProteus v0.4.0 local studies — 22 October 2026

Tests used the GTX 1080 Ti (11 GiB), Windows/WHPX disposable VMs, the pinned PrismML CUDA 12.4 runtime, and the standard production inference adapter. No candidate Python was imported or executed on the host.

Frozen application commit: `f37b1d9eb781af4defcb4c72d508f91d708096de`. Starter fingerprint: `cc065155ce4f258d6918df2229a4b34e5ee7701395207097e28a4b7cd7ae8cbd`.

The base Qwen remains the stronger control in this batch: it earned two accepted first upgrades and two verified second extensions. No tested profile completed a correct second-extension workflow. The existing LoRA and final-contract reminder established no workflow improvement here. This small study does not establish a universal model or adapter ranking.

## First extensions and conditional growth

| Profile | Ordinary tasks | Accepted first upgrades | Verified second extensions | Complete second-extension workflows |
|---|---:|---:|---:|---:|
| base-q6 | 5/5 | 2/3 | 2/2 | 0/2 |
| adapter-q6 | 5/5 | 0/3 | Not run | Not run |
| bonsai2-27b-pq2 | 4/5 | 1/3 | 0/1 | 0/1 |
| qwen35-4b-q4_k_m | Not run | Not run | Not run | Not run |

First contracts are hashing, JSON formatting and CSV preview. Each accepted first source receives a new task adding a second capability, preserving the first, and using both after independent activation. Different attempted task sets must not be treated as a model ranking. The 4B profile is a reserve.

The 4B reserve was not started because the remaining batch time could not fund a full trial. Bonsai's second extension and its formatter/CSV first attempts exhausted the shared deadline before independent grading could launch; those candidates remain unverified.

A verified package requires independent behavior, the candidate suite, protected regressions, public invocation and allowed source scope. Complete growth additionally needs the required stage order, retained behavior, unchanged activated source, correct final artifacts, observed use of both capabilities and explicit completion. Native routing is also scored separately.

## Supplied-parent handoff comparison

| Profile | Handoff | Verified extensions | Activated | Correct final artifacts | Complete workflows |
|---|---|---:|---:|---:|---:|
| base-q6 | baseline | 3/3 | 3/3 | 0/3 | 0/3 |
| base-q6 | final-contract | 3/3 | 3/3 | 0/3 | 0/3 |
| adapter-q6 | baseline | 2/3 | 2/3 | 0/3 | 0/3 |
| adapter-q6 | final-contract | 1/3 | 1/3 | 0/3 | 0/3 |

The factorial independently switches the existing workflow LoRA off/on and baseline/final-contract handoffs, with three fresh public CSV fixtures per condition and counterbalanced order. The reminder repeats only the original final-task paragraph after activation. It supplies no hidden answers. Both arms start from one human-reference CSV parent rebased onto v0.4.0; these attempts earn **no autonomous first-upgrade credit**.

Of 9 activated candidates, 9 saved a two-row preview instead of the requested default five. 9 preserved the input and had matching path, bytes, SHA-256 and truncation fields. This posthoc byte/field audit does not alter the original verdicts.

This is a narrow directed-extension study, not broad self-improvement or capability-discovery evidence. CSV implementation was absent from the adapter training corpus; hashing and formatter procedures were familiar. The current code and fixtures differ from historical experiments, and those results are not pooled here.

## Failure and budget distinctions

- `adapter-q6_first_01_sha256_file`: Behavior checks: 11/11; failures: none. Candidate-suite exit: 1; run status: paused; actions: 128.
  - AssertionError: ValueError not raised
  - ValueError: sha256_file requires an existing ordinary file
- `adapter-q6_first_01_format_json`: Behavior checks: 20/20; failures: none. Candidate-suite exit: 1; run status: paused; actions: 128.
  - AssertionError: ValueError not raised
  - ValueError: Invalid JSON: Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
- `base-q6_first_01_csv_preview`: Behavior checks: 34/35; failures: default_limit. Candidate-suite exit: 0; run status: completed; actions: 42.
- `adapter-q6_first_01_csv_preview`: Behavior checks: 31/35; failures: unicode_exact_1, unicode_exact_5, unicode_exact_20, default_limit. Candidate-suite exit: 1; run status: paused; actions: 128.
  - ValueError: Write a text string of at most 100,000 characters
- `bonsai2-27b-pq2_first_01_format_json`: No independent behavior verdict was available. Candidate-suite exit: None; run status: paused; actions: 76.
- `bonsai2-27b-pq2_first_01_csv_preview`: No independent behavior verdict was available. Candidate-suite exit: None; run status: paused; actions: 90.

4 completed records reached the shared deadline. A timeout with unlaunched independent checks is unverified, not a demonstrated behavior defect. Stopping/saving overhead is recorded separately. No failed live attempt was silently retried or operator-repaired.

- qwen: `adapter-q6_growth_01_sha256_file` — not_run: No accepted first-upgrade parent; second extension not attempted
- qwen: `adapter-q6_growth_01_format_json` — not_run: No accepted first-upgrade parent; second extension not attempted
- qwen: `base-q6_growth_01_csv_preview` — not_run: No accepted first-upgrade parent; second extension not attempted
- qwen: `adapter-q6_growth_01_csv_preview` — not_run: No accepted first-upgrade parent; second extension not attempted
- bonsai: `bonsai2-27b-pq2_growth_01_format_json` — not_run: No accepted first-upgrade parent; second extension not attempted
- bonsai: `bonsai2-27b-pq2_growth_01_csv_preview` — not_run: No accepted first-upgrade parent; second extension not attempted

## Expense and measurement coverage

| Condition | Calls | Trial wall minutes | Input tokens, known sum | Output tokens, known sum | Token measurements complete |
|---|---:|---:|---:|---:|---|
| base-q6/baseline | 306 | 54.7 | 4,090,847 | 35,315 | no — partial sums |
| base-q6/final-contract | 129 | 18.6 | 1,497,409 | 16,047 | yes |
| adapter-q6/baseline | 77 | 14.9 | 626,255 | 12,628 | yes |
| adapter-q6/final-contract | 191 | 24.0 | 2,731,814 | 19,555 | yes |

These totals include failures and describe expense. Logical input tokens include cached input and are not financial cost. A complete trace and complete usage/timing measurements are separate properties. There are no matched successful complete workflows in this factorial, so it cannot establish a full-workflow efficiency advantage. Phase timings and per-field coverage remain in the JSON.

## What blocked completion

- In the base Qwen hashing-to-formatter chain, the package passed independent checks but the model changed the final input during development. The required stage order failed, so activation was withheld.
- In the base Qwen formatter-to-hashing chain, both capabilities passed and activated, but the saved inventory remained unformatted and audit.json named sample.txt instead of inventory.json. Native calls and an explicit completion were insufficient to satisfy the requested outcome.
- The LoRA hashing and formatter first candidates passed every independent feature behavior case (11/11 and 20/20 respectively), yet their candidate suites failed. This separates successful tool behavior from inconsistent tests and unfinished development; the strict rejection is preserved.
- The supplied CSV-parent comparison repeatedly carried the earlier two-row demonstration into the final task, which required the default five-row preview. That is an observed artifact pattern, not proof that the demonstration caused it.

These observations support investigating contract retention, self-test quality and final-file verification. Keep the base Q6 control and the adapter experimental; do not promote the reminder on the basis of this batch. Broader changes or more training data need a separately frozen comparison.

## Reproduction and state

- Qwen and its adapter: the same pinned Q6_K deployment, 128K context, 4K responses, temperature 0.6, thinking off. The selected workflow adapter is epoch two; no training or merge occurred tonight. Runtime probability probes verified an effect and exact disabled-control restoration, with explicit cache erasure between arms.
- Bonsai: pinned PQ2_0, 128K context, Q4 KV cache, temperature 0.7, presence penalty 1.5 and thinking off. The 4B reserve uses Q4_K_M. Different runtime/sampling profiles do not isolate weight or quantization effects.
- Every extension has 128 actions, 65,536 generated tokens and 30 minutes shared across development, independent grading, retention, activation and final use. No upgrade starts without its full allowance remaining in the six-hour batch.
- The trusted VM bootstrap was refreshed before freezing. A real-VM smoke test delivered a literal human correction and queued follow-up, saved both requested files and recorded complete operation receipts. Scripted positive/negative grader calibration passed before inference.
- The user explicitly approved removing only the unused LFM Q8 and OxCoder Q4/Q5 weight files (21,107,291,360 bytes). Qwen, Bonsai, the 4B reserve, OxCoder Q6, adapters and all prior evidence were preserved. The disk guard retains 10% free space plus 3 GiB.
- No application settings, protected starter, sampling defaults or acceptance criteria were changed. No candidate was installed as the application starter. Findings remain local; no commit or push was requested.

Private frozen protocol and evidence: `D:\AI_New\AP\.data\overnight-v040-20261022`.

[Machine-readable results](seed-v0.4.0-night-2026-10-22-results.json).

## Final integrity and cleanup

The batch ran for 5.82 hours, from 05:05 to 10:54 America/Regina (11:05–16:54 UTC). The tracked starter, protected runner and frozen driver hashes still match the protocol. No hidden retries or operator candidate repairs were recorded. The model server, test VMs and driver are stopped; port 47841 has no listener. D: has 103.21 GiB free (10.82%), above the 10% plus 3 GiB reserve.

Full receipt: `.data/overnight-v040-20261022/final-validation.json`.
