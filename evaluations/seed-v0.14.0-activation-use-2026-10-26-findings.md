# Qwen3.5 9B: first use, cumulative growth and optional planning

The unchanged v0.14.0 starter completed one independently checked two-feature
chain in the initial growth batch. A later baseline batch also has one complete
chain after correcting a tool-use observation gap. First-package acceptance
varied substantially. Neither added navigation nor optional planning established
a benefit; the shipping seed remains unchanged.

## Protocol

These prospective `activation-use-v2` studies independently check a first
extension, activate it on fresh input, then score actual use and completion.
A separate task adds a second tool, preserves the first, and uses both. A verified
first package whose use fails may receive a labelled diagnostic second task;
that cannot erase its first failure or earn complete-chain credit. Invalid
packages cannot grow.

All studies used Qwen3.5 9B Q6_K on the GTX 1080 Ti, the pinned Prism engine,
native production adapter, 128K context, 4K maximum responses, temperature .6,
top-p .8, top-k 20, thinking off, Q8 KV and no LoRA. Each edit/use task shared
128 actions, 3,600 seconds and 65,536 generated tokens, including checking and
activation. A second task received a fresh allowance. Ordinary/preflight checks
were separate overhead. All three batches passed their five ordinary tasks.

Each attempt started a fresh owned server, with matched initial sampling seeds
by capability. Fresh first-use cases were identical within a paired comparison;
different batches had different frozen case paths/contents. Equal initial seeds
do not imply identical trajectories. No coaching, candidate repairs, selective
retries, promotion or deadline changes occurred. Candidates ran only in VMs.
No infrastructure-error attempts were recorded.

The shipping source stayed at SHA-256
`944dde7bd0e5185699c292b929d0fd4042031266872fc29a8af4c38a84b88465`.
The friend's frozen `d8e7175` setup was not changed.

## Outcomes and observation correction

First-use and complete-chain denominators are **scheduled first tasks**, three
per arm. Second-stage denominators are eligible launched tasks. A dash means
not requested, not failure.

| Batch / arm | First packages | First use, raw → reassessed | Second verified | Second-task use | Complete chains, raw → reassessed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Navigation / baseline | 3/3 | 3/3 → 3/3 | — | — | — |
| Navigation / source-outline | 2/3 | 1/3 → 2/3 | — | — | — |
| Initial growth / baseline | 3/3 | 3/3 → 3/3 | 3/3 | 1/3 | 1/3 → 1/3 |
| Planning follow-up / baseline | 1/3 | 0/3 → 1/3 | 1/1 | 1/1 | 0/3 → 1/3 |
| Planning follow-up / optional planning | 1/3 | 0/3 → 0/3 | 1/1 | 0/1 | 0/3 → 0/3 |

Final trace inspection found valid guest programs using a `Workspace` variable,
including a normal `PYTHONPATH` prefix, that the original use detector missed.
One formatter first use in each paired study was a false negative. The optional
hashing run also invoked its tool, but finished waiting rather than completed,
so it still fails first use.

The observer now recognizes bounded, straight-line imported Workspace calls and
their printed results. First-use evidence must match the actual fresh input and
expected returned fields. Failed commands, wrong inputs, dead branches, fake
print-only receipts and overwritten bindings have negative tests. Recognition is
observational evidence, not a security proof against hostile code; arbitrary
dynamic programs remain outside its supported scope.

Original plans, result files, queues and primary reports were **not overwritten**.
`use_reassessment.py` separately reads closed exports, verifies saved blob and
candidate hashes, and reevaluates first use from the recorded activation boundary.
It executes no candidate, recovers no Store, replays no model, and leaves
independent implementation reviews and second-task verdicts unchanged. Separate
JSON reassessments preserve raw flags and identify their input/observer hashes.

## What failed and what changed

The initial hashing-parent chain implemented a valid formatter but changed the
real final input during development, withholding activation. The CSV-parent chain
used both tools after activation but copied an earlier limit of two into its
checklist instead of following the final default. The formatter-parent chain
added hashing and completed the final audit.

The navigation helper was invoked **zero times** in its three attempts. One CSV
candidate exhausted its actions and failed checking. After the observer correction,
the two matched successful first-use pairs totaled 111 versus 100 calls, 16,713
versus 17,014 generated tokens, and 1,106.752 versus 1,071.508 trial seconds
(baseline versus outline). These small descriptive differences do not establish
benefit, especially without actual helper adoption. No promotion is warranted.

The focused revision made required checklist/assertion preparation optional in
the copied development prompt and README. It changed no tool, active-use prompt,
context handling, permission or grading requirement. The copied files shrank
from 4,951/11,848 bytes to 4,708/11,445 bytes. This targeted misleading task notes
without adding another procedure. It was tested against a fresh baseline across
all three first extensions and every eligible second task.

Baseline wrote todo.txt in 4/4 upgrade attempts; the optional arm did so in 2/4.
Neither wrote the specifically named development/verify_task.py. That measures
observed adoption, not whether other verification occurred. The revision did not
improve completion. Its hashing package passed, but its CSV missed exact Unicode
handling and its formatter rejected the valid exact output-size boundary. Its
diagnostic second task again used the final input too early. Baseline also failed
hashing size rejection and quoted CSV handling in this later batch.

There were no matched successful first-use pairs in the planning follow-up.
Lower aggregate calls/tokens for the optional arm therefore do not establish
greater efficiency. Baseline variation remains a qualification gap. These
one-repeat arms are exploratory, not model rankings.

## Validation and evidence

**405 ordinary tests passed, 59 skipped.** The scripted real-VM test passed seven
cases: all three first-use tools, missing use, action exhaustion, a successful
Python-variable call and a failed program. These are scripted checks, not model
capability data. Reassessment tests reject corrupted evidence and active queues
and verify that no source data is modified or candidate program executed.

Private exports retained on the test machine:

- `.data/activation-use-v2-navigation-20261026-ready/`
- `.data/activation-use-v2-growth-20261026/`
- `.data/activation-use-v2-optional-planning-20261026/`
- `.data/activation-use-night-20261026/`: reports, adoption/cost counts, validation
  logs and separately named `*-use-reassessment.json` files.
- `.data/activation-use-followup-20261026/`: follow-up ownership/engine receipts.

The owned inference services were stopped. Optional planning remains experimental.
Qualify frozen-baseline task completion across repeats and unfamiliar requirements
before adding more seed instructions or treating cheaper failures as progress.
Changed observers require fresh plans for future live trials.
