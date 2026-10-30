# 6K local-Qwen LoRA: completed gated screen

**The adapter improved validation loss but did not qualify for seed-editing
trials.** Its five ordinary task artifacts were correct, but two responses
omitted explicit completion. The unchanged base completed two independently
verified two-feature growth chains. The adapter's seed-editing ability remains
unmeasured: the predefined ordinary-task gate prevented those trials.

## Fixed design and outcomes

Both arms used the pinned Qwen3.5 9B Q6 weights/engine and starter
`645d2222c5f7f6e92ad5f2ca964f7584e07b47ea4d410872e98a61009eb7bb0d`, native
production connection, 128K context, 4K responses, temperature 0.6, thinking off
and requested seed 104729. Only the final one-epoch overlay differed. Every
cell started a fresh owned service with verified actual adapter state.
One repeat of five chain families was scheduled; this is exploratory evidence.

| Measure | Base Q6 | Final one-epoch LoRA |
| --- | --- | --- |
| Inference/protocol screen | Passed | Passed |
| Ordinary task artifacts | 5/5 correct | 5/5 correct |
| Ordinary tasks explicitly completed | 5/5 | 3/5 |
| First extensions attempted / scheduled | 5/5 | 0/5 — gated |
| First packages accepted | 2/5 attempted | Not tested |
| Correct use after first activation | 2/2 activated | Not tested |
| Second extensions accepted | 2/2 attempted | Not tested |
| Correct cumulative use after second activation | 2/2 activated | Not tested |
| Complete functional chains | 2/5 scheduled | Not measured — gated before upgrades |

The gate requires the protocol screen plus at least four of five ordinary tasks.
All five LoRA chains remain **not run**, not five failed upgrades. There were 19
completed launched cells and 13 skipped stages: three base second stages and all
ten LoRA feature stages. No model attempt was retried, no follow-up instruction
supplied, and no candidate repaired by the operator.

## Failure audit

The LoRA wrote and read back the exact greeting and Unicode files, then replied
in plain prose saying each task was complete. Both raw responses had
`tool_calls: []`; neither called `finish(status="completed")`. The production
adapter correctly preserved these as plain replies and paused the sessions.
The other three tasks completed normally. These failures involved neither
incorrect file contents, malformed tool arguments, timeouts nor token exhaustion.

The base model's **hash → formatting** and **CSV → hashing** chains passed
package checks, first use, second extension, retention and cumulative fresh use.
All required tools were called natively, defaults were actually omitted and
first-task artifacts were preserved. Read-only re-auditing of saved bytes and
post-activation journals confirmed all four successful activated stages.

Its three rejected first packages were:

- **Formatting:** modified protected `file_ops.py` and left a development fixture
  inside the harness. Scope/protection rules rejected the package before feature
  qualification; that rejection does not establish formatter correctness.
- **INI:** passed all feature, public-use and protected regression checks, but
  added a third runtime module outside the requested two-file edit scope. This
  is working feature evidence with a submission-contract failure, not an accepted
  package or a VM escape.
- **Newlines:** passed public/default use but failed CRLF and Unicode boundaries.
  Static source inspection found an output limit measured in UTF-8 **bytes**
  instead of characters, and sequential replacement that doubles CR while
  converting bare CR to CRLF. Hidden checks correctly rejected it. No hidden
  feedback reached the model.

The audit read serialized evidence only; it did not execute candidates or rerun
failures. No command-route false negative explains these scores.

## Training and matched-success efficiency

The one-epoch run completed 93 ordered updates in 80.8 supervised minutes,
with all 496 gradient tensors finite per update, verified final checkpoint and
no resource trips. Validation NLL improved **18.7%**, workflow-bucket macro NLL
**19.5%**, while ordinary-task NLL worsened **37.1%**. Loss gains are not task
success. See [training findings](local-lora6k-training-2026-10-30-findings.md).

Three ordinary tasks passed fully in both arms: precise edit, recovery and bug
fix. Their complete measured totals were:

| Matched-success cost | Base | LoRA |
| --- | ---: | ---: |
| Model calls | 15 | 14 |
| Input tokens | 34,030 | 31,723 |
| Output tokens | 992 | 1,074 |
| Task wall seconds, excluding fresh service load | 77.995 | 89.592 |

Fewer calls accompanied more output tokens/time here. Three pairs do not
establish a general speed effect. No matched seed-editing cost comparison exists.

## Provenance and closure

The separate GGUF adapter passed static mapping and disabled/enabled/disabled
probability controls through raw completion and native chat, with exact disabled
restoration and slot erasure. Overlay state verified on all 19 study launches:
13 base and six LoRA. An initial checksum-publication error occurred before any
agent trial; its records are preserved, and the corrected publication reused
identical cases and limits. This is infrastructure history, not a model retry.

All 19 cleanup receipts report stopped owned processes. The final host check
found no matching owned trainer/study/model process, QEMU process or listener on
port 47848; GPU utilization was zero. Base/adapter assets, source, graders and
reviewed dataset hashes verified unchanged. No deployment, merge, extra epoch,
cloud call, download, commit or push occurred.

**Do not promote this adapter from these results.** A separately authorized
diagnostic could investigate explicit completion and, if declared beforehand,
measure extensions without the ordinary gate. More epochs are not an established
remedy. The full gated comparison is closed; no extra studies were launched.

Private evidence: `.data/lora6k-pilot-20261029/post-training-20261030/`, including
`STUDY-CLOSED.json`, `outcome-audit.json`, `closed-study.json/.md`, and all original
`study-v2/` sources, checks, transcripts, artifacts and skipped-cell reasons.
