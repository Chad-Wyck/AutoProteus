# Shorter guidance: preparation for the next comparison

The normal seed keeps its current instructions. `short-guidance` is an opt-in
copied-source treatment that changes only `autoproteus/protocol.py`'s guidance
and the README upgrade-workflow section. It makes plans and verification scripts
optional while retaining implementation checks, human precedence, activation,
final-output verification and explicit completion. No benefit is established.

The prepared unfamiliar capability is `inventory_files(path=".", recursive=False)`.
It inventories immediate files by default, with optional recursion. Development
uses a recursive example; final use requires a different directory with defaults.
The three paired fixtures include Unicode, nested files and different byte counts.
This tests a boolean/default-directory contract rather than repeating CSV limits.
It remains a directed extension, not model-selected capability discovery.

Prepare inert source snapshots, public task definitions and independent outcomes:

```sh
python evaluations/guidance_comparison.py prepare --output .data/guidance-comparison-NEW
```

Calibrate only the trusted grader and starter regressions in disposable VMs:

```sh
python evaluations/guidance_comparison.py calibrate --output .data/guidance-comparison-NEW
```

Preparation makes no model or VM calls. Calibration uses scripted actions, no
model service or public website. It checks both frozen starters and requires a
human-written positive control to pass and five faulty/absent controls to fail:
wrong default recursion, character counts instead of bytes, followed symlinks,
escaping paths, and an absent tool. The escaping control has valid external
files and relative-path rendering so accidental formatting errors cannot hide
the boundary bypass. Candidate/reference code executes only inside VMs.

For the later model comparison, freeze one standard model connection and its
assets/settings in a new execution manifest referencing `plan.sha256`. The helper
prepares and calibrates inputs; it does not start or schedule live trials.
Run six attempts in paired order A/B, B/A, A/B, matching each pair's input bytes.
Both arms share 128 actions, 65,536 generated tokens and 1,800 seconds per attempt
across development, independent grading, activation and final use. Internet is
explicitly off in both arms. Require calibrated feature checks before activation,
preserved inputs/source, observed use of the new tool, correct final JSON and
explicit completion. No final-use coaching, candidate repair or silent retries.

Report feature correctness, correct final artifacts and complete workflows
separately. Record whether calls omitted optional arguments as a diagnostic;
explicitly passing the correct default is still valid functional behavior.
Infrastructure failures and human interventions stay separate. Compare calls,
tokens and time among matched successes, with partial measurements labelled.
The treatment changes two instruction surfaces together; a gain would justify
qualifying that simpler bundle, not attributing the effect to a particular line.

## Web-extension development

Each editable copy now includes `examples/test_web_extension.py`. Copy it into a
new test file and adapt the tool call/assertions. Its mock supplies fixed bytes
without contacting the broker. A separate fresh-VM integration check must use
the actual bridge with explicit permission, a known fixture, inspected status
and saved bytes. Keep mocked functionality and integration evidence distinct.
The terminal bridge remains unavailable; no new relay or networking framework
was added to the seed.
