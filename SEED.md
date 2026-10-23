# Editable AutoProteus seed

This is your source copy. The protected controller owns model connections,
credentials, the interface, execution policy and recovery. VM runs have no host
drives or general network access. Explicit Linux native mode relies on external
protection and has the launching account's access.

Preserve the loop's input polling and complete human corrections. Resume may
report an interrupted operation; inspect saved work before repeating it. The
controller does not automatically replay uncertain operations.

## Source map

- `seed.py`: entry point, development checks and edited-tool invocation.
- `autoproteus/tools.py`: Workspace, text helpers and tool dispatch.
- `autoproteus/providers.py`: one `TOOL_SPECS` catalog for every model connection.
- `autoproteus/file_ops.py`, `search.py`, `terminal.py`: existing file and command helpers.
- `autoproteus/agent.py`, `storage.py`: loop, saved state and snapshots.
- `autoproteus/protocol.py`, `context.py`: shared instructions, normalized actions and context budgets.
- `tests/`: existing regressions and your separate new tests.

The controller supplies model-facing response syntax and renders this catalog
for native calls or JSON fallback. The seed uses the same prompt and action loop
in either mode. Register a capability once; do not add separate implementations
or instructions for each provider. Protocol compatibility does not change host
permissions or independently certify a capability.

## Upgrade workflow

1. **Implement.** Read the relevant source, then add the requested behavior in
   `Workspace.execute` and its definition in `TOOL_SPECS`. Use `self.path` for
   workspace paths. A new capability normally needs no loop changes.
2. **Test.** Preserve every existing test and add a focused `tests/test_NAME.py`.
   Call `workspace.execute("tool_name", arguments)`; tools are not Workspace
   methods. Use disposable fixtures outside `harness/` and inspect actual files
   as well as return values. Repair concrete failures, then run the full suite.
3. **Request activation.** Explain the change and actual checks. If final work
   needs the new tools, finish `needs_input` requesting activation. Editing the
   source copy does not change the running tools. A development pass is not
   independent approval. No separate feature report is required.
4. **Use the active tools.** After activation, continue the original task using
   its actual paths, parameters and requested defaults. Earlier demonstration
   inputs do not define the final task. The activation request is fulfilled;
   request another only after further seed changes.
5. **Verify outputs.** Inspect the saved files against the current user's
   requirements. When terminal access is available and the output is checkable,
   write and run a small `development/verify_task.py` that asserts the required
   paths, exact contents or computed properties. Derive expected values from the
   requirements, not by copying the actual output. For open-ended outputs,
   inspect them and report what was and was not checked.
6. **Finish.** Explicitly finish `completed` after verifying the requested
   outcome. Passing implementation tests alone does not complete the user's
   task. Avoid repeating unchanged passing checks.

Keep fixtures, argument JSON and verification scripts outside `harness/`, for
example under `development/`. Optional task notes belong in root `todo.txt`.
Every command below starts at the task workspace root.

## Contract-based tests

Implement optional defaults when arguments are omitted and leave those arguments
out of `TOOL_SPECS`'s required list. Test the smallest valid call first, then
explicit defaults and invalid values. A schema and implementation can share the
same mistake; compare both with the user's contract.

Assert a particular exception type or message only when the contract requires
it. Otherwise check rejection using the documented API's exceptions. For example,
a missing-file rejection test can accept `ValueError` or `OSError` when either
satisfies the contract. Do not invent extra restrictions to make a test pass.
`Workspace.path` resolves paths and rejects escapes; a link that stays inside
the workspace does not itself violate that rule.

For file tools cover empty input, Unicode character versus byte counts, CRLF,
exact limits and failures preserving original bytes. Isolate one requirement
per fixture. A size-limit test for valid JSON must contain valid JSON; otherwise
it can pass because of a parse error. For example:

```python
text = json.dumps({"text": "猫" * 100000}, ensure_ascii=False)
assert len(text) > 100000
json.loads(text)  # Confirm validity before testing oversized-input rejection.
```

Import `json` for that example. For an output-limit test, use valid input within
the limit whose transformed output exceeds it. Do not infer correctness from
an error caused by a different invalid condition.

New tests can import `unittest`, `Path` from `pathlib`, `Workspace` from
`autoproteus.tools`, and `temporary_directory` from `test_seed`. Construct
`Workspace(Path(directory))` inside `with temporary_directory() as directory:`.
Generate large fixtures with short expressions rather than repeated literals.

Reuse `Workspace.read_text(path, missing_ok=False)` and
`Workspace.write_text(path, content)` for UTF-8 text. Their limit is 100000
Unicode characters, measured by `len(text)`; report bytes separately with
`len(text.encode("utf-8"))`. They preserve CRLF and validate before writing.
`read_text` raises for a missing file unless `missing_ok=True`. Helpers accept
relative strings or validated Path objects.

## Development commands

Try an edited registered file tool without waiting for its tests to pass. Write
`development/args.json` with the tool's actual argument object, then run:

```sh
python3 harness/seed.py invoke --tool TOOL_NAME --arguments-file development/args.json
```

For source fragments or other multiline text, put the exact text in ordinary
workspace files. Keep only the remaining arguments, such as `path`, in
`development/args.json`, then load the text arguments without inline escaping:

```sh
python3 harness/seed.py invoke --tool edit_file --arguments-file development/args.json --text-file old_text development/old.txt --text-file new_text development/new.txt
```

The same option can supply `write_file`'s `content`, or any other text argument.
Each name must be unique and absent from the supplied JSON. Files use the same
workspace boundary and 100000-character limit as the existing text helpers;
Unicode, backslashes and line endings are preserved. This is a development
invocation of the registered tool, not activation or independent verification.

To isolate a failing test file while repairing it:

```sh
python3 harness/seed.py check --test tests/test_NAME.py
```

A focused pass covers only that file. Empty or entirely skipped selections fail.
Focused checks do not invoke tools or replace the full check before submission:

```sh
python3 harness/seed.py check
```

The older `check --tool NAME --arguments JSON` runs the full suite before
invocation. These commands require terminal access; their bounded output and exit
status are already useful without a shell pipeline. Independent controller
checks still decide upgrade acceptance.

After activation, a task-specific assertion script can check the final files:

```sh
python3 development/verify_task.py
```

Make its assertions cover every required output and call the checks before
exiting. Do not rely on printed success text or tool return values alone. This
script is your development evidence, not independent certification.

## Activation, navigation and allowances

**Continue with edited seed** freezes the current source and restarts the same
task with its saved files and history. VM mode uses a fresh VM under the same
policy. Resume keeps that activated version; starter recovery stays in the
controller. Some experiments withhold final inputs until activation; follow the
current task's instructions about which files are available and when.

`read_file` returns whole UTF-8 files up to 12000 characters. For larger files,
`read_section` uses character offsets and lengths (default 1000, maximum 12000).
Read useful sections, often 2000-6000 characters, and continue at `next_start`
only when needed. Newlines are preserved; CRLF counts as two characters.
`search_files` returns literal matches, snippets and character positions.
`edit_file` replaces one unique exact fragment; conflicts return locations and
a hint without changing bytes. Writes and edits are limited to 100000 characters.

Failed actions and each tool in a batch consume the action allowance; finishing
is free. Resume preserves the checkpoint and gives a fresh allowance. Opening
instructions stay stable; current todo notes follow the conversation. Report
unfinished work rather than rushing an unverified finish.

Cut-off responses execute no partial action. Output cutoffs and invalid action
formats share two repair retries per response, reset after an accepted response.
The protected controller bounds total requests using the same policy, including
finishing. The host keeps source fingerprints, differences and command results.
