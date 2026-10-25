# autoresearch review for AutoProteus — October 24, 2026

**Recommendation:** borrow the compact experiment procedure and use it to organize AutoProteus's existing studies. The largest opportunity is a bounded research runner that proposes a small change, evaluates a frozen candidate, records every result and presents promising candidates for review. No AutoProteus performance benefit was measured in this review.

## Scope and evidence

Reviewed [karpathy/autoresearch](https://github.com/karpathy/autoresearch/tree/228791fb499afffb54b46200aca536f79142f117) at `228791fb499afffb54b46200aca536f79142f117`, the latest commit returned by GitHub commit search and shown in its master history. Inspected README, program.md, the relevant preparation/evaluation and training code, dependency configuration, and notebook analysis. The master blobs for program.md, prepare.py and train.py matched the pinned versions; blob identities are in the companion JSON. Raw web views showed different formatting/line counts, so source anchors use the pinned GitHub connector content.

Local comparison uses the working tree documenting v0.8.2, based on committed HEAD `532e36bcc9fcf7a1eb2b69015eef2558c965c13f`, including uncommitted changes. Read the current README, upgrade recipe, release notes, relevant evaluation/context/evidence code, latest guidance study and workflow LoRA findings. This was a focused source review, not a complete repository audit. The JSON identifies the local inputs.

Only these research notes were added. No upstream code was executed, packages installed, training or model trials started, defaults changed, or recurring research scheduled.

## What the repository actually provides

The repository is a small pretraining research environment. A coding agent receives [program.md](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/program.md), edits train.py, runs an experiment, reads validation bits per byte and memory measurements, logs keep/discard/crash, and continues from retained changes. The instructions also prefer simple changes when benefits are comparable.

prepare.py fixes the data split and evaluation function by convention. The agent instructions prohibit changing it or adding dependencies. This restriction is expressed in a prompt; it is not a protected controller boundary. train.py runs both training and final evaluation and prints the reported metric. The evaluator also calls the candidate model's own loss computation. These are appropriate points to examine before treating a reported score as independent proof.

The research loop is largely an instruction-driven workflow for an external coding agent. program.md is human-controlled in the baseline; the repository does not demonstrate automatic recursive improvement of that research procedure or a general-purpose agent harness. The README's large future-swarm narrative is introductory framing.

## Relevant ideas and existing overlap

| Idea | Current AutoProteus overlap | Useful addition |
| --- | --- | --- |
| One explicit experiment brief: objective, editable surface, fixed evaluator, budget and retention rule | Frozen comparison plans, source packs, contracts, model profiles and trusted-file inventories already exist | Standardize a short trial card across studies so a model can propose experiments without choosing its own success criterion |
| Small changes followed by baseline comparison and retention | Starter/edited comparisons, fresh VMs, protected regressions, feature checks, activation and source identities already exist | Coordinate a bounded series through these existing controls; retain research candidates separately from normal app defaults |
| Record unsuccessful experiments as well as wins | AP already preserves attempts, partial costs, source evidence and per-study JSON | Add a compact index across studies with parent/candidate identities, hypothesis, exact grader version, outcome and evidence link; failed ideas can inform later proposals |
| Prefer simpler solutions when outcomes are comparable | AP's small editable seed is already a deliberate constraint | Use source size/change scope as review diagnostics, with correctness first; do not award points for deleting tests or compressing code into fewer lines |
| Improve the research instructions themselves | AP already tests shared guidance and activation/context variants | Treat instruction changes as explicit experimental candidates and qualify them across models; do not assume shorter guidance is better |
| Predictable bounded experimentation and a readable progress summary | Shared action/token/wall ceilings, Stop, saved reports and a VM lease already exist | An opt-in research session could take a user-selected budget and finish with a concise account of verified, failed and inconclusive trials |

These are proposed adaptations. Existing AP mechanisms do not need to be reimplemented under a new framework.

## Why the latest local results change the priorities

The [v0.8.2 guidance study](D:/AI_New/AP/evaluations/seed-v0.8.2-guidance-2026-10-24-findings.md) found that shortened instructions did not improve the tested workflow. The original Qwen baseline grader passed 3/3 primary attempts, but a later schema audit reduced candidates satisfying all additional checks to 1/3. Two baseline candidates advertised an optional path as required. After the supplementary checks, complete Qwen baseline workflows were also 1/3; Empero had no fully checked complete workflows in either guidance arm.

The excluded Qwen baseline exposure remains part of the report's all-exposure accounting, giving 1/4 fully checked baseline workflows when included. These posthoc audits supplement rather than replace frozen scores.

One baseline attempt wrote correct output, inspected it, then repeatedly called the inventory tool until its action allowance expired. This makes completion and correct use after activation a useful target. It does not establish activation context as the cause. The current working tree already contains an opt-in activation-history variant in evaluations/activation_comparison.py, so a second implementation would duplicate preparation.

The [workflow LoRA comparison](D:/AI_New/AP/evaluations/qwen-workflow-lora-2026-10-21-findings.md) similarly shows why the objective matters: more verified upgrade packages did not increase full workflow completion (one of six in each arm). Lower adapter validation loss is useful for training selection but does not substitute for an independently completed task.

## Adapt the acceptance rule to AutoProteus

Use independent complete-workflow success as the primary outcome: correct public tool contract and schema, preserved inputs and earlier capabilities, activated checked source, required observed use, correct final artifacts, and explicit completion.

Require protected checks before a candidate is eligible. Compare time, generated tokens, memory and source complexity only after accounting for correctness and uncertainty. Report failed trials and setup/checking costs. Record unknown measurements as unknown.

Keep discovery fixtures distinct from final qualification tasks. Repeatedly choosing winners on the same small task set can fit that set; a winner should face fresh public contracts/fixtures and a second model before a general model-agnostic claim. Never reveal private expected answers to the candidate.

The latest schema and exact-boundary controls are now present in the local guidance probe/calibration code. Verify them before freezing any new study. Do not retroactively change historical scores or imply that the updated grader was used in the earlier primary runs.

The AP controller should own evidence and stopping conditions. Autoresearch's printed metric and prompt-only do-not-edit restriction are not replacements for AP's existing trust boundary. A candidate may remain retained in a research store without becoming the starter or being automatically approved for daily use.

## Budget and hardware limits

The [training implementation](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/train.py#L458) uses CUDA, BF16, compiled execution and externally fetched Flash Attention kernels; [dependencies](https://github.com/karpathy/autoresearch/blob/228791fb499afffb54b46200aca536f79142f117/pyproject.toml) select a CUDA 12.8 PyTorch index. This is a pretraining setup tested on H100. It is not a demonstrated ready-to-run path for AP's GTX 1080 Ti or the current 9B LoRA process.

The nominal 300-second training budget excludes startup/compilation, the first eleven step timings and final evaluation. program.md also asks the external agent to stop runs exceeding ten minutes. Approximate experiments-per-hour figures therefore are not guaranteed end-to-end throughput.

AP already shares wall time, actions and generated tokens across stages in its research studies. Retain those ceilings, include boot/checking/activation costs, and choose a task-appropriate allowance. Five minutes is not a useful universal rule for AP tasks. The original instructions' indefinite loop can instead become a finite user-authorized batch.

## Suggested first use

Use the existing activation-history comparison as a bounded pilot once its independent grader and deliberately faulty controls are confirmed. Compare the frozen baseline with the existing context-placement variant under matched model/settings, alternating order and unchanged budgets. Retain all attempts and separately report functional contract, schema, artifacts and explicit finish.

This pilot tests the current completion bottleneck; it does not train a model. Treat any apparent winner as provisional, then qualify it on unfamiliar task contracts and another model. Only after that consider a generic loop that proposes the next candidate automatically.

For user convenience, a future optional research interface could expose a goal, allowed change scope, time/resource allowance and a readable final report. Most of the execution machinery can reuse AP's controller and studies, keeping the seed small.

## Decision

High relevance as a research-process reference. Moderate incremental implementation value because AP already has stronger source/evaluation boundaries and detailed trial evidence. Low immediate value from copying the GPU training stack. Prioritize clearer experiment selection and independent qualification over another agent framework or an automatic promotion rule.
