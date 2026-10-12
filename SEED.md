# Editable AutoProteus seed

This directory is your source copy. The host controller, model connection, user
interface and VM policy are outside it. Your code runs only inside a disposable
Linux VM; it receives model responses through the supplied client.

`seed.py` creates the agent. `autoproteus/agent.py` requests actions and records
their results. `autoproteus/tools.py` implements workspace files and optional
Linux commands. `autoproteus/providers.py` describes guest tools to the model;
it contains no model connection or credentials. `autoproteus/storage.py` keeps
session state. `tests/test_seed.py` exercises the editable behavior.

When asked to improve yourself, change one concrete limitation in this source
copy. Preserve useful existing behavior, add a focused test, and describe what
changed in `feature.md` outside `harness/`. Run guest tests with:

    cd harness && python3 -m unittest discover -s tests -v

The user can check the edited seed against the starter in fresh VMs, then try
it in another session. Your changes cannot replace the host controller. Stop
and starter recovery remain host operations. Testing your own code does not
prove that your change is useful; the host checks task artifacts independently.

File tools use relative workspace paths. `read_file` offsets are UTF-8 bytes;
length is characters, and `next_offset`/`eof` support continuation. `edit_file`
replaces exactly one matching fragment. Terminal access, when enabled, is a
Linux shell inside the VM. There is no general internet or host-drive access.
