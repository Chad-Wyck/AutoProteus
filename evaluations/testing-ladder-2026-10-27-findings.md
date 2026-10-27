# Testing ladder — first recorded pass, 27 October 2026

Machine-readable receipts: `testing-ladder-2026-10-27-results.json`
(this folder). Harness: `testing_ladder.py`. Protocol: the project's own
frozen completion study (`completion_study.py` — prepare → calibrate →
run, check-only before any inference). Environment: Linux x86-64,
Python 3.12.3, upstream v0.14.1 (commit c2c7d13). **No model inference was
started in this pass, and no money was spent.**

## What genuinely ran

| Rung | Preflight | Prepare | Calibrate | Live run |
| --- | --- | --- | --- | --- |
| local-tiny (qwen2.5:0.5b) | endpoint-unreachable | **prepared** — frozen plan + plan.sha256 recorded | **attempted — blocked** (below) | not attempted |
| local-default (qwen3:4b-instruct) | endpoint-unreachable | **prepared** — frozen plan recorded | not attempted | not attempted |
| local-large (qwen2.5:14b) | endpoint-unreachable | **prepared** — frozen plan recorded | not attempted | not attempted |
| hosted-top (rented engine) | spend-gated, not probed | not prepared | not attempted | **designed, not built out** |

## The two gaps, exactly as recorded

1. **No local inference endpoint on this machine.** Preflight is a
   model-listing call (not inference). All three local endpoints answered
   the same way: `http://127.0.0.1:11434` — connection refused. There is
   no Ollama service and no downloaded model on this box, so no rung
   could start a live trial here.
2. **Calibration is blocked by absent hardware virtualization.** The
   check-only calibration for local-tiny ran the study's own machinery;
   its regression arms recorded, verbatim: *"Hardware virtualization is
   unavailable. Enable virtualization in your computer firmware, or
   enable nested virtualization on your VM…"* — and the grader controls
   could not execute a guest. The failure detail is preserved by the
   study itself in `calibration-failure.json`. This is the same limit
   that makes the ordinary suite skip its 49 VM-dependent tests on this
   machine; per standing instructions, no native-mode fallback was used.

## What a live pass needs

- A host with hardware virtualization (KVM or WHPX), like the prepared
  runners the VM workflow already describes;
- A local inference endpoint (Ollama) with the rung's model downloaded;
- Then, per rung: `testing_ladder.py calibrate --rung <id>` followed by
  `testing_ladder.py run --rung <id>`. Receipts land per rung either way.

## The top rung

`hosted-top` is a rented, production-grade engine — the qualification
test that has failed twice. It is deliberately **designed but not built
out**: the harness refuses to probe, prepare or run it without explicit
spend approval with the amount named beforehand (at the study's budgets,
roughly tens of dollars per full pass). No spend is committed by this
report, this harness, or this rung existing.
