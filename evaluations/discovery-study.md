# Outcome-first capability discovery

This optional study gives the model a concrete stock-reconciliation problem and
lets it choose a new reusable capability, tool name and argument interface.
The output contract is fixed beforehand; no candidate tool name or implementation
is supplied. It complements prescribed-tool studies rather than replacing them.

Prepare a frozen experiment with an existing local profile, then calibrate:

```text
.runtime/python/python.exe -X utf8 evaluations/discovery_study.py prepare --profile profile.json --output .data/discovery-study
.runtime/python/python.exe -X utf8 evaluations/discovery_study.py run --input .data/discovery-study --check-only
.runtime/python/python.exe -X utf8 evaluations/discovery_study.py run --input .data/discovery-study
```

The profile JSON contains a `config` object for the standard ModelClient. The
inference service is owned by the caller. Nothing is downloaded or started by
preparation. Fresh disposable VMs are required for candidate execution.

The public task specifies TSV columns, JSON output, duplicate aggregation,
caller-selected paths and byte preservation. A small declaration names the
model's chosen tool and substitutes three path placeholders into its chosen
argument object. Hidden tests use renamed inputs, duplicates, Unicode and empty
shops. Reference and duplicate-overwrite controls run only during calibration.
Existing protected tests, a separate new candidate test file, source scope,
retained input bytes and a full candidate-suite pass are still required.

Write `capability.json` at the workspace root, alongside `harness/`, rather than
inside it. Its `arguments` keys are your tool's parameter names; `@INPUT_A`,
`@INPUT_B` and `@OUTPUT` are values to be substituted for held-out paths. An
example shape is supplied without prescribing a tool name or parameter names.
The optional `python3 development/check_submission.py` checks this public shape
and statically visible argument declarations. It parses source as data and never
imports or executes candidate code. A passing preflight does not approve behavior
or activation. Use `--no-submission-preflight` when preparing a separate control
plan; the normal seed is unchanged. The helper is not a protected task input.

Checking and final use share 3,600 seconds, the profile's explicitly enabled
action allowance (128 by default), and 65,536
generated tokens with development. Only the controller activates a checked
candidate. Final scoring requires the exact saved summary, preserved inputs,
unchanged activated source, observed use after activation and explicit completion.
No automatic repair, retry, promotion, skills framework or new host permission is
introduced. Missing measurements and infrastructure errors remain explicit.

This is one concrete discovery task, not proof of broad capability discovery.
Qualify on other business tasks and another model before changing defaults.
