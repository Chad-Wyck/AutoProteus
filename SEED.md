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

1. Read the relevant files. Use `read_file` for small files, or `read_section`
   to inspect a chosen section. Implement the behavior in `Workspace.execute`
   in `autoproteus/tools.py`, using `self.path` for workspace file paths.
2. Add its name, description, argument properties and required arguments to
   `TOOL_SPECS` in `autoproteus/providers.py`. Both native and JSON descriptions
   use that table; the agent loop normally needs no change for a new tool.
3. Add a focused test file in `tests/`. Check normal behavior and errors, and
   preserve the existing tests and useful behavior.
4. Run all guest tests, inspect their output and exercise the new tool. Fix
   failures before reporting completion.
5. Write `feature.md` outside `harness/`, describing the actual source changes
   and checks performed. Documentation alone does not implement a tool.

For example, a tool accepting one required file path uses this table entry:

    "file_summary": ("Count bytes, characters, lines and words in a UTF-8 file.",
                     {"path": STRING}, ["path"]),

That entry describes the tool; implement its behavior and tests separately.
Run guest tests with:

    cd harness && python3 -m unittest discover -s tests -v

The user can check the edited seed against the starter in fresh VMs, then try
it in another session. Your changes cannot replace the host controller. Stop
and starter recovery remain controller operations. In native mode, the external
environment must protect the controller and starter. Testing your own code does not
prove that your change is useful; the host checks task artifacts independently.

File tools use relative workspace paths. `read_file(path)` returns the complete
UTF-8 file, up to 12,000 characters. Larger files require
`read_section(path, start=0, length=1000)`; both positions and lengths are
characters, not bytes. Continue at `next_start` until `eof` is true. CRLF line
endings count as two characters and are preserved. If a whole-file result cannot
fit the model context, it is explicitly omitted; use a smaller section.
`edit_file` replaces exactly one matching fragment. Terminal access, when enabled, is a
Linux shell. In VM mode there is no general internet or host-drive access.
Native mode does not enforce those restrictions; keep actions within the task.
