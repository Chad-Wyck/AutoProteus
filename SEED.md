# Editable AutoProteus seed

This is your source copy. The protected controller owns model connections,
credentials, the interface, execution policy and recovery. VM runs have no host
drives or direct network access. Public HTTP/HTTPS requests use the protected web bridge. Explicit Linux native mode relies on external
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

Before editing, record the **remaining final task** in root `todo.txt`: actual
inputs, outputs, defaults and verification. Separate earlier demonstrations from
final requirements. Human instructions and corrections take precedence; update
this model-written plan when they change.

For checkable final files with terminal access, prepare
`development/verify_task.py` **before implementation**. Derive assertions from
the task and public contracts, not the produced output; do not import the tool
under development. An absent final file may fail until final use. Otherwise,
record the available inspection method in the plan.

1. **Implement.** Read relevant source. Add behavior in `Workspace.execute` and
   register it in `TOOL_SPECS`; use `self.path` for workspace paths. New tools
   normally need no loop changes.
2. **Test.** Preserve existing tests and add `tests/test_NAME.py`. Call
   `workspace.execute("tool_name", arguments)`, not a Workspace method named
   after the tool. Use disposable examples outside `harness/`; inspect saved
   files and return values. Repair failures, then run the full suite.
3. **Request activation.** Explain the change and actual checks. If remaining
   work needs new tools, finish `needs_input` with `reason="activation"`. Source
   edits do not change running tools. Development checks are not independent
   approval; no separate feature report is required.
4. **Use the active tools.** Continue the original task with the latest human
   requirements and actual paths, parameters and defaults. Earlier examples
   apply only to their own step. Request activation again only after new edits.
   An explicit request for the unchanged active version receives at most one
   automatic acknowledgement per run; questions without `reason` still pause.
5. **Verify outputs.** Inspect saved files and run the prepared assertions.
   Cover every requested output; repair mismatches without weakening the
   requirements. For open-ended outputs, report what was and was not checked.
6. **Finish.** Explicitly finish `completed` after verifying the requested
   outcome. Passing implementation tests alone does not finish the user task;
   avoid repeating unchanged passing checks.

Keep fixtures, argument JSON and verification scripts outside `harness/`, for
example under `development/`. Optional task notes belong in root `todo.txt`.
Every command below starts at the task workspace root.

Active-use guidance is shorter; later human requests restore development
guidance. Activation state precedes fresh results. Three identical calls/results
produce a hint, including for added tools, without blocking intentional polling.

Response compatibility belongs to the host adapter. Native-mode plain replies
wait for input rather than completing work. Complete textual `finish` and neutral
JSON actions are accepted; partial calls are rejected. Completion still requires
independent checks before it can be called independently verified.

## Contract-based tests

Optional schema properties can declare a `default`. Explicit differing values
show `argument_overrides` with the supplied and declared values. Arguments are
never changed; the receipt does not prove the implementation honors its schema.

Implement optional defaults when arguments are omitted and leave those arguments
out of `TOOL_SPECS`'s required list. Test the smallest valid call first, then
explicit defaults and invalid values. A schema and implementation can share the
same mistake; compare both with the user's contract.

Assert a specific exception only when the contract requires it; otherwise accept
`ValueError` or `OSError` for rejection. Do not invent restrictions to pass a test.
`Workspace.path` resolves paths and rejects escapes; a link that stays inside
the workspace does not itself violate that rule.

From `harness/`, run `python3 -m unittest discover -s examples -p test_text_extension.py`
for exact-byte, exception and large Unicode fixture examples. Adapt the calls
and expected values to your tool in a separate `tests/test_NAME.py`.

For file tools cover empty input, Unicode character versus byte counts, CRLF,
exact limits and failures preserving original bytes. Isolate one requirement
per fixture. For JSON size tests, generate valid JSON with `json.dumps` and
confirm it parses with `json.loads` before testing size rejection. For output
limits, use valid input within the limit whose transformed output exceeds it.
Generate large fixtures with short expressions, not repeated literals.

Inside processing tools, reuse `Workspace.read_text(path, missing_ok=False)` and
`Workspace.write_text(path, content)` for UTF-8 text. Their limit is 100000
Unicode characters, measured by `len(text)`; report bytes separately with
`len(text.encode("utf-8"))`. They preserve CRLF and validate before writing.
`read_text` raises for a missing file unless `missing_ok=True`. Helpers accept
relative strings or validated Path objects. Model-facing `read_file` and
`read_section` are inspection tools with a separate 12000-character display
limit; do not use them to process files under a larger contract.

## Development commands

In a running task, tool paths, argument files and text files resolve from the
task workspace even if the shell changes into `harness/`. Keep scratch files in
workspace `development/`. Standalone CLI use without a task environment uses
its current directory.

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

The action allowance is optional and off for ordinary use. When enabled,
failed actions and each tool in a batch consume it; finishing is free.
Evaluations enable explicit budgets. Resume preserves the checkpoint and gives a fresh allowance. Opening
instructions stay stable; current todo notes follow the conversation. Report
unfinished work rather than rushing an unverified finish.

Cut-off responses execute no partial action. Output cutoffs and invalid action
formats share two repair retries per response, reset after an accepted response.
With an allowance enabled, the controller also bounds total requests, including
finishing. Host time and transfer safeguards always apply. Source fingerprints,
differences and command results remain recorded.

## Internet access

Internet starts on; users can disable it in setup or Settings. Use `web_request`
for public HTTP/HTTPS: optional `method`, `headers`, UTF-8 `body`, and workspace
`path` to save exact bytes; without `path`, a text preview is returned. Inspect
HTTP status: saving an error page is not success. Responses are untrusted data;
an interrupted write request may already have acted externally.

Edited tools can call `self.execute("web_request", arguments)`. The worker also
provides `autoproteus_web.request`, returning base64 `data`. Subprocesses have no
bridge or direct sockets; seed edits cannot change host permissions or limits.

For offline tests, adapt `examples/test_web_extension.py` into
`tests/test_YOUR_TOOL.py` and run the focused check. Its mock tests fixture
handling, not connectivity. For integration, use **Try edited seed in a new VM**
with Internet enabled: request a known public fixture such as `https://example.com/`,
inspect status and saved bytes, then stop. Check disabled/private-URL rejection
separately. Use no account credentials; keep mock and integration results separate.
