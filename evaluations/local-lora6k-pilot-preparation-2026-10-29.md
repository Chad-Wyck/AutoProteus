# Local-Qwen 6K pilot: dataset review and evaluation design

**Prepared 93 training and 27 validation examples using only audited local Qwen
outputs. No training, model loading, GPU work or live-model evaluation started.**
The new frozen design remains separate from the normal seed.

## Reviewed dataset

| Purpose | Training | Validation |
| --- | ---: | ---: |
| Seed implementation | 26 | 8 |
| Test writing | 5 | 3 |
| Development checks | 4 | 1 |
| Activation | 4 | 1 |
| Correct capability use | 14 | 5 |
| Saving final outputs | 14 | 4 |
| Completion | 10 | 2 |
| Ordinary tasks | 13 | 3 |
| Navigation immediately before an edit | 3 | 0 |
| **Total** | **93** | **27** |

The preparation rechecked original local-runtime provenance and independent
success, excluding Sol, other remote teachers, prior adapters, manual candidate
repairs, automatically corrected outcomes and diagnostic/supplied-parent stages.
The final action/artifact qualification was replayed across 32 contributing
attempts. Hash receipts cover 185 input files. The starting index contained 638
decisions; 90 diagnostic/supplied-parent decisions were excluded before context
selection and subsequent filtering.

Original system/user text, selected target responses and tool declarations are
preserved. Complete observed exchanges supply relevant source, checks and final
output evidence, with explicit retained/omitted indices. No synthetic observation
or rewritten target is added. Stable-public-API tests retain their original
`Workspace.execute` contract rather than requiring the dispatcher's entire source;
provider declarations remain when the test inspects them. Context transformations
are disclosed and not claimed to be the original full teacher requests.

All examples fit 6,144 tokens: training is 2,016–6,052 and validation 2,021–6,002.
Final saved JSON is rendered with the pinned Qwen tokenizer before loss masks
are produced. This catches schema-key ordering differences introduced during
serialization; draft tokenizations were not reused blindly. Only selected
assistant tokens are supervised.

Whole first/second-extension lineages, shared generated core files and sessions
stay in one split, using the actual host-selected source identity rather than
the different runtime-bundle hash. There are 15 training groups and four
validation groups. One equivalent code target was removed from validation after
normalizing away assistant prose and formatting. Shared immutable starter code
and generic tool actions still appear in both splits.

Twelve offline controls passed: model provenance/exclusions, original evidence,
instruction/target equality, tool pairing, source-lineage separation, normalized
code deduplication, round-trip tokenization/masking, default omission, full-check
evidence, data/evaluation separation and reference-oracle/schema checks. Candidate
code was not imported or executed on the host.

These remain three familiar capability families and a small number of successful
workflows. There are only four activation and ten completion training examples.
The review does not establish broad diversity or guarantee a useful adapter.

## Prospective pilot and evaluation

Plan one epoch first, using the [tested chunked-loss configuration](local-lora-backward-diagnosis-2026-10-29.md):
rank 8 on all 32 text layers, NF4/FP32, CPU embedding/checkpoint inputs and
64-target checkpointed projection/loss chunks. Validate before and after that
epoch, reporting overall token-weighted and per-bucket/workflow macro NLL.
No later epoch, export, merge, deployment or generation starts automatically.

The frozen future comparison uses the same starter
`645d2222c5f7f6e92ad5f2ca964f7584e07b47ea4d410872e98a61009eb7bb0d`,
Q6 base/runtime, 128K inference context, 4K responses, temperature 0.6 and
thinking off in both arms. The 6K training window is independent of the inference
context. Adapter conversion/overlay compatibility and enable/disable probability
controls are prerequisites after a separately authorized training/export.

The exploratory screen has five ordinary retention tasks per arm, then five
chain families per arm: the familiar hashing, JSON-formatting and CSV-preview
chains plus INI-section listing → newline normalization and the reverse. The
new tool names occur in neither prepared split; this is dataset-level novelty,
not a claim about the base model's pretraining.

The main measure is independently checked complete functional growth per
scheduled first-extension start: accepted first package, correct first use,
accepted second extension, retention and correct cumulative second use with
explicit completion. Native/development route scores remain separate. Use the
same existing activation reminder in both arms, with no human repairs or
automatic public corrective feedback. Check omitted optional arguments, Unicode,
character boundaries, valid external inputs for path/symlink rejection, exact
saved bytes and strictly typed receipts.

Ten scheduled chains permit at most 20 extension tasks. The existing 60-minute
shared allowance per task means up to **20 hours of task ceilings**, excluding
startup/calibration; this is not an ETA. Each task also retains 128 actions and
65,536 generated tokens. Second tasks get a fresh allowance but are skipped when
first acceptance/use fails. Record infrastructure/resource stops separately and
never silently retry. A three-repeat confirmation is explicitly disabled until
the screen is reviewed and separately authorized.

The two novel guest probes are prepared, but **VM calibration and integration
with the protected study wrapper are still required before generation**. The
existing stock grader recognizes only its original three features. Planned
controls include correct references, byte-limit mistakes, boundary bypass,
missing file mutation, incorrect defaults and false-success receipts. Offline
oracle checks do not qualify a guest probe. Hidden checks must remain separate
from model feedback and be frozen before trials.

Private handoff: `.data/lora6k-pilot-20261029/README.md`, `dataset/`,
`pilot-plan.json` and `evaluation-v1/`. Public files contain no conversations,
token datasets, credentials or weights. Full training and evaluation remain
unstarted; the user requested preparation only.

Follow-up: the separately authorized VM calibration and protected runner
integration are recorded in [the grader calibration report](novel-grader-calibration-2026-10-29.md).
The private `INTEGRATION.md` and `evaluation-v2/` supersede the calibration
prerequisite and clarify fixture delivery; the original frozen design and dataset
remain intact. Training and live-model studies have still not started.

The subsequent [full-runner preparation](local-lora6k-runner-2026-10-30.md) adds
transactional checkpoint/Resume, validation and supervised resource control.
Its frozen private run verifies offline; it has not started training.
