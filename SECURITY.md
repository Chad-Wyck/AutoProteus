# AutoProteus isolation boundary

## Threat model

**The isolation guarantees in this document apply to VM mode only.** It is the default. Linux native mode requires `--execution native --acknowledge-host-access` at every launch; missing virtualization never activates it. The UI/API and editable seed cannot select the launch policy through settings or broker operations.

### Explicit Linux native mode

Native mode is for disposable machines or environments isolated by their operator. It runs copied seed code in a separate Linux process with the launching account's permissions. A working directory, environment marker, file-tool checks, separate process and warning are not security boundaries. Same-account code can bypass those checks, access networks and other files, inspect credentials, alter the controller/starter/tests/reports, and defeat recovery. Running as root exposes root's access. Turning off terminal tools does not make edited Python safe.

The native transport still validates messages and quarantines exports during normal operation; it does not make the controller inaccessible to native code. Keys are not deliberately passed to the worker, but same-account access is not prevented. Fresh directories, Stop, deadlines, ordinary-descendant termination and Linux parent-death signals provide best-effort lifecycle handling. They cannot contain deliberately detached processes, hostile resource consumption or controller tampering. Aggregate resource quotas and actual restrictions must come from the external environment. No host mounts, management sockets or broader credentials should be supplied without accepting their exposure.

Native sessions record their mode and retain run history. Reports explicitly mark `isolated: false` and `checks_protected: false`; native regressions and artifact checks are functional diagnostics and may be manipulated by candidate code with account access. VM isolation tests never select native mode. Windows native execution is not supported.

The remaining sections describe VM mode.

Treat all guest code, commands, model responses, harness changes and protocol output as hostile. The host executes `app.py` and `controller/`; it never imports candidate code, `seed.py`, or `autoproteus/`. It owns credentials, provider configuration, UI assets, VM arguments, runtime hashes, quotas, Stop, recovery, and quarantine storage. Source and inputs enter the VM as copied bytes, never host mounts.

Optional research profiles under `evaluations/` can start an owned inference
service from a trusted operator-supplied command and pinned assets. These are
host programs, not sandboxed guest tools; their manifests must not come from
candidate output. Windows jobs and the existing Linux supervisor manage their
lifecycle, while memory/startup guards improve operation rather than create a
new security boundary. Guests cannot select these commands, process settings,
or frozen research response instructions through broker frames. Host-derived
plain-reply labels affect display only and grant neither completion credit nor
new authority.

VM backends use QEMU 11.1.0/WHPX on x86-64 Windows and distribution-managed QEMU/KVM on x86-64 Linux. No hardware accelerator means no VM execution. Windows Sandbox and full Hyper-V management are not required. Linux setup installs signed distribution packages and, after administrator authorization, grants the launching account KVM group access. The host records the root-owned QEMU executable's path and SHA-256; a changed executable requires preparing isolation again. Guest components and portable Python are checksum-pinned. Setup belongs to the trusted host, never to the editable seed.

Windows QEMU runs in a job. Linux QEMU runs under a separate process-group supervisor, with no-new-privileges, resource limits and QEMU seccomp restrictions on privilege changes, spawning and scheduler changes. The supervisor monitors the controller PID and process start time; pidfds address the actual supervisor for shutdown without signaling a reused PID. Its environment excludes provider keys. The environment marker used by guest code prevents accidental native launch; it is not a security boundary.

## VM policy

The fixed command line selects q35, disables user configuration and default devices, and has no NIC, disk, display, monitor/QMP, clipboard, shared filesystem, USB or device passthrough. A virtual serial port carries bounded broker frames over a private host-loopback socket; the guest has no network interface to access that socket. The kernel and initramfs paths are fixed under `.runtime/isolation/`. Guest code cannot supply arguments or host filenames.

The guest boots into an in-memory appliance. The seed runs as UID/GID 1000 without supplementary groups. Starter source and bootstrap are root-owned; task files are writable. Unprivileged user namespaces are disabled, and process/file-descriptor limits apply. Even compromised guest root remains behind the VM and broker boundaries.

## Broker

The transport is bounded, newline-framed JSON, not a network server, host shell, filesystem server, or unrestricted URL proxy. Protocol 2 verifies SHA-256 for every source/input file before writing it in the guest. A host file lease serializes VM runs across app, evaluator and test processes; process exit releases the lease. After the boot/input exchange it accepts only:

- `infer`: bounded history and optional guest tool schemas using the host-selected model/provider/settings. Schemas describe guest tools to the model; they never create host capabilities. Guest URL, headers, credentials, commands and environment overrides are rejected. Provider exceptions become generic guest-facing errors to avoid reflecting secrets.
- `web`: explicit public HTTP/HTTPS request data, governed by the host's Internet access preference. This capability is separate from inference; web URLs and headers cannot redirect model-provider requests or change host policy. See Public internet access below.
- `inputs`: poll one host-admitted human message at a time. Only the authenticated browser API can enqueue or cancel messages. Direction changes are offered between actions; follow-ups wait for reported completion. Exact saved human text and its input ID acknowledge delivery. An edited guest can ignore input or lie about following it, but cannot enqueue new human messages through this operation.
- `file` / `checkpoint`: bounded bytes and validated relative names. The host rejects traversal, absolute paths, Windows device names, alternate data streams, control characters and links. Bytes are stored under host-computed SHA-256 blob filenames. Manifests bind files to one session. No guest archive is extracted on the host; uncommitted exports are discarded on termination.
- `state` / `event`: bounded history/display/journal data. Identity, task, provider, storage roots and policy remain host-owned. The host keeps Stop visible until it ends the VM, even if the guest claims completion.
- `done` / `failure`: completion signals; the host decides termination and final status.

Unknown operations and extra capability fields end the run. Parser, transport and integrity failures fail closed. Only trusted host assets are served as UI. File previews are text and downloads use attachment headers. The evaluator can materialize exported bytes for content checks but never imports or executes them.

Journal event names beginning with `host_` are reserved for the controller.
Its content-addressed inference history records the actual provider payload,
effective instructions and declared tools, source identity, context omissions,
responses and reported usage. Known configured provider keys are redacted;
task content can still be sensitive. These records are included in journal
downloads. Tool declarations and guest operation receipts are observations,
not permissions or independent evidence that the requested outcome occurred.
Each session has at most 64 MiB of inference blobs; exceeding that allowance
records incomplete evidence and lets inference continue. Existing guest-journal
and transport quotas still apply; host evidence adds bounded reference events.
Human queues hold at most 20 undelivered and 200 total entries per session,
each at most 12,000 characters. Queued work does not reset the action allowance.

Operation receipts distinguish a guest-reported start, result, committed file
checkpoint and saved result message. Resume exposes any incomplete receipt and
restores only committed files. No action is automatically replayed, even if a
tool name sounds read-only: an edited seed may change its behavior. A new run
cannot advance an old receipt using an unrelated checkpoint. As with the rest
of the broker, native mode needs external protection for these host records.

Candidate comparisons freeze both versions, model settings and trusted task definitions before execution. New tasks/recovery cannot overlap an active app comparison. Comparisons run candidate code only through the same VM broker; the host checks quarantined artifact bytes against its own definitions. Reports and source diffs are inert data. Model-authored tests, guest journals and reported step counts are not trusted acceptance criteria. A successful comparison does not auto-promote a candidate or prove a new feature. Self-improvement runs may enable guest commands without changing the host isolation boundary or saved preferences.

Before model tasks, the fixed guest bootstrap runs the host's unchanged seed tests from a root-owned directory against the selected modules. Its unprivileged child has no broker descriptor and cannot open the broker device. The protected parent collects the real process exit status and bounded test output. Candidate tests are excluded from this regression suite. Candidate modules still control their behavior and can manipulate test output, so a pass is diagnostic evidence rather than a security proof. Failure rejects the comparison before inference.

Functional Python checks also run in a fresh guest, with host-selected function names, arguments and expected values. The protected parent requires a successful child exit and one complete result frame. A matching comment or an early exit with status zero does not satisfy the check. Arbitrary submitted code still controls the guest's behavior; known cases and output can be gamed. This is functional evidence, not a proof of honesty. Candidate Python is never imported on the host.

File imports copy bounded bytes into the same quarantine and manifest system. They provide no host directory mounts or new broker operations. Session deletion moves its protected storage directory to recoverable Trash. Runtime archive hashes and installed file inventories cover privately managed Python and Ollama; external model services and OS-managed Linux QEMU remain separately trusted dependencies.

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
| Model requests | With the optional action allowance enabled: `(min(configured steps, 200) + 1) × 3`, maximum 603; ordinary use defaults off. Time, frame and transfer limits always apply. |
| Model history | 2,048 messages / 1.5 MB serialized per request; the provider context budget also applies |
| Export file / count / checkpoint | 2 MiB / 500 / 32 MiB |
| Exported bytes per run | 32 MiB |
| Session journal | 64 MiB |
| Guest state / protocol messages | 1.5 MB / 10,000 messages per run |

Stop closes the Windows job or signals the Linux supervisor to kill its whole managed process group. Controller exit/crash closes the Windows job handle or is detected by the Linux supervisor, which terminates the VM. Linux has no Windows-style percentage CPU cap; its two virtual CPUs, CPU-time limit and the broker wall deadline bound execution. An external watchdog also ends blocked or noncooperating guests during each active run. After an ordinary completed/waiting turn, the interactive app can retain that session's VM and exclusive lease while its local Ollama model is resident. Follow-ups reuse it only if source, configuration and committed input identities still match. Stop, different sessions, changes, edited-seed activation and independent checks discard it; Resume after Stop restores committed files/history in a fresh VM. The host polls residency; the seed cannot enable retention. Idle guest processes remain bounded by the VM's host quotas. Candidate trials freeze source separately and never install it over the protected starter. Starter recovery drops candidate selection while preserving saved task data.

The interactive app can prewarm one clean VM after detecting the selected local
Ollama model in memory. It holds the same exclusive VM lease and waits for a task
without any source or task files. Host-owned residency checks close it on model
unload. Graders disable prewarming and retain their independent fresh-VM policy.

Reasoning previews are host-owned display data, separate from guest history and
prompts. The UI renders them as plain text, retaining at most 200 spans and 256,000
characters total, up to 64,000 per span. Cancelled/finished previews reject late
transport updates. The raw provider trace retains its existing storage limits.

Authenticated per-page heartbeats and per-page event streams track AutoProteus tabs.
Stream access uses an expiring page nonce issued by the authenticated heartbeat;
it grants no task or model operations. The last closed tab
starts a 5-second cleanup grace period; a missed-heartbeat lease expires after
five minutes. Cleanup applies Stop semantics, closes idle VMs, and unloads only
local model names recorded by this app, without deleting weights. Browser crashes,
tab suspension and dropped close notifications make this best-effort detection.
No browser registration means headless runs are not automatically stopped.

## Limits of the guarantee

This contains model file operations, arbitrary guest commands/code, malicious upgrades, unauthorized networking attempts and malformed broker requests. It cannot promise protection from vulnerabilities in the host operating system, hypervisor, emulated devices, trusted host code, or upstream packages. QEMU's website links to the Windows build provider used here; pinned hashes identify downloads, not an independent security audit. Relevant runtime fixes require reviewed pin updates.

The inference engine/provider is trusted and configured separately. A bad seed may waste its bounded requests or produce incorrect results. User-opened downloads, manually launched code, host plugins and human edits to controller/runtime files are outside the boundary. Quarantine/journal storage is bounded per session; many user-created sessions still consume disk space. Passing a task does not make its output trusted.

No host email-account integration, user-selected host folder or arbitrary socket access exists. Other host capabilities need explicit authorization, narrow broker operations, scopes, quotas and secrets outside the guest. Public web APIs can be used with explicitly supplied credentials, but host account credentials are never extracted or forwarded automatically. A host command endpoint, unrestricted URL proxy or writable mount would change this security model.

## Public internet access

Internet access is enabled by default, including for legacy settings without
a saved preference. Users can turn it off during setup or in Settings. Saved
boolean choices are preserved; invalid non-boolean values stay off. Changes
apply to the next run. The host snapshots the permission at run start; edited seeds cannot
enable it. Stop ends a current run. The VM still has no network adapter. Its
`web_request` tool and the running worker's `autoproteus_web.request` bridge
submit HTTP request data to a dedicated protected host client. The preference
controls this bridge only; native mode retains the account's network access.

Only public HTTP on port 80 and HTTPS on port 443 are allowed. The client rejects
URL credentials, local names, loopback/private/link-local/shared/reserved and
multicast destinations, known IPv6 transition addresses, and Azure's host
infrastructure address. Every DNS answer must be public; connections use the
validated numeric address without resolving it again. HTTPS keeps the original
hostname for SNI and normal certificate verification. Host proxy environment
variables are ignored. Each redirect repeats destination and DNS validation.
HTTPS downgrades are rejected. Cross-origin redirects drop custom headers
except Accept, Accept-Language and User-Agent. Only GET/HEAD follow redirects;
write requests return the redirect response without automatically replaying.

Requests have a 20-second total deadline (including DNS), at most five redirects,
64 KiB UTF-8 bodies, 8 KiB request headers and 2 MiB response bodies. Each run has
200 requests and 32 MiB of received response-body allowance, including failed
oversize reads. Stop/deadlines close active sockets; DNS workers are daemonized
and globally bounded to four so a blocked OS resolver cannot block shutdown or
create unbounded threads. The run's existing host wall deadline still applies.
Transport and routing headers are host-owned. Results include status, response
headers and bytes; HTTP error responses are returned for inspection. The host
stores bounded request receipts without request bodies, headers or URLs. Normal
guest journals can include URLs, explicit credentials or returned task data;
treat journal exports as sensitive.

No host browser sessions, cookies, provider keys, proxy credentials or files are
attached. Requests may send workspace contents to public services, and write
methods can cause external effects. A stopped/timed-out request may already have
taken effect; recovery must inspect it before retrying. Remote content remains
untrusted input. This changes the previous offline policy: isolation protects
host resources, but does not promise privacy for data available to a seed that
has Internet access. The tool does not provide JavaScript browsing, unrestricted
package-manager networking, raw TCP/UDP or access to private services. Public
HTTP proxy/tunnel services are still public destinations; granting Internet
access is not a restriction on which public information the agent may obtain.

## References

- [QEMU security model](https://www.qemu.org/docs/master/system/security.html)
- [QEMU KVM acceleration and Linux seccomp sandbox](https://www.qemu.org/docs/master/system/qemu-manpage.html)
- [QEMU Windows Hypervisor Platform prerequisites](https://www.qemu.org/docs/master/system/whpx.html)
- [Microsoft hypervisor capability probe](https://learn.microsoft.com/en-us/virtualization/api/hypervisor-platform/funcs/whvgetcapability)
- [Windows job resource controls](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-setinformationjobobject)

### Observation and save failures

The optional practical model check uses synthetic inputs in fresh VMs through
the saved production connection. It runs only when explicitly requested, shares
finite action/time/token budgets across follow-ups, and cannot run alongside
normal tasks or seed evaluations. It saves source/profile-bound receipts in the
controller data directory. Provider keys remain host-owned; hosted providers
still receive the diagnostic task data. Stop or closing the last browser tab
cancels the check. Passing ordinary tasks does not approve a seed upgrade.

Discovery's public submission preflight parses JSON and Python source as data.
It grants no permission and cannot replace protected independent checking.

Observers use the owning controller API and its storage lock. They do not open
a second recovering Store, schedule work, acknowledge input or replay actions.
The Evidence view renders bounded text; original evidence blobs are checked
against their SHA-256 identity before display. External monitors should use the
API or closed trace exports rather than reading mutable live snapshot files.

The session snapshot is authoritative; summary files are rebuildable indexes.
A failed snapshot replacement restores the last readable committed state. A
failure after replacement does not roll back the committed snapshot. Summary
failures retain the new snapshot, while journal write/sync failures have an
explicit uncertain outcome. These distinctions describe process recovery; they
do not promise multi-file transactional durability under sudden power loss.
