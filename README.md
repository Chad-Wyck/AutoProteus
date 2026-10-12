# AutoProteus Seed

A small, model-agnostic agent that grows its own harness inside a disposable Linux VM. A separate host controller keeps model connections, credentials, the browser interface, safety policy, and recovery outside the editable seed.

## Start

On **64-bit Windows 11**, double-click **Start AutoProteus.cmd**. Choose a local model, hosted connection, or scripted demo. Before the first task, choose **Prepare isolated environment**. The app downloads pinned portable QEMU and Linux components into this project, then continues your task. Later runs reuse them.

**Windows Hypervisor Platform must be enabled.** This backend works on the tested Windows 11 Home PC using its existing hardware virtualization. If unavailable, the app explains how to enable it through Windows Features and restart. Enabling that Windows feature may require administrator access; portable setup does not install drivers or alter Windows features. There is no software-emulation or native-host execution fallback.

Isolation downloads are about 290 MB. Preparing a local model requires several additional GB. The launcher can download official portable Python if Python 3.10+ is unavailable. No pip packages are required. `python app.py --no-browser` starts the protected controller directly. Other operating systems currently cannot execute agent tasks through this backend.

## Models

- **Local model** is the default. Prepare portable Ollama and Qwen3 4B Instruct, choose the lighter 1.7B model, or connect an existing engine. Ollama runs on the host to use your GPU. The VM receives responses through the broker and cannot access the engine directly.
- **Hosted connection** accepts a compatible chat-completions service, model ID, and optional key. Keys are encrypted with Windows DPAPI. The host keeps provider addresses, credentials, and settings. Hosted requests send task data to the provider and may incur charges.
- **Interactive demo** creates real files using a deterministic script inside the same VM boundary. It does not call an AI model.

Native tool calls and a JSON text fallback share a small action protocol. Incomplete replies never execute actions. Native replies must explicitly call `finish`; plain prose enters a bounded repair loop. Tool compatibility does not guarantee task competence.

The managed local engine keeps one model loaded at a time to reduce GPU memory contention. Closing AutoProteus also ends that engine's runner processes; an existing engine you connected separately remains independently managed. See [Ollama's concurrency settings](https://docs.ollama.com/faq).

## Work and recovery

Every run starts a fresh VM and restores its saved checkpoint as copied bytes. Host drives are never mounted. The VM has no network card, clipboard integration, shared filesystem, display, USB passthrough, or host command channel.

**Terminal access** is initially off. When enabled, commands run as an unprivileged Linux user inside the VM. **Stop** terminates the VM from the host, including noncooperating candidate code. **Resume** starts another VM from the last committed checkpoint; later guest changes may be lost. Use **Settings → Quit AutoProteus** to close the background controller.

Saved files enter a quarantine store as inert blobs. The interface previews text or downloads attachments. It never imports exported code or serves edited seed JavaScript as host UI. **Download saved files** produces an archive. Running a downloaded program yourself is outside the isolation boundary.

Exports are limited to 2 MiB per file, 500 files, and 32 MiB per checkpoint. The VM receives 2 GiB RAM, two virtual CPUs, and a 512 MiB task filesystem in RAM. External process, CPU, memory, transfer, journal, model-request, and one-hour runtime limits apply. One task runs at a time. “Finished” reflects the model's report; review outputs or use independent checks.

## Growing the seed

Each workspace has `harness/`, a small copy of the editable source: `seed.py`, the agent, tools, session storage, tool descriptions, guest documentation, and tests. Model adapters, download/setup code, browser assets and evaluation definitions remain outside this copy. The model edits its seed without overwriting the protected starter or controller.

**Check edited seed** compares the starter with that frozen source copy using the connected real model. The same ten tasks run in fresh VMs, twice by default; order alternates between repeats. The host checks saved file bytes independently and records source fingerprints, configuration, runtime identity, changes, successes, failures, time and reported steps. A comparison can take several minutes and hosted requests may incur charges. **Stop checks** saves incomplete results. Checks use a separate store and never activate a candidate. A new feature still requires independent functional review beyond these existing tasks. Saved comparisons can be reopened from the source panel after restarting the app.

Before any model task, a protected guest driver runs the unchanged starter tests against each version. The candidate cannot edit those test files or the driver. A failed regression stops the comparison and shows its output. These checks help catch breakage; they do not prove a hostile candidate honest or make its new tests authoritative.

**Try edited seed in a new VM** freezes that version and opens a separate session under the same policy. **Resume with starter seed** ends the candidate VM and resumes with the protected starter, keeping saved task files. Candidates cannot supply VM arguments, enable host mounts, obtain keys, choose host commands or URLs, or change export locations. The controller never imports a candidate.

The browser interface and `controller/` are maintained by the human developer. Generated interfaces remain guest artifacts. Additional host capabilities, such as email, will need separately implemented, explicitly authorized broker operations. The current broker exposes only inference, bounded session events/state, and artifacts.

`read_file` offsets are UTF-8 bytes; length is characters (default 1,000, maximum 12,000). Continue using `next_offset` until `eof`. `edit_file` replaces exactly one matching fragment, preserving surrounding bytes and line endings. Writes and edits are limited to 100,000 characters. Optional checklists use `todo.txt`.

## Files

| Path | Purpose |
| --- | --- |
| `app.py`, `launch.ps1` | Protected host launcher |
| `controller/` | Host UI/API, credentials, inference, VM policy, broker |
| `guest/worker.py` | Guest bootstrap and communication adapter |
| `seed.py`, `autoproteus/` | Editable guest entry point, agent and tools |
| `web/` | Trusted host interface, outside the editable seed |
| `SEED.md` | Copied into the guest as `harness/README.md` |
| `controller/evaluation.py`, `evaluations/` | Protected artifact checks and evaluation definitions |
| `.data/evaluations/checks/` | Frozen comparisons, diffs, reports and isolated evaluation sessions |
| `.data/sessions/<id>/` | Session state, journal, quarantined artifact blobs |
| `.data/models/` | Managed local model cache |
| `.runtime/isolation/` | VM engine, kernel, and guest appliance |
| `.runtime/` | Portable Python, Ollama, and download caches |
| `old/` | Earlier experiments, untouched |

Existing sessions and model downloads are preserved. Legacy files can be previewed; resuming copies their contents into a VM. Oversized legacy inputs must be reduced before migration. No session resumes natively.

## Verify

`python -m unittest discover -s tests -v` runs regression and broker tests. Set `AUTOPROTEUS_VM_TESTS=1` on a prepared Windows host to include real VM checks for host file visibility, networking, guest privilege, forged exports, Stop, restoration, and recovery. Guest tests copied into `harness/tests/` run inside the VM; controller tests stay on the host.

`python evaluate.py` checks the scripted demo inside the VM. `--live` uses the configured model with independent artifact checks; `--model MODEL_NAME` selects another model without changing preferences, including a cached local model while the app is in demo mode. `--task exact-file` selects one task, `--repeat 2` repeats tasks, and `--candidate SESSION_ID` compares a saved editable copy with the starter. Hosted evaluations may incur charges. VM execution is serialized across the app, evaluator and tests. Input bytes are integrity-checked before guest source is loaded.

`python evaluate.py --live --model qwen3:4b-instruct --self-improve --max-steps 64 --timeout 900` runs a small feature trial with Linux commands enabled inside the VM, without changing saved preferences. The model can run its guest tests. A ready submission reports `REVIEW`, `passed: null`, and exit code 2 until independent functional checks are recorded. Candidate code never executes on the host. Reports, source snapshots and diffs are saved under `.data/evaluations/runs/`. Guest tests and journals are diagnostics; host artifact checks determine task success. Comparisons establish performance on the checked tasks, not general capability or security of a candidate.

See [SECURITY.md](SECURITY.md) for the threat model and limits. Virtualization provides an operating-system boundary, but cannot guarantee immunity to hypervisor or host OS vulnerabilities.

The [v0.3 findings](evaluations/seed-v0.3-findings.md) record the seed reduction, local-model measurements, and rejected self-improvement attempts, including limitations of the comparison.

## Runtime sources

Downloads and SHA-256 hashes are pinned in `controller/runtime-lock.json`. Hashes are checked before extraction and installed components before execution. Pins identify the selected bytes; upstream suppliers and security updates still require review.

- [QEMU downloads](https://www.qemu.org/download/#windows), [WHPX backend](https://www.qemu.org/docs/master/system/whpx.html), and [Windows build provider](https://qemu.weilnetz.de/w64/)
- [Alpine Linux releases](https://alpinelinux.org/releases/)
- [Ollama Windows distribution](https://docs.ollama.com/windows) and [chat API](https://docs.ollama.com/api/chat)
- [Python portable distribution](https://www.python.org/downloads/release/python-31312/)
