# AutoProteus Seed

A small, model-agnostic agent that grows its own harness inside a disposable Linux VM. A separate host controller keeps model connections, credentials, the browser interface, safety policy, and recovery outside the editable seed.

Development releases use **v0.0.x**, incrementing the final number with each release. **v1.0.0** is reserved for launch.

Incomplete model responses never execute partial actions. An output-budget cutoff can use the seed's existing two response-repair retries to request a smaller action. Connection failures, timeouts and repeated invalid responses still stop the run with its checkpoint preserved.

VM isolation is the default. An explicitly acknowledged **Linux native mode** is available for disposable machines and environments isolated by their operator. The security claims below apply to VM mode unless stated otherwise.

## Start

### Windows

On **64-bit Windows 11**, double-click **Start AutoProteus.cmd**. Choose a local model, hosted connection, or scripted demo. Before the first task, choose **Prepare isolated environment**. The app downloads pinned portable QEMU and Linux components into this project, then continues your task. Later runs reuse them.

**Windows Hypervisor Platform must be enabled.** If unavailable, the app explains how to enable it through Windows Features and restart. Portable setup does not install drivers or alter Windows features.

### Linux

On a **64-bit Intel/AMD Linux desktop**, open **Start AutoProteus.desktop** in the downloaded project folder. If your file manager asks, choose **Allow Launching** or **Run**. The launcher takes care of first-time setup and opens the same browser interface used on Windows. No preinstalled Python, Ollama, QEMU, pip packages, or separate setup commands are required.

The setup window explains any administrator prompt before installing missing components through your distribution's package manager and granting your account access to KVM. Ubuntu/Debian, Fedora, Arch and openSUSE package managers are supported. The launcher downloads checksum-pinned private Python into `.runtime/python-linux/`. Choose a local model in the browser to download its engine and weights, then choose **Prepare isolated environment** before the first task. Later launches reuse the setup.

Linux tasks run inside the same diskless, network-free guest appliance, using **QEMU/KVM**. QEMU is managed by the distribution; its executable and the pinned guest image are checked before execution. Model-written code cannot change this host setup or give itself access to host files. Hardware virtualization must be enabled and KVM exposed to the computer; if unavailable, the app explains the next step and refuses VM execution. Native mode is never selected automatically.

First-time setup needs internet access and disk space for the engine and selected model. Local inference can use the CPU when a compatible GPU is unavailable. Linux ARM and macOS VM backends are not included in this release.

The interface starts in dark mode. Use **Light mode** in the top bar to switch;
your browser remembers the choice across launches.

## Advanced execution

### Linux without AutoProteus VM protection

For a disposable Linux machine, container, or cloud workspace you manage, explicitly launch:

```sh
sh launch.sh --execution native --acknowledge-host-access
```

Add `--no-browser` when accessing the loopback interface through your environment's port forwarding. The app prints a warning and displays it persistently. Both flags are required on every controller launch; preferences, model output, container detection and a failed VM launch cannot enable this mode. An already-running app in a different mode must be quit before switching.

**This mode adds no filesystem or network isolation.** Seed code and commands have the account's permissions, even when ordinary file tools restrict paths or terminal access is off. Code may access or modify the controller, starter, other files, credentials, tests and reports. A dedicated computer still exposes everything accessible on that computer. An external container/cloud boundary must be reviewed for host mounts, network access, privileged capabilities, management sockets and secrets. Never assume that a detected container is sufficient protection.

Native runs copy the same seed into a fresh temporary directory and use the existing inference/artifact broker. They do not intentionally inherit provider keys. Stop and shutdown terminate the worker and ordinary command descendants; parent-death cleanup is best effort. Deliberately detached code can evade these controls. There are no AutoProteus-enforced aggregate CPU, memory, disk or network limits in this mode; configure them externally. Session histories and evaluation reports record the execution mode. Native checks are functional evidence only, and are not protected against same-account candidate code.

Automatic model-engine setup works on Windows and Linux. An installed Ollama service, hosted provider, or scripted demo can also be selected. API keys entered in the Linux interface stay in memory for that launch; `AUTOPROTEUS_API_KEY` is also supported. The surrounding native environment must protect keys. Windows native execution is not supported.

Preparing a local model requires several GB. Both launchers can prepare Python automatically, with no pip dependencies. Developers with Python 3.10+ can also use `python app.py --no-browser` to start the controller directly; normal desktop use starts from the platform's Start file.

## Models

- **Local model** is the default. Prepare portable Ollama and Qwen3 4B Instruct, choose the lighter 1.7B model, or connect an existing engine. Ollama runs on the host to use your GPU. The VM receives responses through the broker and cannot access the engine directly.
- **Hosted connection** accepts a compatible chat-completions service, model ID, and optional key. Windows encrypts saved keys with DPAPI; Linux keeps entered keys in memory for that launch. The host keeps provider addresses, credentials, and settings. Hosted requests send task data to the provider and may incur charges.
- **Interactive demo** creates real files using a deterministic script inside the same VM boundary. It does not call an AI model.

Native tool calls and a JSON text fallback share a small action protocol. Incomplete replies never execute actions. Native replies must explicitly call `finish`; plain prose enters a bounded repair loop. Tool compatibility does not guarantee task competence.

The managed local engine keeps one model loaded at a time to reduce GPU memory contention. Closing AutoProteus also ends that engine's runner processes; an existing engine you connected separately remains independently managed. See [Ollama's concurrency settings](https://docs.ollama.com/faq).

## Work and recovery

Every run starts a fresh VM and restores its saved checkpoint as copied bytes. Host drives are never mounted. The VM has no network card, clipboard integration, shared filesystem, display, USB passthrough, or host command channel.

**Terminal access** is initially off. When enabled, commands run as an unprivileged Linux user inside the VM. **Stop** terminates the VM from the host, including noncooperating candidate code. **Resume** starts another VM from the last committed checkpoint; later guest changes may be lost. Use **Settings → Quit AutoProteus** to close the background controller.

Saved files enter a quarantine store as inert blobs. The interface previews text or downloads attachments. It never imports exported code or serves edited seed JavaScript as host UI. **Download saved files** produces an archive. Running a downloaded program yourself is outside the isolation boundary.

Exports are limited to 2 MiB per file, 500 files, and 32 MiB per checkpoint. The VM receives 2 GiB RAM, two virtual CPUs, and a 512 MiB task filesystem in RAM. External process, CPU, memory, transfer, journal, model-request, and one-hour runtime limits apply. One task runs at a time. “Finished” reflects the model's report; review outputs or use independent checks.

Conversation history stays bounded by a conservative estimate of serialized UTF-8 bytes, including the system prompt and native tool schemas, with room reserved for the response. The complete original request and latest human follow-up stay in context. Repair and Resume notices are tagged separately so they cannot displace that follow-up. Legacy journals recognize recorded human inputs and old internal notices. Provenance stays in the journal and is removed from provider requests. If the required inputs alone exceed the estimate, the task stops with a settings hint. This is an estimate rather than an exact tokenizer for every model. Older history may be trimmed; the full journal remains on disk. Source files use LF line endings on Windows and Linux so exact source edits see consistent text.

Checkpoints transfer changed conversation tails rather than resending the full growing history. The host validates the reconstructed state under the same limits, and the full journal is retained. Temporary test files that disappear during a checkpoint no longer interrupt the run.

An active task keeps a visible Stop control even after choosing New task or viewing another session. Conflicting starts are rejected before a new session is created. The interface identifies local or hosted inference and defaults to dark mode, with a light-mode toggle. Saved sessions support title search, pagination, renaming and archiving. Delete moves a session to recoverable Trash; **Saved work & storage** shows usage and restores it. Histories load on demand and polling transfers new conversation entries rather than full model context.

Use **Files** to copy inputs into a new task, or **Add files** in a stopped session. Imports are inert bytes in quarantine; they do not grant access to the original host folder. The same 2 MiB/file, 500-file and 32 MiB/checkpoint limits include the editable seed. Existing names and `harness/` cannot be overwritten by imports.

Connecting or preparing a model checks the selected native-tool or JSON protocol with a harmless two-request tool/result exchange. Protocol-related settings are checked before saving. Failed checks report a connection, timeout, cutoff, context or protocol category without exposing provider response bodies or credentials. Compatibility confirms that exchange, not task competence; AutoProteus never silently switches protocols.

## Growing the seed

Each workspace has `harness/`, a small copy of the editable source: `seed.py`, the agent, tools, session storage, tool descriptions, guest documentation, and tests. Model adapters, download/setup code, browser assets and evaluation definitions remain outside this copy. The model edits its seed without overwriting the protected starter or controller.

File capabilities can reuse `Workspace.read_text` and `Workspace.write_text` for bounded UTF-8 access, preserved line endings and workspace validation. `TEXT_CHARACTER_LIMIT` counts Unicode characters; encoded byte counts may be larger. The public `write_file` uses the same write helper. See the [seed upgrade recipe](SEED.md).

**Check edited seed** compares the starter with that frozen source copy using the connected real model. The same sixteen tasks run in fresh VMs, twice by default; order alternates between repeats. They include file recreation, source search, long files, follow-up corrections, multiple files and interruption/resume. The bug-fix check calls the submitted function with several inputs in a fresh guest instead of accepting a matching comment. The host checks saved file bytes independently and records source fingerprints, configuration, runtime identity, model digest and engine version when available, changes, successes, failures, reads, time and reported steps. A comparison can take several minutes and hosted requests may incur charges. **Stop checks** saves incomplete results. Checks use a separate store and never activate a candidate. A new feature still requires independent functional review beyond these existing tasks. Saved comparisons can be reopened from the source panel after restarting the app.

The optional [role diagnostic](evaluations/role-check.py) asks "Who are you, and what is your role?" at the start and after a separate file task, using cached models from the local benchmark plan. It preserves answers and distinguishes role wording from the required completion protocol. It runs outside the editable seed and is not an upgrade acceptance or safety check. See the [initial findings](evaluations/role-check-findings.md).

Before any model task, a protected guest driver runs the unchanged starter tests against each version. The candidate cannot edit those test files or the driver. A failed regression stops the comparison and shows its output. These checks help catch breakage; they do not prove a hostile candidate honest or make its new tests authoritative.

**Continue with edited seed** freezes the current checkpoint and restarts the same task with that source, saved files and conversation history. Stop an active run first. Resume keeps the activated version; use the same control after further edits to activate the next version. The controller owns each restart, tells the agent when its edited seed is active, and uses the same selected execution policy. **Try edited seed in a new VM** remains available for a separate trial session. **Resume with starter seed** restores the protected starter while keeping saved task files. Candidates cannot supply VM arguments, enable host mounts, obtain keys, choose host commands or URLs, or change export locations. The controller never imports a candidate.

The browser interface and `controller/` are maintained by the human developer. Generated interfaces remain guest artifacts. Additional host capabilities, such as email, will need separately implemented, explicitly authorized broker operations. The current broker exposes only inference, bounded session events/state, and artifacts.

`read_file(path)` returns the whole UTF-8 file up to 12,000 characters, and rejects larger files instead of truncating them. `read_section(path, start=0, length=1000)` reads a chosen section of up to 12,000 characters. Both `start` and `length` count characters. Search and read useful surrounding sections; continue at `next_start` only when more of the file is needed. Unicode and original line endings are preserved. Whole-file results that cannot fit the model context are explicitly omitted with a section-reading hint. This replaces the older byte-offset `read_file` API; existing candidate copies retain their own implementation. `edit_file` replaces exactly one matching fragment, preserving surrounding bytes and line endings. Failed matches return a count, up to three locations and a recovery hint; they never apply an approximate replacement. Writes and edits are limited to 100,000 characters. Checklists in `todo.txt` are optional. The main tool dispatch stays short; existing search and terminal machinery lives in plainly named helpers.

From the task workspace, `python3 harness/seed.py check` runs the edited copy's tests and returns a compact count and useful failure traces. Run it early and after changes. Add `--tool TOOL_NAME --arguments '{"path":"sample.txt"}'` with the actual tool's arguments to check registration in both descriptions and invoke the edited implementation on a disposable sample file. This runs in a new guest process; edited tools do not replace those in the running loop. Check returned values and Unicode/CRLF, exact-limit and rejected-write behavior. Editable development checks support repair during a task; protected regressions and independent feature checks still determine acceptance.

New installations default to **128 tool actions per run**, a **32,768-token context**, **8,192 response tokens**, and a 300-second model timeout. Saved preferences are preserved. In Settings, **Allow longer upgrades** selects these allowances; review and save to apply them to an existing installation. Limits remain individually adjustable. Compare 4,096 versus 8,192 response tokens at the same context and action allowance before attributing a gain to either limit. Larger supported contexts still need memory and performance measurements on the selected hardware. Opening instructions stay stable across actions; current checklist state and an exhaustion notice belong after the conversation history. This runtime context is included when it fits without displacing user instructions. Failed calls and each tool in a batch count; finishing is free, with one final opportunity to inspect the last result and report completion. A further tool request at zero pauses the saved task. Resume keeps its files and gives a fresh allowance. Host VM, time and request limits remain outside the editable seed.

The seed's `TOOL_SPECS` table supplies both native and JSON descriptions. To add a tool, implement its dispatch, add one table entry and focused tests, then follow the short recipe in the copied `harness/README.md`. Give a concise final explanation and update usage documentation where needed; a separate `feature.md` report is not required. Upgrade evaluators assemble filenames, diffs, fingerprints and recorded command results on the host. Guest commands remain diagnostic; protected regressions and independent feature checks remain required. The host forwards descriptions as data and never imports the editable modules.

`search_files(query, path=".")` searches a literal in bounded UTF-8 files and returns paths, lines, snippets and character starts usable with `read_section`. It reads at most 200 files / 2 MiB, visits at most 2,000 entries, skips links and hidden files, and returns at most 30 matches. `delete_file(path)` deletes one ordinary workspace file. Three identical consecutive reads, or each eight consecutive successful reads/searches without another action, receive a progress hint; this does not force a stop or change the model's tools.

## Files

| Path | Purpose |
| --- | --- |
| `app.py`, `launch.ps1`, `launch.sh`, `Start AutoProteus.desktop` | Host launchers and explicit execution choice |
| `controller/` | Host UI/API, credentials, inference, VM policy, broker |
| `guest/worker.py` | Shared VM/native bootstrap and communication adapter |
| `seed.py`, `autoproteus/` | Editable guest entry point, agent and tools |
| `web/` | Trusted host interface, outside the editable seed |
| `SEED.md` | Copied into the guest as `harness/README.md` |
| `controller/evaluation.py`, `evaluations/` | Protected artifact checks and evaluation definitions |
| `.data/evaluations/checks/` | Frozen comparisons, diffs, reports and isolated evaluation sessions |
| `.data/sessions/<id>/` | Session state, journal, quarantined artifact blobs |
| `.data/models/` | Managed local model cache |
| `.data/native-runs/` | Temporary native workers; not a sandbox |
| `.runtime/isolation/` | VM engine, kernel, and guest appliance |
| `.runtime/` | Portable Python, Ollama, and download caches |
| `old/` | Earlier experiments, untouched |

Existing sessions and model downloads are preserved. Legacy files can be previewed; resuming copies their contents into the environment explicitly selected at launch. Oversized legacy inputs must be reduced before migration. Execution history retains prior native runs even if a later resume uses VM mode.

## Verify

GitHub CI runs ordinary tests on Windows and Linux, plus interface syntax checks. The manual **Hardware VM checks** workflow uses a prepared self-hosted runner labelled `autoproteus-vm` and `linux` or `windows`. Review the selected revision before dispatching it: this lane runs trusted repository code with hardware access. It is never triggered automatically by pull requests. The runner needs Python 3.13, internet for pinned appliance setup, and working KVM or WHPX. It runs the real VM checks, including identical-byte file recreation and functional grading.

`python -m unittest discover -s tests -v` runs regression and broker tests. Set `AUTOPROTEUS_VM_TESTS=1` on a prepared Windows/WHPX or Linux/KVM host to include real VM checks for host file visibility, networking, guest privilege, forged exports, Stop, restoration, and recovery. `tests/test_linux.py` also covers Linux runtime integrity and managed engine cleanup. Guest tests copied into `harness/tests/` run inside the VM; controller tests stay on the host.

On Linux, `python3 -m unittest discover -s tests -p test_native.py -v` runs trusted, offline native-worker fixtures for consent, startup, broker exports, checkpoint restoration, functional regressions, Stop and ordinary parent-exit cleanup. These are not hostile-code isolation tests. To evaluate the demo without a VM:

```sh
python3 evaluate.py --execution native --acknowledge-host-access
```

The evaluator accepts the same launch flags for live/candidate trials. Reports include `execution_mode`, `isolated`, `checks_protected` and the warning. Native regression passes do not claim immutable tests or a protected controller. Runtime fingerprints from a VM installation are not evidence for native execution.

`python evaluate.py` checks the scripted demo inside the VM. `--live` uses the configured model with independent artifact checks; `--model MODEL_NAME` selects another model without changing preferences, including a cached local model while the app is in demo mode. `--task exact-file` selects one task, `--repeat 2` repeats tasks, and `--candidate SESSION_ID` compares a saved editable copy with the starter. Hosted evaluations may incur charges. VM execution is serialized across the app, evaluator and tests. Input bytes are integrity-checked before guest source is loaded.

`python evaluate.py --live --model qwen3:4b-instruct --self-improve --max-steps 128 --context-tokens 32768 --response-tokens 8192 --timeout 2700` runs a feature trial with Linux commands enabled inside the VM, without changing saved preferences. The model can run its guest tests. Match context, output and timeout settings to the model and hardware. A ready submission reports `REVIEW`, `passed: null`, and exit code 2 until independent functional checks are recorded. Candidate code never executes on the host. Reports, source snapshots and diffs are saved under `.data/evaluations/runs/`. Guest tests and journals are diagnostics; host artifact checks determine task success. Comparisons establish performance on the checked tasks, not general capability or security of a candidate.

The saved local-model benchmark accepts `--upgrade-steps` (default 128), `--response-tokens` (8,192), `--context-tokens` (32,768), `--temperature` (0.6), `--thinking auto|on|off` and `--timeout` (2,700 seconds per upgrade). Ordinary tasks keep their 32-action comparison limit. Use separate data directories for different settings; resuming a batch refuses to mix them. Frozen source and task JSON can be supplied from `.data/` for controlled experiments. Reports retain source fingerprints, settings and independent results. Earlier published results retain their original 48-action/4,096-response-token settings.

See [SECURITY.md](SECURITY.md) for the threat model and limits. Virtualization provides an operating-system boundary, but cannot guarantee immunity to hypervisor or host OS vulnerabilities.

The [v0.3 findings](evaluations/seed-v0.3-findings.md) record the seed reduction, local-model measurements, and rejected self-improvement attempts, including limitations of the comparison.

The [v0.6 local findings](evaluations/seed-v0.6-local-findings.md) compare the cached Qwen3.5 9B with K2-Horizon 7B on the expanded suite and repeated feature upgrades, including independent functional checks and a targeted JSON fallback diagnostic.

The [v0.0.10 local findings](evaluations/seed-v0.0.10-local-findings.md) record 32 fresh Qwen3.5 9B feature attempts, checkpoint fixes, shared text helpers and further growth trials. Some extensions now pass independent checks, but consistent autonomous improvement remains unproven.

## Runtime sources

VM downloads and SHA-256 hashes are pinned in `controller/runtime-lock.json`. Managed Python and Ollama versions, URLs and hashes are pinned in `controller/managed-runtime-lock.json`: Windows Python 3.13.12, Linux Python 3.13.16, and Ollama 0.40.4. Hashes are checked before extraction. Installed private runtimes are inventoried and verified before reuse, including libraries and added or missing files. An old unrecorded engine is replaced through verified setup while preserving model weights; damaged runtimes stop or require verified setup. Independently installed model services remain user-managed and are not covered by these private-runtime manifests.

Pin updates require reviewing official upstream metadata, changing the version/URL/hash together, synchronizing the Linux launcher's Python pin, and repeating launcher, integrity and hardware checks. Pins identify selected bytes; upstream suppliers and security updates still require review.

- [QEMU downloads](https://www.qemu.org/download/#windows), [WHPX backend](https://www.qemu.org/docs/master/system/whpx.html), and [Windows build provider](https://qemu.weilnetz.de/w64/)
- [Alpine Linux releases](https://alpinelinux.org/releases/)
- [Ollama Windows distribution](https://docs.ollama.com/windows), [Linux distribution](https://docs.ollama.com/linux), and [chat API](https://docs.ollama.com/api/chat)
- [Python portable distribution](https://www.python.org/downloads/release/python-31312/)
