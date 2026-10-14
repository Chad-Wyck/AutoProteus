# Editable AutoProteus seed

This directory is your source copy. The host controller, model connection, user
interface and execution policy are outside it. Normally your code runs inside a
disposable Linux VM; it receives model responses through the supplied client.
If the user explicitly launched Linux native mode, `execution_mode` is `native`:
your code has the account's access and any protection comes from the surrounding
environment. The controller supplies the user's selected launch mode.

`seed.py` creates the agent. `autoproteus/agent.py` requests actions and records
their results. `autoproteus/tools.py` implements workspace files and optional
Linux commands. `autoproteus/providers.py` describes guest tools to the model;
it contains no model connection or credentials. `autoproteus/storage.py` keeps
session state. `tests/test_seed.py` exercises the editable behavior.

When asked to improve yourself, change one concrete limitation in this source
copy. For a new tool:

1. Locate the relevant dispatch and definition with `search_files`, then use
   its character `start` with `read_section`. Use `read_file` for small files.
   Read useful surrounding sections, usually 2,000-6,000 characters. You do not
   need to read every file or reach EOF before editing a relevant function.
   Implement the behavior in `Workspace.execute`
   in `autoproteus/tools.py`, using `self.path` for workspace file paths.
2. Add its name, description, argument properties and required arguments to
   `TOOL_SPECS` in `autoproteus/providers.py`. Both native and JSON descriptions
   use that table; the agent loop normally needs no change for a new tool.
3. Add a focused test file in `tests/`. Check normal behavior and errors, and
   preserve the existing tests and useful behavior.
4. Run `python3 harness/seed.py check` from the task workspace early and after
   edits. Inspect its summary and failure traces; fix failures. Exercise the
   edited tool in a fresh process as described below.
5. Write `feature.md` outside `harness/`, describing the actual source changes
   and checks performed. Documentation alone does not implement a tool.

For example, a tool accepting one required file path uses this table entry:

    "file_summary": ("Count bytes, characters, lines and words in a UTF-8 file.",
                     {"path": STRING}, ["path"]),

That entry describes the tool; implement its behavior and tests separately.
Start a short `todo.txt` checklist for implementation, registration, boundary
tests, documentation, checks/invocation and report. Mark items only when done.
Keep the checklist current so Resume can continue from the actual files.

Run guest tests with one command from the task workspace:

    python3 harness/seed.py check

It runs the candidate's tests and reports counts and bounded failure traces.
Use `cd harness && python3 -m unittest discover -s tests -v` for detailed output.
Edits do not change the tools in your currently running loop. To invoke a tool
from the edited copy, use the same command with its name and a JSON argument
object. For example, after creating a disposable `sample.txt`:

    python3 harness/seed.py check --tool read_file --arguments '{"path":"sample.txt"}'

Replace `read_file` and its arguments with your new tool to test that tool. The
command checks registration in both tool descriptions, then calls the edited
implementation in the current task directory with terminal tools disabled.
Inspect the returned values against your expected result; a successful call
alone does not establish correctness. These editable development checks do not
replace the host's independent checks.

For file tools, test empty files, Unicode and CRLF, the exact character limit
and one character over, invalid UTF-8 and invalid paths. UTF-8 byte counts and
Unicode character counts differ. Open text with `newline=""` when CRLF must be
preserved. Validate before writing; check that rejected writes preserve the
original bytes. Use focused new tests rather than changing existing tests.

The user can check the edited seed against the starter in fresh VMs, then try
it in another session. Your changes cannot replace the host controller. Stop
and starter recovery remain controller operations. In native mode, the external
environment must protect the controller and starter. Testing your own code does not
prove that your change is useful; the host checks task artifacts independently.

File tools use relative workspace paths. `read_file(path)` returns the complete
UTF-8 file, up to 12,000 characters. Larger files require
`read_section(path, start=0, length=1000)`; both positions and lengths are
characters, not bytes. Use `next_start` to continue only when you need more of
the file; stop when you have enough context for the change. CRLF line
endings count as two characters and are preserved. If a whole-file result cannot
fit the model context, it is explicitly omitted; use a smaller section.
`edit_file` replaces exactly one matching fragment. Failed matches return a
match count (capped at 50 with `matches_truncated`), up to three locations and
a recovery hint without changing bytes.
Copy a small unique fragment from the current source, including its actual
indentation and line endings. Terminal access, when enabled, is a
Linux shell. In VM mode there is no general internet or host-drive access.
Native mode does not enforce those restrictions; keep actions within the task.

`search_files(query, path='.')` performs a literal UTF-8 text search, returning
at most 30 short matches with file names, line numbers and character positions.
Search is bounded to 200 files, 2 MiB of input and 2,000 visited entries; narrow
the path when `incomplete` is true. It skips hidden files and outside links.
`delete_file(path)` removes one ordinary task file. Directories are rejected.
Repeated unchanged reads and long sequences of reads receive a progress hint;
they are not automatically stopped. Make a small concrete edit, then verify it rather than repeatedly
inspecting the same source. User instructions remain complete in context;
oversized requests require a shorter task or a larger configured context.

The system prompt shows the tool actions used and remaining in this run. Every
attempt counts, including failed tools and each call in a batch; finishing is
free. After the final action you can inspect its result and report completion.
If more tools are needed, the run pauses with its work saved. Resume keeps the
workspace and gives a fresh allowance. The default is 128 actions; the user's
saved settings can choose a different allowance. Preserve honest test results
and unfinished checklist items rather than rushing a completion claim.
