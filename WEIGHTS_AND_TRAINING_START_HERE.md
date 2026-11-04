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

**Ready now:** inspect the included implementation and run the CPU checks below.
**Portable live W&T runs are not ready from this checkout alone:** the historical
research runners require a new preparation adapter and separately acquired,
qualified assets. Launching the ordinary AutoProteus app does not fill those gaps.

## Normal agent loop versus W&T research runner

| | Normal AutoProteus | Specialized W&T research |
| --- | --- | --- |
| Entry and control | The app/controller starts the editable `seed.py` and `autoproteus.agent.Agent` in the normal guest. The agent requests model actions, executes workspace tools, journals results and continues until it finishes, waits or is stopped. | A host study coordinator controls frozen arms, cases, prompts, budgets, gates and cleanup. Examples are `Study`, `TeacherStudy` and `FocusStudy` under `evaluations/`. |
| What the model changes | Task files and, when requested, its workspace copy of the Python harness/tools. Activating an edited seed is a separate controller operation. Harness self-extension does not by itself modify model parameters. | The editor can generate a complete fenced Python cell for a persistent NumPy guest. Numeric helpers read/save permitted tensors, checkpoint/restore candidates and request controlled evaluations. Frontier-authored teacher interventions and the later teacher/student comparison are separate stages. |
| Inference and feedback | The protected controller brokers the configured model connection, file transfers and permitted web requests. The seed uses its ordinary tool catalog and conversation loop. | Qualified native workers perform the specified editor/student inference outside the guest. A closed-schema numeric broker validates candidate operations; receipts bind tests to exact candidate contents/settings, and independent outcome grading stays outside the editor. Synthetic fixtures may return `protocol_stub` outcomes with no student inference. |
| Starting a run | Follow the normal [README setup](README.md#start), connect a model and prepare the normal isolated environment. | Requires a new experiment manifest and preparation adapter, model/runtime/image assets and W&T-specific calibration. There is no normal UI switch that launches this complete experiment. |

Source anchors: [seed entry](seed.py), [normal agent loop](autoproteus/agent.py),
[protected controller/broker](controller/isolation.py),
[research cell loop](evaluations/tensor_workspace_study.py),
[teacher stages](evaluations/tensor_workspace_teacher_stage.py) and
[focused study](evaluations/neuron_focus.py). Historical brief strings contain
different limits; each frozen manifest and its explicit contract determine that
study's actual settings. Do not copy an old brief's allowances into a new run.

## Shared isolation, different guests and protocols

Both routes use the project's diskless QEMU appliance/VM command, framed
transport and VM leases; the Windows W&T route also uses owned Windows Job
Objects for resource limits and process cleanup. The default VM command has no
host-drive mounts or direct guest NIC. Model connections remain host-side.
These are shared building blocks, not one interchangeable execution loop.

W&T's [TensorVM](evaluations/tensor_workspace_vm.py) reuses those controller
components but selects a separate [NumPy guest image](evaluations/tensor_workspace_image.py)
and [persistent kernel/helper protocol](evaluations/tensor_workspace_guest.py).
Model-written cells execute in that guest; the host accepts validated numerical
operations through [the broker](evaluations/tensor_workspace_precision.py).
The normal controller has its own guest and broker, including optional mediated
web access; the W&T numerical workspace does not inherit the normal web/tool
catalog. Preparing the normal appliance alone does not create the W&T image,
numeric interface, native inference configuration or frozen study records.
Do not replace the research guest with host Python execution.

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

The published baseline discovers **255 checks: 251 pass and four explicitly skip**
when the excluded private artifacts are absent. The skipped checks need the
private codec manifest, frozen ownership source or historical brief sources.
The included tests cover numerical-edit constraints, precise preservation,
candidate/restore receipts, grading contracts, budgets, ownership and memory
policies, using synthetic fixtures and controlled CPU child processes. They do
not establish real VM readiness, native codec/sampler parity, model capability or
an improved student. See [the recorded validation](docs/weights-and-training/VALIDATION.json).

These additional commands only show supported command-line syntax; they do not
start the app, load models or prepare a live experiment:

```powershell
.\.venv-wt\Scripts\python.exe -B app.py --help
.\.venv-wt\Scripts\python.exe -B evaluations/weight_repair.py --help
```

`weight_repair.py` is an offline reproduction-preparation CLI. Although its parser
lists `acquire`, `preflight`, `run` and `resume`, those commands deliberately stop
with an execution-hold error in this file. Other included historical research
modules do contain live code, so do not treat arbitrary entry points as inert.

## What a portable live W&T run still needs

1. **A fresh preparation adapter and manifest.** Current builders such as
   `tensor_workspace_prepare.py` and `neuron_focus.py` read specific private
   predecessor publications under `.data/`. Those records are excluded. Replace
   that dependency with a new, reviewed setup from explicit model/runtime paths,
   a new case/exposure inventory, data splits and registered budgets. Do not
   fabricate historical receipts or disable their checks to make a runner start.
2. **Permitted, pinned assets.** Acquire teacher/student originals, tokenizers,
   templates, datasets/golds, converted artifacts and compatible native engine
   binaries. Supply the separate research VM kernel/image and dependencies.
   The current research binding targets Windows x64/WHPX and a pinned native C
   ABI; the ordinary app's wider platform support does not qualify that binding.
3. **Real runtime qualification.** Validate VM isolation and helper contracts,
   tokenizer/sampler parity, numerical no-edit round trips, candidate test
   coverage, resource admission and owned cleanup on the receiving machine.
   Record the new dependency lock, hashes and calibration receipts for all arms.
4. **A new experiment and frontier workflow.** Choose the frontier model and
   access method, freeze its intervention budget and development-only evidence,
   then implement the matched untouched/edited teacher comparison and independent
   student/preservation grading in [PROTOCOL.md](docs/weights-and-training/PROTOCOL.md).
   No automatic frontier-provider integration or portable end-to-end launcher is
   supplied here. This is implementation work before live replication, not a
   promise that supplying weights or running CPU checks completes the setup.

Model/source pins, resource requirements and the implementation map are in
[SETUP.md](docs/weights-and-training/SETUP.md). The research directories and
artifacts from the original machine are not prerequisites another user can fetch
from GitHub; the receiving agent must create a new independent study.

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

Prepared on November 4, 2026. The owner approved publication to the existing
public AutoProteus repository. This file does not grant permission for live
experiments or redistribution of model assets.
