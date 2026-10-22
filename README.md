# AutoProteus

**A small, model-agnostic seed for agents that can extend their own tools.**

Run a local model, give it a task, and let it work in a private workspace. AutoProteus can edit a copy of its own harness, test new capabilities, and continue with the edited version. A separate controller manages model connections, isolation and recovery.

AutoProteus is experimental. Small models can produce useful extensions, but reliable autonomous growth remains an open problem. See the [latest comparison results](evaluations/seed-v0.2.1-seed-comparison.md).

[Download ZIP](https://github.com/Chad-Wyck/AutoProteus/archive/refs/heads/main.zip) · [Release notes](CHANGELOG.md) · [Security](SECURITY.md)

## Start

Download and extract the project, then open the launcher for your system:

| System | Launch |
| --- | --- |
| Windows 11, 64-bit | Double-click **Start AutoProteus.cmd** |
| Linux desktop, 64-bit Intel/AMD | Open **Start AutoProteus.desktop**; choose **Allow Launching** or **Run** if prompted |

Follow setup in the browser:

1. Choose a local model, hosted connection, or interactive demo.
2. Prepare your model if needed.
3. Choose **Prepare isolated environment** before the first task.

The launchers handle dependency setup; you do not need to install Python, Ollama or QEMU beforehand. First-time setup needs internet access and space for the model, usually several GB. Later launches reuse the downloads.

- **Windows:** Windows Hypervisor Platform must be enabled. The app explains how to enable it and restart if needed.
- **Linux:** Hardware virtualization and KVM are required. Setup may request administrator permission to install components and grant KVM access.

Linux ARM and macOS are not supported yet.

## Choose a model

| Option | What to expect |
| --- | --- |
| **Local — default** | Download a model through setup, or connect an existing engine. Inference uses your CPU or a compatible GPU. |
| **Hosted** | Connect a compatible chat-completions service with a model name and optional API key. Task data is sent to that provider; charges may apply. |
| **Interactive demo** | Try the interface and file workflow with a scripted agent. No AI model is called. |

Model size, available memory and inference speed affect the experience. A successful connection check confirms communication with the model, not its ability to complete a task or improve the seed.

## Everyday use

- **Describe a task.** Attach inputs with **Files**, or use **Add files** in a stopped session. Imports copy files into the workspace without granting access to the original folder.
- **Review the results.** Preview or download saved files. A model reporting completion is different from an independently checked result.
- **Send a correction while it works.** Choose **Change direction** for the next action boundary, or **Do this afterwards** for a follow-up after completion. Pending messages can be cancelled.
- **Stop and resume.** Stop ends the VM. Resume restores the last saved checkpoint in a fresh VM; changes made after that checkpoint may be lost.
- **Keep your work.** Search, rename or archive sessions. Deleted sessions can be restored from **Saved work & storage**.

Terminal access starts off. Enable it in Settings when a task needs Linux commands inside the VM. Use **Settings → Quit AutoProteus** to close the background controller.

The interface defaults to dark mode, with a light-mode toggle in the top bar.

Session journal downloads include the effective model instructions, tool
definitions and provider exchanges. These can contain your task data. Resume
shows incomplete operation receipts so uncertain work can be inspected before
retrying. Older edited seeds must retain the current input-polling loop to
receive live messages; undelivered messages remain visibly pending.

## Growing the seed

Each task has an editable source copy in `harness/`. Ask the agent to add a capability and test it there. Edits do not replace the running tools automatically.

| Control | Purpose |
| --- | --- |
| **Check edited seed** | Compare the starter and edited copy on fixed tasks. Results cover those tasks; a new capability still needs its own functional checks. |
| **Continue with edited seed** | Restart the same task with the current source copy, saved files and conversation. |
| **Try edited seed in a new VM** | Explore the edited version in a separate session. |
| **Resume with starter seed** | Return to the protected starter while keeping saved task files. |

Stop an active task before switching seeds. After further edits, choose **Continue with edited seed** again to activate the next version.

For implementation and testing details, see the [seed upgrade recipe](SEED.md). Model connections, credentials, the trusted browser interface and execution policy remain outside the editable seed.

## Isolation

By default, code and commands run in a disposable Linux VM with no host-drive mounts or general network access. The controller handles inference and bounded file transfers from outside the VM. Edited seed code is never imported on the host.

VM isolation has limits, and running a downloaded program yourself is outside that boundary. See [SECURITY.md](SECURITY.md) for the threat model, resource limits and recovery behavior.

<details>
<summary><strong>Advanced: Linux without VM protection</strong></summary>

For a disposable machine or an environment you have isolated yourself:

```sh
sh launch.sh --execution native --acknowledge-host-access
```

**Native mode removes AutoProteus's VM protection.** Agent code has the launching account's access to files, networks and credentials. A working directory alone does not restrict it. Review the [native-mode security details](SECURITY.md#explicit-linux-native-mode) before using it.

Add `--no-browser` when using your environment's port forwarding. Native mode is never selected automatically and is not supported on Windows.

</details>

## Files on your computer

| Location | Contents |
| --- | --- |
| `.data/models/` | Managed local model downloads |
| `.data/sessions/` | Saved sessions, journals and file checkpoints |
| `.data/evaluations/` | Saved comparisons and reports |
| `.runtime/` | Downloaded runtimes and VM components |

## Development and research

The editable core lives in `seed.py` and `autoproteus/`. The host controller and interface live in `controller/` and `web/`.

With Python installed, run the ordinary regression suite:

```sh
python -m unittest discover -s tests -v
```

Real VM checks require a prepared WHPX/KVM host and `AUTOPROTEUS_VM_TESTS=1`. GitHub CI runs ordinary checks on Windows and Linux; hardware and empty-cache release checks are separate workflows.

- [Seed upgrade recipe](SEED.md)
- [Local model testing guide](evaluations/model-study.md)
- [Workflow experiments](evaluations/workflow-experiments.md)
- [Experience experiments](evaluations/experience-study.md)
- [Latest seed comparison](evaluations/seed-v0.2.1-seed-comparison.md)
- [Security and execution limits](SECURITY.md)
- [Release notes](CHANGELOG.md)
