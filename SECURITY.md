# AutoProteus isolation boundary

## Threat model

**The isolation guarantees in this document apply to VM mode only.** It is the default. Linux native mode requires `--execution native --acknowledge-host-access` at every launch; missing virtualization never activates it. The UI/API and editable seed cannot select the launch policy through settings or broker operations.

### Explicit Linux native mode

Native mode is for disposable machines or environments isolated by their operator. It runs copied seed code in a separate Linux process with the launching account's permissions. A working directory, environment marker, file-tool checks, separate process and warning are not security boundaries. Same-account code can bypass those checks, access networks and other files, inspect credentials, alter the controller/starter/tests/reports, and defeat recovery. Running as root exposes root's access. Turning off terminal tools does not make edited Python safe.

The native transport still validates messages and quarantines exports during normal operation; it does not make the controller inaccessible to native code. Keys are not deliberately passed to the worker, but same-account access is not prevented. Fresh directories, Stop, deadlines, ordinary-descendant termination and Linux parent-death signals provide best-effort lifecycle handling. They cannot contain deliberately detached processes, hostile resource consumption or controller tampering. Aggregate resource quotas and actual restrictions must come from the external environment. No host mounts, management sockets or broader credentials should be supplied without accepting their exposure.

Native sessions record their mode and retain run history. Reports explicitly mark `isolated: false` and `checks_protected: false`; native regressions and artifact checks are functional diagnostics and may be manipulated by candidate code with account access. VM isolation tests never select native mode. Windows native execution is not supported.

The remaining sections describe VM mode.

Treat all guest code, commands, model responses, harness changes and protocol output as hostile. The host executes `app.py` and `controller/`; it never imports candidate code, `seed.py`, or `autoproteus/`. It owns credentials, provider configuration, UI assets, VM arguments, runtime hashes, quotas, Stop, recovery, and quarantine storage. Source and inputs enter the VM as copied bytes, never host mounts.

VM backends use QEMU 11.1.0/WHPX on x86-64 Windows and distribution-managed QEMU/KVM on x86-64 Linux. No hardware accelerator means no VM execution. Windows Sandbox and full Hyper-V management are not required. Linux setup installs signed distribution packages and, after administrator authorization, grants the launching account KVM group access. The host records the root-owned QEMU executable's path and SHA-256; a changed executable requires preparing isolation again. Guest components and portable Python are checksum-pinned. Setup belongs to the trusted host, never to the editable seed.

Windows QEMU runs in a job. Linux QEMU runs under a separate process-group supervisor, with no-new-privileges, resource limits and QEMU seccomp restrictions on privilege changes, spawning and scheduler changes. The supervisor monitors the controller PID and process start time; pidfds address the actual supervisor for shutdown without signaling a reused PID. Its environment excludes provider keys. The environment marker used by guest code prevents accidental native launch; it is not a security boundary.

## VM policy

The fixed command line selects q35, disables user configuration and default devices, and has no NIC, disk, display, monitor/QMP, clipboard, shared filesystem, USB or device passthrough. A virtual serial port carries bounded broker frames over a private host-loopback socket; the guest has no network interface to access that socket. The kernel and initramfs paths are fixed under `.runtime/isolation/`. Guest code cannot supply arguments or host filenames.

The guest boots into an in-memory appliance. The seed runs as UID/GID 1000 without supplementary groups. Starter source and bootstrap are root-owned; task files are writable. Unprivileged user namespaces are disabled, and process/file-descriptor limits apply. Even compromised guest root remains behind the VM and broker boundaries.

## Broker

The transport is bounded, newline-framed JSON, not a network server, host shell, filesystem server, or URL proxy. Protocol 2 verifies SHA-256 for every source/input file before writing it in the guest. A host file lease serializes VM runs across app, evaluator and test processes; process exit releases the lease. After the boot/input exchange it accepts only:

- `infer`: bounded history and optional guest tool schemas using the host-selected model/provider/settings. Schemas describe guest tools to the model; they never create host capabilities. Guest URL, headers, credentials, commands and environment overrides are rejected. Provider exceptions become generic guest-facing errors to avoid reflecting secrets.
- `file` / `checkpoint`: bounded bytes and validated relative names. The host rejects traversal, absolute paths, Windows device names, alternate data streams, control characters and links. Bytes are stored under host-computed SHA-256 blob filenames. Manifests bind files to one session. No guest archive is extracted on the host; uncommitted exports are discarded on termination.
- `state` / `event`: bounded history/display/journal data. Identity, task, provider, storage roots and policy remain host-owned. The host keeps Stop visible until it ends the VM, even if the guest claims completion.
- `done` / `failure`: completion signals; the host decides termination and final status.

Unknown operations and extra capability fields end the run. Parser, transport and integrity failures fail closed. Only trusted host assets are served as UI. File previews are text and downloads use attachment headers. The evaluator can materialize exported bytes for content checks but never imports or executes them.

Candidate comparisons freeze both versions, model settings and trusted task definitions before execution. New tasks/recovery cannot overlap an active app comparison. Comparisons run candidate code only through the same VM broker; the host checks quarantined artifact bytes against its own definitions. Reports and source diffs are inert data. Model-authored tests, guest journals and reported step counts are not trusted acceptance criteria. A successful comparison does not auto-promote a candidate or prove a new feature. Self-improvement runs may enable guest commands without changing the host isolation boundary or saved preferences.

Before model tasks, the fixed guest bootstrap runs the host's unchanged seed tests from a root-owned directory against the selected modules. Its unprivileged child has no broker descriptor and cannot open the broker device. The protected parent collects the real process exit status and bounded test output. Candidate tests are excluded from this regression suite. Candidate modules still control their behavior and can manipulate test output, so a pass is diagnostic evidence rather than a security proof. Failure rejects the comparison before inference.

## Limits and recovery

| Resource | Limit |
| --- | --- |
| Guest RAM / virtual CPUs | 2 GiB / 2 |
| Windows host job committed memory / CPU | 3 GiB / 25% hard CPU rate |
| Windows host job active processes | 1; children prohibited |
| Linux QEMU address space / CPU time / open files | 4 GiB / 7,200 CPU seconds / 128 |
| Linux QEMU host file writes / core dumps / spawning | zero file-size limit / disabled / seccomp-denied |
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

Stop closes the Windows job or signals the Linux supervisor to kill its whole managed process group. Controller exit/crash closes the Windows job handle or is detected by the Linux supervisor, which terminates the VM. Linux has no Windows-style percentage CPU cap; its two virtual CPUs, CPU-time limit and the broker wall deadline bound execution. An external watchdog also ends blocked or noncooperating guests. Every Resume boots a fresh VM and restores committed files/history. Candidate trials freeze source separately and never install it over the protected starter. Starter recovery drops candidate selection while preserving saved task data.

## Limits of the guarantee

This contains model file operations, arbitrary guest commands/code, malicious upgrades, networking attempts and malformed broker requests. It cannot promise protection from vulnerabilities in the host operating system, hypervisor, emulated devices, trusted host code, or upstream packages. QEMU's website links to the Windows build provider used here; pinned hashes identify downloads, not an independent security audit. Relevant runtime fixes require reviewed pin updates.

The inference engine/provider is trusted and configured separately. A bad seed may waste its bounded requests or produce incorrect results. User-opened downloads, manually launched code, host plugins and human edits to controller/runtime files are outside the boundary. Quarantine/journal storage is bounded per session; many user-created sessions still consume disk space. Passing a task does not make its output trusted.

No email, arbitrary internet, user-selected host folder or other service access exists. Future host capabilities need explicit authorization, narrow broker operations, scopes, quotas and secrets outside the guest. A general host command/URL endpoint or writable mount would change this security model.

## References

- [QEMU security model](https://www.qemu.org/docs/master/system/security.html)
- [QEMU KVM acceleration and Linux seccomp sandbox](https://www.qemu.org/docs/master/system/qemu-manpage.html)
- [QEMU Windows Hypervisor Platform prerequisites](https://www.qemu.org/docs/master/system/whpx.html)
- [Microsoft hypervisor capability probe](https://learn.microsoft.com/en-us/virtualization/api/hypervisor-platform/funcs/whvgetcapability)
- [Windows job resource controls](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-setinformationjobobject)
