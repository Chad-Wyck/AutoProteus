# Weights and Training: agent starting instructions

Read this file first, then [the current report](docs/weights-and-training/REPORT.md)
and [the experiment protocol](docs/weights-and-training/PROTOCOL.md).

**Question:** can a frontier agent edit a teacher's numerical weights so that the
teacher becomes better at editing separate student models? No downstream
improvement has yet been demonstrated. This branch provides research code, CPU
controls, a candid evidence summary and a protocol for a new independent test.

**4B and 0.4B are example test sizes, not required sizes.** The models actually used
in the reported local work were **Qwen3.5-4B Q8_0 teacher/editor** and
**Qwen3.5-0.8B student/target**. There is no reported 0.4B run. Different teacher
and student sizes, families and quantization formats may need testing. A result
on one pairing must not be generalized to another.

## Start with CPU controls

From a fresh checkout of this branch, use a separate Python 3.11 environment:

```powershell
py -3.11 -m venv .venv-wt
.\.venv-wt\Scripts\python.exe -m pip install -r docs/weights-and-training/requirements-cpu.txt
.\.venv-wt\Scripts\python.exe -B tools/wt_cpu_checks.py
```

Installing packages requires network access. The check command itself runs
synthetic CPU controls: no model downloads, GPU inference, VM boots, training or
frontier API calls. It writes disposable fixtures under ignored `.data/` and
prints the actual pass/fail/skip count. A pass verifies engineering contracts;
it is not a teacher or student capability result.

## Instructions for the receiving agent

1. Record the branch commit and read the report's status table. Do not combine
   scores from different versions, task sets, prompts or model artifacts.
2. Run CPU controls. Review the source map and portability gaps in
   [SETUP.md](docs/weights-and-training/SETUP.md). This is not a complete portable
   one-command live benchmark: historical preparers reference private predecessor
   publications which are deliberately absent.
3. Agree a new run budget and model/download/API access with your own owner.
   Make a fresh experiment directory and manifest. Never copy another owner's
   authorization, receipts, leases or private traces. Public-source preparers
   default generated execution-authorization flags to false; this branch grants
   no live permission. Design a new run rather than reenabling an old grant.
4. Acquire checkpoints directly from their permitted sources; pin revisions,
   licenses, hashes, conversion commands and dependencies. Keep original files
   immutable and use separate teacher/student copies. Do not upload weights.
5. Implement and freeze the matched comparison in PROTOCOL.md. Verify the actual
   runtime, tokenizer, sampler, numeric broker and isolated execution route before
   allowing any model-authored code to run. New platforms need new qualification.
6. Let the frontier agent design a bounded teacher intervention using development
   evidence only. Freeze the resulting teacher before opening student outcome
   holdouts. Compare it with an untouched teacher using identical tools, tasks,
   seeds, budgets and fresh student copies. Evaluate final student artifacts
   independently. Include no-edit and numerical/quantization controls.
7. Report failed, interrupted and unrun work as well as completed work, costs and
   preservation losses. Use [REPORT_TEMPLATE.md](docs/weights-and-training/REPORT_TEMPLATE.md).
   A synthetic fixture gain or shorter reasoning is insufficient for advancement.

The receiving agent may propose larger or smaller model pairs, but must explain
the resource consequences and create a separate registered comparison. Training,
distillation and self-editing are separate experiments with their own controls.
The name "Weights and Training" does not mean these local studies trained models.

## Scope of this branch

The code is opt-in research outside AutoProteus's editable starter seed.
Model files, raw responses, hidden cases, numerical patch payloads, approval
records, dependency wheels, native DLLs and VM images are not distributed here.
The [source manifest](docs/weights-and-training/SOURCE-MANIFEST.json) records the
copied files and the private reports used for the public summary.
See [AUDIT.md](docs/weights-and-training/AUDIT.md) before publication.

Prepared locally on November 4, 2026. A local Git branch is not a GitHub
publication; publication is pending owner approval.
