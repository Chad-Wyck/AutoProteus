# Editable AutoProteus seed

This is your source copy. The controller owns model connections, credentials,
the interface, execution policy and recovery. In VM mode, code runs in a
disposable Linux guest without host drives or general network access. Explicit
Linux native mode has the account's access and relies on external protection.

Source map:

- `seed.py`: entry point and development-check command.
- `autoproteus/tools.py`: workspace validation and tool implementations.
- `autoproteus/providers.py`: the shared `TOOL_SPECS` definition table.
- `autoproteus/search.py`, `terminal.py`: existing search and command helpers.
- `autoproteus/agent.py`, `storage.py`: the running loop and saved state.
- `tests/`: existing regressions and your focused new tests.

## Add a capability

1. Search for the relevant dispatch or definition; read useful surrounding
   sections rather than scanning every file.
2. Implement the tool in `Workspace.execute` in `autoproteus/tools.py`, using
   `self.path` for workspace paths. Add its description, argument types and
   required arguments to `TOOL_SPECS` in `autoproteus/providers.py`. Both action
   formats use this table. A new tool normally needs no agent-loop changes.
3. Add focused tests and preserve existing behavior and tests. For file tools,
   cover empty text, Unicode versus byte counts, CRLF, exact limits, invalid
   inputs and failed writes preserving the original bytes.
4. From the task workspace, run:

       python3 harness/seed.py check

   Inspect failures and repair them. With a disposable `sample.txt`, exercise
   the edited implementation in a new process, replacing the name and arguments
   with those of your new tool:

       python3 harness/seed.py check --tool read_file --arguments '{"path":"sample.txt"}'

   Inspect the returned values against the expected result. These editable
   development checks do not replace independent controller checks. Terminal
   access must be enabled to run commands.
5. Finish with a concise explanation of the change and actual checks. Update
   usage documentation where needed. A checklist in `todo.txt` is optional;
   no separate `feature.md` report is required. The host records the diff,
   source fingerprints and command results.

## Continue with the edited seed

Edits do not replace tools in the running loop. After stopping or finishing a
run, the user can choose **Continue with edited seed**. The controller freezes
the current copy and starts a new worker with the same task, saved files and
history. In VM mode it starts a fresh VM under the same policy. Resume keeps
that activated version. After further edits, use the same control again to
activate the next version. Starter recovery remains a controller operation.

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
