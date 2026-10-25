# Focused final-task completion comparisons

These opt-in pilots test retaining final requirements after an earlier example
used a different argument. They do not measure a new upgrade or autonomous
growth. The default starter stays unchanged. An optional frozen accepted parent
can be supplied as inert source bytes; it receives no new first-upgrade credit.

Each pilot compares one treatment with baseline:

- `final-contract`: append a concise restatement of the public final task.
  Both arms use identical source. No held-out answer or corrective feedback is
  supplied. This tests an explicit prompt intervention, not unassisted success.
- `short-guidance`: shorten the copied upgrade instructions. Task wording stays
  identical across arms. Do not combine this with final-contract in the same arm.

Three tasks use different defaults and scopes: a default-length Unicode section
after a short preview, workspace-wide search after a regional example, and root
listing after an archive example. Exact output and input preservation are
checked independently. Source must remain unchanged, the required native tool
must be observed, and the agent must explicitly complete before its deadline.
Omitting optional arguments is a separate diagnostic; explicitly supplying the
correct default is not automatically a functional failure.

Prepare either pilot using a JSON object with the standard connection `config`:

```text
.runtime/python/python.exe -X utf8 evaluations/completion_study.py prepare --profile profile.json --comparison final-contract --output .data/completion-contract
.runtime/python/python.exe -X utf8 evaluations/completion_study.py run --input .data/completion-contract --check-only
```

Use `--comparison short-guidance` and a different output folder for the other
pilot. Linux users can substitute the bundled `.runtime/python-linux/bin/python3`.
`--source parent-source.json` accepts a frozen source bundle. Preparation never
starts inference. Calibration runs protected regression suites and guest-side
positive/stale-override controls against the same artifact oracle used live.

Only when ready for inference, run without `--check-only`, or use the generated
Windows launcher. Default size is **six attempts per pilot**, one repetition of
three tasks and two alternating arms. Choose one pilot first. `--repeats 3`
creates 18 attempts. Each attempt explicitly shares 128 configured actions,
3,600 seconds and 65,536 generated tokens; action limits remain enabled even
when disabled in the normal app. The profile can select a smaller action cap.
Hosted keys belong in `AUTOPROTEUS_API_KEY`, never a plan file.

Source, runner, environment and supplied model assets are fingerprinted.
Calibrate the exact plan before inference. Changes require a fresh plan.
Interrupted evidence remains on disk and is not silently retried. Reports retain
all attempts, partial measurements, model identities and matched-success pair
identifiers. Compare efficiency only among independently successful matched
tasks. A positive pilot needs repetition, unfamiliar tasks and another model
before any treatment becomes a default.
