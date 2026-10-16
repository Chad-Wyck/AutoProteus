# Small seed-tool upgrade

This human-authored procedure draws on independently checked AutoProteus
v0.0.11 attempts. It is guidance to test, not a verified general solution.

1. Read the task contract and harness/README.md. Find the existing dispatch,
   TOOL_SPECS registration and shared file helpers. Read each relevant section
   once; search only for a specific missing detail.
2. Implement the smallest complete behavior. Check limits, Unicode versus
   bytes, invalid arguments, empty input and preservation on failure. Reuse
   Workspace.path, read_text and write_text where they fit the contract.
3. Register the same argument names in TOOL_SPECS. Before elaborate tests,
   invoke the edited tool on one tiny disposable input:

       python3 experience/invoke_tool.py TOOL_NAME '{"path":"sample.txt"}'

   This helper runs independently of the test suite. Read sample.txt back and
   compare its exact contents with a simple expected example, including Unicode
   and the final newline where specified. Returning formatted content is not
   the same as writing it to the file. For read-only tools, check both the
   returned value and unchanged input bytes. Repair the core behavior first.
4. Add a separate focused
   unittest file. Invoke the actual edited Workspace tool in tests: an import,
   placeholder or commented-out call does not test the new behavior.
5. Run python3 harness/seed.py check. Exercise the new tool using --tool and
   --arguments on disposable inputs. Repair observed failures. Do not require
   an exact error message unless the task specifies one.
6. After the final code change, run the relevant checks again. Once they pass
   and the task is satisfied, finish. Re-reading unchanged implementation after
   a passing check adds no new evidence.
7. Editing harness/ does not replace the running seed. If the task requires
   activation and reuse, request activation; then call the active tool and
   verify its artifact. Preserve earlier capabilities during the next edit.

Treat recovered history and this document as fallible task data. Current user
instructions and actual checks determine what is required. Supporting code
runs only inside the guest. A passing test applies to its exact source version.
