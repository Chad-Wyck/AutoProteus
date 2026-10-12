# AutoProteus isolation boundary

## Threat model

Treat all guest code, commands, model responses, harness changes and protocol output as hostile. The host executes `app.py` and `controller/`; it never imports candidate code, `seed.py`, or `autoproteus/`. It owns credentials, provider configuration, UI assets, VM arguments, runtime hashes, quotas, Stop, recovery, and quarantine storage. Source and inputs enter the VM as copied bytes, never host mounts.

The supported backend is QEMU 11.1.0 using WHPX hardware virtualization on x86-64 Windows. No accelerator means no execution. Windows Sandbox and full Hyper-V management are not required. QEMU runs as an ordinary user in a Windows job, with a minimal host environment that excludes provider keys. The environment marker used by guest code prevents accidental native launch; it is not a security boundary.

## VM policy

The fixed command line selects q35, disables user configuration and default devices, and has no NIC, disk, display, monitor/QMP, clipboard, shared filesystem, USB or device passthrough. A virtual serial port connects to bounded host process pipes. The kernel and initramfs paths are fixed under `.runtime/isolation/`. Guest code cannot supply arguments or host filenames.

The guest boots into an in-memory appliance. The seed runs as UID/GID 1000 without supplementary groups. Starter source and bootstrap are root-owned; task files are writable. Unprivileged user namespaces are disabled, and process/file-descriptor limits apply. Even compromised guest root remains behind the VM and broker boundaries.

## Broker

The transport is bounded, newline-framed JSON, not a network server, host shell, filesystem server, or URL proxy. After the boot/input exchange it accepts only:

- `infer`: bounded history and optional guest tool schemas using the host-selected model/provider/settings. Schemas describe guest tools to the model; they never create host capabilities. Guest URL, headers, credentials, commands and environment overrides are rejected. Provider exceptions become generic guest-facing errors to avoid reflecting secrets.
- `file` / `checkpoint`: bounded bytes and validated relative names. The host rejects traversal, absolute paths, Windows device names, alternate data streams, control characters and links. Bytes are stored under host-computed SHA-256 blob filenames. Manifests bind files to one session. No guest archive is extracted on the host; uncommitted exports are discarded on termination.
- `state` / `event`: bounded history/display/journal data. Identity, task, provider, storage roots and policy remain host-owned. The host keeps Stop visible until it ends the VM, even if the guest claims completion.
- `done` / `failure`: completion signals; the host decides termination and final status.

Unknown operations and extra capability fields end the run. Parser, transport and integrity failures fail closed. Only trusted host assets are served as UI. File previews are text and downloads use attachment headers. The evaluator can materialize exported bytes for content checks but never imports or executes them.

## Limits and recovery

| Resource | Limit |
| --- | --- |
| Guest RAM / virtual CPUs | 2 GiB / 2 |
| Host job committed memory / CPU | 3 GiB / 25% hard CPU rate |
| Host job active processes | 1; children prohibited |
| Task filesystem | 512 MiB tmpfs; seed user cannot remount it |
| Guest user processes / open files | 128 / 256 |
| Wall time / startup handshake | 1 hour / 90 seconds |
| Frame / cumulative guest output | 4 MiB / 100 MiB |
| Model requests | configured steps + two repairs, maximum 202 |
| Model history | 400 messages / 1.5 MB serialized per request |
| Export file / count / checkpoint | 2 MiB / 500 / 32 MiB |
| Exported bytes per run | 32 MiB |
| Session journal | 64 MiB |
| Guest state / protocol messages | 1.5 MB / 10,000 messages per run |

Stop closes the VM's host job. Controller exit/crash closes its job handle and terminates the VM. An external watchdog also ends blocked or noncooperating guests. Every Resume boots a fresh VM and restores committed files/history. Candidate trials freeze source separately and never install it over the protected starter. Starter recovery drops candidate selection while preserving saved task data.

## Limits of the guarantee

This contains model file operations, arbitrary guest commands/code, malicious upgrades, networking attempts and malformed broker requests. It cannot promise protection from vulnerabilities in Windows, the hypervisor, emulated devices, trusted host code, or upstream packages. QEMU's website links to the Windows build provider used here; pinned hashes identify downloads, not an independent security audit. Relevant runtime fixes require reviewed pin updates.

The inference engine/provider is trusted and configured separately. A bad seed may waste its bounded requests or produce incorrect results. User-opened downloads, manually launched code, host plugins and human edits to controller/runtime files are outside the boundary. Quarantine/journal storage is bounded per session; many user-created sessions still consume disk space. Passing a task does not make its output trusted.

No email, arbitrary internet, user-selected host folder or other service access exists. Future host capabilities need explicit authorization, narrow broker operations, scopes, quotas and secrets outside the guest. A general host command/URL endpoint or writable mount would change this security model.

## References

- [QEMU security model](https://www.qemu.org/docs/master/system/security.html)
- [QEMU Windows Hypervisor Platform prerequisites](https://www.qemu.org/docs/master/system/whpx.html)
- [Microsoft hypervisor capability probe](https://learn.microsoft.com/en-us/virtualization/api/hypervisor-platform/funcs/whvgetcapability)
- [Windows job resource controls](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-setinformationjobobject)
