# Editable AutoProteus seed

This is your source copy. The controller owns model connections, credentials,
the interface, execution policy and recovery. In VM mode, code runs in a
disposable Linux guest without host drives or general network access. Explicit
Linux native mode has the account's access and relies on external protection.

The loop polls the protected controller for human direction changes between
actions, and for queued follow-ups before reporting completion. Preserve this
small polling interface when editing the loop. All human corrections remain
complete in context; an oversized set of instructions fails explicitly. Resume
includes any incomplete operation receipt. Inspect saved work before retrying;
the controller never automatically replays an interrupted command.

Source map:

- `seed.py`: entry point, development tests and edited-tool invocation.
- `autoproteus/tools.py`: workspace validation, shared text helpers and tool dispatch.
- `autoproteus/file_ops.py`: existing section reading and exact-edit mechanics.
- `autoproteus/providers.py`: the shared `TOOL_SPECS` definition table.
- `autoproteus/search.py`, `terminal.py`: existing search and command helpers.
- `autoproteus/agent.py`: the running loop; `storage.py`: saved state and snapshots.
- `autoproteus/protocol.py`: prompts and action parsing; `context.py`: conversation budgeting.
- `tests/`: existing regressions and your focused new tests.

## Add a capability

1. Search for the relevant dispatch or definition; read useful surrounding
   sections rather than scanning every file.
2. Implement the tool in `Workspace.execute` in `autoproteus/tools.py`, using
   `self.path` for workspace paths. Add its description, argument types and
   required arguments to `TOOL_SPECS` in `autoproteus/providers.py`. Both action
   formats use this table. A new tool normally needs no agent-loop changes.
   An argument with a requested default is optional: leave it out of `required`
   and apply the default in the implementation when the argument is omitted.
   Reuse the existing text helpers for file capabilities:

   - `self.read_text(path, missing_ok=False)` returns UTF-8 text up to
     `TEXT_CHARACTER_LIMIT` (100000 Unicode characters), preserves CRLF,
     and rejects invalid or oversized input. A missing file returns empty
     text only with `missing_ok=True`.
   - `self.write_text(path, content)` replaces a file after validating its
     character limit, creates parent directories, and returns path and bytes.
     The public `write_file` tool uses this same helper.

   Helpers accept relative strings or validated `Path` objects. The text
   limit applies to `len(text)`. Only report byte size using
   `len(text.encode("utf-8"))`; valid Unicode text can exceed 100000 bytes.
3. Add a separate new `tests/test_<capability>.py` file and preserve existing
   behavior and tests. Invoke tools with `workspace.execute("tool_name", arguments)`;
   tool names are not methods such as `workspace.format_json(...)`. For file tools,
   cover empty text, Unicode versus byte counts, CRLF, exact limits, invalid
   inputs and failed writes preserving the original bytes.
   Test the smallest valid call from the user's contract, omitting optional
   arguments, then explicit defaults and invalid values. Check against that
   contract, not only your new schema; a schema and implementation can share
   the same mistake.
   New `tests/test_*.py` files can import `unittest`, `Path` from `pathlib`,
   `Workspace` from `autoproteus.tools`, and `temporary_directory` from
   `test_seed`. Inside `with temporary_directory() as directory:`, construct
   `Workspace(Path(directory))`. You do not need to read the full existing
   test suite to use this helper. Generate large fixtures with short expressions
   such as `'猫' * 100000`, rather than writing repeated literal text.
4. Try the edited implementation on a disposable example before running the
   suite. Keep disposable input files and argument JSON outside `harness/`,
   for example in `development/`. They are task files, not seed source.
   From the task workspace, replace the tool and arguments as needed:

       python3 harness/seed.py invoke --tool read_file --arguments '{"path":"sample.txt"}'

   To avoid shell quoting, write a UTF-8 `arguments.json` containing
   `{"path":"sample.txt"}` with `write_file`, then run:

       python3 harness/seed.py invoke --tool read_file --arguments-file arguments.json

   `invoke` does not run tests, so it also works while a test needs repair. It
   allows registered file tools only and keeps workspace path restrictions.
   Inspect returned values and actual resulting file contents against a simple
   exact expected example; successful return values alone do not prove a write.
   Then run the separate suite and repair concrete failures:

       python3 harness/seed.py check

   The older `check --tool NAME --arguments JSON` still runs tests first and
   invokes the tool only if they pass. These editable
   development checks do not replace independent controller checks. Terminal
   access must be enabled to run commands. The check already bounds its output;
   run it directly so a shell pipeline cannot hide its failure status.
5. Finish with a concise explanation of the change and actual checks. Update
   usage documentation where needed. A checklist in `todo.txt` is optional;
   no separate `feature.md` report is required. The host records the diff,
   source fingerprints and command results.
   After the requested outputs are verified, explicitly finish. Repeating
   checks of unchanged passing work does not complete the user's task.

Every command starts at the task workspace root; use relative `harness/` paths.
Optional task notes belong in `todo.txt` at that root, beside `harness/`.
After enough inspection, make a small implementation, test it and repair concrete
failures. Re-reading the whole existing suite is not an upgrade requirement.
Cut-off model responses execute no partial action. The seed shares its two format
repair retries with output cutoffs; retry with a smaller action when asked.
The two retries apply to each response and reset after an accepted response.
The controller bounds total requests using that same policy, including finishing.

## Continue with the edited seed

Edits do not replace tools in the running loop. After stopping or finishing a
run, the user can choose **Continue with edited seed**. The controller freezes
the current copy and starts a new worker with the same task, saved files and
history. In VM mode it starts a fresh VM under the same policy. Resume keeps
that activated version. After further edits, use the same control again to
activate the next version. Starter recovery remains a controller operation.
After activation, use the now-active tools to finish the remaining user task.
The activation request for that version is already fulfilled. Repeat development
or request another activation only when further changes are needed.

## File navigation and allowances

`read_file` returns a complete UTF-8 file up to 12,000 characters. For larger
files, `read_section` uses character positions and lengths (default 1,000;
maximum 12,000). Useful sections are often 2,000-6,000 characters. Continue at
`next_start` only when more source is needed. Original newlines are preserved;
CRLF counts as two characters. `search_files` returns literal matches with
paths, snippets and character positions.

`edit_file` replaces one exact, unique fragment. Match failures return a count,
up to three locations and a recovery hint without changing bytes. Writes and
edits are limited to 100,000 characters. Validate before writing.

The seed enforces the action allowance and adds an exhaustion notice when it
fits without displacing user instructions. Failed calls and each tool in a batch
count; finishing is free.
Resume preserves the checkpoint and grants a fresh allowance. Report unfinished
work honestly rather than rushing to finish. Opening instructions stay stable;
the current checklist, when present, appears after the conversation history.
