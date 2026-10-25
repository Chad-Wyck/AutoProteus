# Workflow-focused Qwen LoRA pilot — 2026-10-21

The fresh workflow adapter produced more fully verified upgrade packages, but
did **not increase completed end-to-end workflows** in this small comparison.
Both arms completed one of six workflows. Keep the adapter experimental; no
application setting or default seed was changed.

The three-pass training, export and twelve directed second-extension attempts
are complete. The detailed evidence is in
[the audited results](D:/AI_New/AP/evaluations/qwen-workflow-lora-2026-10-21-results.json).
Dates in this title use the user's local date; machine receipts use UTC.

## Results

“Behavior probes” check the requested tool's behavior. “Verified upgrade” also
requires passing candidate tests, protected regressions and package constraints.
“Complete workflow” additionally requires preserving the visible input during
development, activation, correct final artifacts, use of both capabilities and
an explicit finish. Native calling is recorded separately.

| Starting capability → added capability | Profile | Behavior probes | Verified upgrades | Complete workflows | Native complete workflows |
|---|---|---:|---:|---:|---:|
| Hashing → JSON formatting, familiar family | Base Q6 | 3/3 | 2/3 | 1/3 | 1/3 |
| Hashing → JSON formatting, familiar family | Workflow LoRA Q6 | 3/3 | 3/3 | 1/3 | 1/3 |
| CSV preview → hashing, transfer family | Base Q6 | 3/3 | 2/3 | 0/3 | 0/3 |
| CSV preview → hashing, transfer family | Workflow LoRA Q6 | 3/3 | 3/3 | 0/3 | 0/3 |

Both arms passed the advisory standard-connection diagnostic, benchmark and
all five ordinary tasks. All twelve candidates passed the protected seed
regressions and the independent behavior probes. Ordinary tasks overlap prior
training/preparation and are regression checks, not held-out capability evidence.

These are supplied-parent second extensions. Neither parent earns autonomous
first-upgrade credit. Three attempts per arm/family cannot establish reliability.

## What prevented completion

- Four formatter attempts changed the final inventory during development,
  before activation. All six ultimately had correct formatted files and hash
  receipts, but only one attempt per arm preserved the required stage order.
- The third base formatter candidate also included two disallowed development
  argument files in its source package. Its tool behavior and tests passed;
  the package constraint prevented verification.
- Five CSV transfer attempts reached activation. Every one preserved the CSV
  bytes and produced the right byte count and hash, but its audit contained a
  two-row preview instead of the requested default five-row preview. The initial
  task used `limit=2`; final use required the default. Both arms failed to make
  that parameter change correctly.
- The remaining base CSV attempt exhausted its action allowance while a new
  test expected `FileNotFoundError` and its implementation raised `ValueError`.
  The behavioral contract required rejection, and all independent behavior
  checks passed; its own test and implementation disagreed. It never reached
  final use.

The LoRA used both capabilities through native calls in all three activated CSV
attempts, compared with one of two activated base attempts. That is a useful
procedural observation, but their incorrect final previews still fail the task.
Posthoc command-route observations do not overturn the frozen scores.

## Training and selection

- Base: official instruction checkpoint `Qwen/Qwen3.5-9B`, pinned revision
  `c202236235762e1c871ad0ccb60c8ee5ba337b9a`.
- Fresh rank-8, alpha-16 adapter across the same 32 text decoder layers, with
  21,639,168 trainable parameters. NF4 base loading, FP32 computation, batch one,
  peak learning rate 0.00005 and the original completion-only loss.
- 141 training examples: the original 98 ordinary decisions plus 43 workflow
  decisions from seven independently completed formatter workflows sharing one
  prescribed parent lineage. Nine workflow examples came from the single
  visible-input workflow; 34 came from withheld-input workflows.
- All original system/user instructions and tool definitions were retained.
  Workflow histories were explicitly bounded to relevant recorded exchanges;
  original teacher contexts remain on disk. Training lengths were 1,527–3,960
  tokens. This changes training examples, not the app's inference context.
- All three complete passes were audited: 423 canonical updates, every example
  exactly three times, in the frozen shuffled order. Calendar training time was
  188.1 minutes including interruption/recovery. Mean canonical update time was
  23.4 seconds.

| Checkpoint | Historical Unicode validation loss |
|---|---:|
| Untrained | 0.221274 |
| Pass 1 | 0.179056 |
| Pass 2, selected | 0.175926 |
| Pass 3 | 0.183610 |

Selection used the smallest token-weighted loss on the same 18 historical
Unicode examples, not live task scores. The selected loss was 20.5% below the
untrained baseline. This reused, narrow validation set is not independent
workflow evidence.

Longer examples required memory work before full training: bounded context,
numerically checked efficient attention with explicit KV-head repetition, and
CPU offloading of saved checkpoint inputs. Four full-model readiness checks
failed before the fifth passed. Those changes and failures are preserved.

During full training, one long third-pass update hit the unchanged watchdog.
Recovery restored adapter, optimizer and RNG at update 375; five completed
updates were discarded and replayed. A stale progress record initially stopped
the resume launcher before loading. There were also missing-import preparation
and export-launch failures before inference. No candidate was repaired by the
operator, and training data, math and order were unchanged during recovery.

## Frozen inference comparison and cost

Both arms used the existing published Qwen Q6_K, Prism runtime, standard host
adapter, 128K context, 4K responses, temperature 0.6 and thinking off. The adapter
was loaded once and switched between disabled and enabled states. Raw and chat
probability checks confirmed an effect and exact control restoration; slot
caches were erased between cells. No full model merge was needed.

Each attempt shared 128 actions, 65,536 generated tokens and 1,800 seconds across
development, checking, retention, activation and final use. Public fixture bytes
were fresh per repeat and identical within each model pair. Arm/family order was
counterbalanced. Both parent calibrations passed before inference.

| Expense across all six attempts per arm | Base | Workflow LoRA |
|---|---:|---:|
| Model calls | 386 | 213 |
| Development read actions | 232 | 50 |
| Logical input tokens | 6,102,700 | 2,949,854 |
| Output tokens | 49,811 | 43,853 |
| Sum of trial wall time | 61.7 min | 55.0 min |

Input-token, output-token and call-time measurements are complete for these
attempts. Logical input tokens include cached prefixes and are not financial
cost. The totals include failures and show expense, not efficiency among
successful tasks. They exclude calibration, qualification and deployment.

Only formatter repeat two succeeded in both arms: base used 29 calls and 533.9
seconds; LoRA used 31 calls and 469.5 seconds. One matched success does not
establish a speed or call-efficiency advantage. The last LoRA formatter attempt
took 22.5 minutes and still violated stage order.

## Interpretation and artifacts

There is evidence of better package/test consistency and fewer wasted reads in
the transfer attempts. There is no measured increase in full workflow completion.
The next useful data would emphasize preserving visible inputs, distinguishing
development from final use, and updating parameters when the final contract
differs from the initial demonstration. Reserve new parent/task families for
evaluation. More repeats are needed before recommending this adapter.

Formatter workflows and the hashing API were training-exposed. The CSV parent
and task format were absent from training, but hashing itself was familiar.
Neither this result nor the narrow corpus establishes broad self-improvement.
Published GGUF ancestry metadata also does not prove an identical upstream HF
checkpoint; static compatibility and runtime application were verified separately.

Selected adapter:
[selected-adapter-f32.gguf](E:/AutoProteus-training/qwen-workflow-20261021/training/20261021T192833Z/selected-adapter-f32.gguf).
Full private evidence:
[training and comparison folder](D:/AI_New/AP/.data/qwen-workflow-20261021/training/20261021T192833Z).

All 24 study cells completed once, without live-trial retries or operator source
repairs. Source, trusted checks, runtime assets and base GGUF hashes were verified.
Owned test processes and the private listener are stopped; disk space remains
above the 10% reserve plus the 3 GiB guard margin. No permanent activation,
application/default changes, model merge, commit or push was performed.
