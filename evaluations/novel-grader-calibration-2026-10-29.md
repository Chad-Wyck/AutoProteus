# INI/newline graders and protected runner integration

The two new feature graders are VM-calibrated and integrated with the opt-in
research runner. **No training, model loading or live inference was performed.**
The editable starter remains unchanged at
`645d2222c5f7f6e92ad5f2ca964f7584e07b47ea4d410872e98a61009eb7bb0d`.

## Independent grading

`novel-probe.py` imports candidates only inside the VM. `ini_sections` checks
registration/schema, strict INI parsing, section order and DEFAULT exclusion,
empty files, exact multibyte character limits, malformed/duplicate sections and
invalid UTF-8. `normalize_newlines` additionally checks omitted LF defaults,
explicit CRLF, unchanged input, exact converted-output limits and preservation
of rejected input bytes. Both check missing files, directories, traversal and
escaping symlinks against **valid external input**, created before the checks.

The final disposable-VM calibration passed in 365.061 seconds:

| Control | Result |
| --- | --- |
| Correct references: both features, public calls and protected regressions | Passed |
| Absent features | Rejected by registration checks |
| Byte-based limit, each feature | Rejected at valid exact Unicode boundary |
| Workspace-boundary bypass, each feature | Rejected on traversal and escaping link |
| Sorted INI sections | Rejected on file order |
| Newline result returned without saving | Rejected on actual bytes |
| Incorrect newline default | Rejected on omitted-default call |
| Integer instead of boolean `changed` | Rejected on exact JSON types |
| Oversized converted output written before rejection | Rejected on preserved bytes |

All nine faulty candidates passed the 55-test protected starter suite and their
registration/schema checks. The semantic probes rejected the intended faults;
syntax/import failures were not counted as successful negative controls.

Three scripted chains completed through real development, independent package
grading, activation, first use, second extension, retention and cumulative use:
INI → newlines, newlines → INI, and CSV → hashing. Native message preparation and
normalization were exercised with fixed responses and HTTP fallback disabled.
These are plumbing controls, **not evidence of model capability or repeatability**.

## Opt-in runner

`model_study.py prepare --extension-pack pilot-6k --mode full` prepares the three
familiar families plus the two new chain orders. Without that option, the
existing default studies retain their original contracts and scoring.

Within this pack:

- Fresh input and receipt paths are reserved until each activation. There is no
  hidden-grader feedback or automatic public correction.
- A requested feature must be absent before extension. The second task begins
  only after independently accepted first packaging **and correct first use**.
- Actual first-task input/receipt bytes carry into second development and must
  remain unchanged. Fresh second-stage inputs exercise both capabilities.
- Saved receipts and file bytes are exact; JSON boolean/integer types differ.
  Default tasks require actually omitting `newline`/`limit`, as stated publicly.
- Native use and statically evidenced development invocation both count toward
  functional completion; routing is reported separately. Dynamic programs or
  unsupported invocation forms do not establish observed use.
- The existing shared deadline covers input qualification, development, grading,
  retention, activation and use. Activation grants no new action/token allowance.

Calibration cache identity includes the starter, trusted runner/probes,
environment, exact contracts and absent-feature requirements. Evidence-file
hashes are rechecked before reuse. Runner/environment changes invalidate the
frozen plan; cached controls never count as new inference repetitions.

## Prepared private handoff

`.data/lora6k-pilot-20261029/evaluation-v2/` supersedes the unexecuted v1 fixture
design without modifying it or the 93/27 local-Qwen dataset. The executable
base plan has five chain starts, one repeat, 128 actions, 65,536 generated tokens
and a shared 3,600-second allowance per extension task. It retains native 128K
inference, 4K responses, temperature 0.6, thinking off and the same task reminder.

The v2 amendment makes delivery timing explicit and applies the same artifact
preservation/default-omission rules to the familiar and novel chains. Its first
use contracts are frozen; a future adapter arm must reuse those exact contracts,
source, schedule and limits. No adapter or adapter-arm trial has been created.

The ordinary suite ran **553 tests: 486 passed, 67 skipped, no failures**. The
skipped VM test repeats the full calibration when explicitly enabled; the
separate real-VM calibration above was run. Unit controls cover strict receipts,
default omission through native/development routes, preservation, reserved reuse
paths, unknown-feature rejection, and skipping growth after failed first use.

Use `model_study.py run --input STUDY_DIRECTORY --check-only` to verify a prepared
plan and scripted calibration before inference. The prepared base plan passed
this path with zero model cells launched and matching novel calibration reused.
The private integration handoff records this separately from all model outcomes. Training authorization,
adapter export/overlay compatibility and enable/disable controls remain pending.
