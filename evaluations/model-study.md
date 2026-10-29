# Model comparisons

New plans use `activation-use-v2`: first implementation/checking, activation and
model-led use on fresh inputs, then a separate second-extension task and use of
both capabilities. See [the protocol and measurement guide](activation-use-study.md).
Keep existing studies frozen at their original checkout; do not update a friend's
running `d8e7175` study or rewrite its historical scores.

Sampling mode is frozen separately from task/source identity. See the
[focused sampling comparison](next-studies.md#focused-sampling-comparison-prepared-for-later)
for `--sampling-seed-mode per-request` versus `server-initialized`. The latter
omits request seeds; external server initialization and per-attempt restarts
remain the runtime owner's responsibility, unverified by this runner.
Closed-study reports now separate checked artifacts, explicit completion, tool
reuse and skipped stages; historical verdicts and qualification gates are unchanged.

### Optional owned inference service

Profiles without `runtime` keep connecting to an externally managed service.
An optional `runtime` manifest makes the runner start a **fresh owned service
per attempted cell**, then stop it and its descendants. Completed cells are not
relaunched on Resume. An occupied dedicated port is an infrastructure error;
the runner never takes over or stops the existing service.

See [the owned-runtime profile example](owned-runtime-profile.example.json).
Replace paths and hashes, pin all model/runtime dependencies, and select flags,
offload and cache settings appropriate to that exact engine and hardware. The
example is not a memory-fit or runtime-compatibility qualification. Commands are
argument lists, not shell strings; only `{seed}`, `{port}` and `{context_tokens}`
are substituted. Windows processes start suspended and enter an owned job before
running; Linux uses the existing parent-watched process supervisor. No guest or
model-written command is used for host startup. Do not put credentials in commands.

Assets are hashed once per study invocation; size/timestamp changes are checked
during each attempt. Startup, commands, pinned assets, optional reported seed/
context, memory samples and cleanup receipts are saved under each attempt's
`runtime/`. A configured reported setting must match; an omitted check is
unverified. A reported seed match does not establish RNG determinism or that an
API honors per-request seeds. Startup is outside the task allowance and has its
own deadline. The lifetime guard includes startup, the declared task ceiling and
30 seconds for orchestration; cleanup time can extend beyond that ceiling.

The helper watches available physical RAM and, on Windows, available commit.
Linux commit headroom is unmeasured. Tune the starting threshold for the model
and leave space for AP's guest. Default thresholds do not prove a model fits.
Memory/asset/lifetime failures terminate only owned inference and leave an
infrastructure error rather than an accepted capability result. Profiles remain
host-owned; seed edits cannot configure this launcher or grant host access.

The hard floor remains 2 GiB by default. An additional responsiveness guard
requires available physical RAM below `pressure_floor_bytes` (default 4 GiB)
plus sustained paging or stalls for `pressure_seconds` (default 15 seconds).
On Windows, paging means at least 32 MiB/s of memory page-ins; on Linux it
means at least 20% full memory PSI. After readiness, repeated health-check
failures under low RAM also count. High file-read traffic with sufficient RAM
does not trigger this guard. Missing paging telemetry is recorded as unavailable;
the hard floors and health checks remain active. These are host pressure signals,
not proof the model caused the pressure, and do not guarantee a responsive desktop.
Only the owned service is terminated; caches, other apps and Windows settings
are left alone. Cleanup receipts include a structured failure category.

Closed reports show evaluated score denominators separately from all launches,
resource stops, other infrastructure errors and interruptions. Exact legacy
guard receipts take precedence over their downstream connection errors.

### Activation-only handoff replay

`activation_replay.py prepare --profiles PROFILE.json --output .data/REPLAY
--parent .data/ACCEPTED-HASH-ATTEMPT --parent .data/ACCEPTED-CSV-ATTEMPT`
freezes accepted candidate bytes, original human tasks, first-use contracts and
three matched sampling seeds. Then run `activation_replay.py run --input
.data/REPLAY`. Keep each command on one line. The supplied profile controls the
equal action allowance; defaults are 20 minutes and 16,384 generated tokens per
activation-use trial. Every arm gets a fresh owned service and disposable VM.

The control uses normal concise activation. The treatment adds only a verbatim
copy of the already-supplied first-use instruction to host activation state.
This is a fresh activation-only reconstruction, not restoration of the original
development checkpoint. Development transcripts, model-written todos and prior
failed-use outputs are absent in both arms. Candidate source remains identical;
no expected outputs, hidden checks or post-failure corrections reach the model.
Independent VM checks recalibrate each accepted candidate before inference.
The durable queue preserves attempts and does not retry errors automatically;
a STOP file prevents starting further cells. Stop an active run through its
own runner/process owner, not by terminating unrelated services.

Report artifact correctness, actual capability/default use, inspection, source
preservation and explicit completion separately. This experiment cannot establish
new extension ability, complete growth chains or generalization to unseen tasks.

For a full starter-extension/growth study, add `--activation-reminder` to
`model_study.py prepare --mode full`. The frozen plan records this research-only
choice. After independent activation, the host copies the existing first-use
instruction, or the second task's existing final-use clause, into activation
state. It adds no expected outputs, feedback from hidden checks or new human
instructions. Original development prompts and per-stage shared budgets are
unchanged. Each result records the copied clause and whether it appeared in a
captured provider request. The normal application and editable seed are unchanged.

### Experimental public final-output feedback

Prepare a **new**, separate full study with `--public-verifier-feedback` to
measure automatic correction after activation. It is off by default and does
not change app settings or hidden graders. It can accompany
`--activation-reminder`, but cannot be combined with another `--experiment` or
a supplied parent. Use matching profiles/cases and resource limits for a
separate control study; do not reuse the earlier frozen plans after source edits.

Before inference, each task discloses its complete public verifier specification
in `task.json` and the model-facing request. It checks the named final files:
preservation or canonical JSON formatting, receipt fields, byte counts/hashes,
and the requested default CSV preview. Expected values come from the original
public input and stated contract, never candidate output or hidden test results.
Fresh input bytes remain withheld until their normal activation stage.

After a completed finish with incorrect saved outputs, at most **one** automatic
feedback message permits correction using the active tools. Waiting for a real
user answer, exhaustion, timeout and already-correct outputs do not trigger a
correction. The same remaining action, generated-token and wall-time allowances
cover that continuation. Source changes still fail source-preservation checks.
Neither model-produced verifier code nor candidate code executes on the host.

`public-verifier-feedback.json` preserves initial and final public results,
output hashes, the initial run and exact automatic feedback. Closed reports label
the treatment and separate public passes before feedback, corrections and public
passes after feedback. Independent feature, retention, actual-use, inspection and
completion requirements remain separate; a public pass cannot create upgrade or
complete-chain credit. Overall use/chain scores in this treatment include any
correction and must not be described as unassisted success. The public initial
score is an artifact/completion observation, not hidden qualification of the
initial attempt. Rejected packages never reach final-use feedback.
Second-use evidence starts at an explicit activation event boundary and includes
any automatic correction continuation. A valid earlier call is not forgotten
when correction starts another run; pre-activation development never counts.
Mismatch feedback can identify a bounded first difference using a zero-based
JSON pointer and a differing character/type/length. It does not return entire
expected rows. These diagnostics use the same public requirements and original
inputs; the public pass predicate and hidden qualification do not change.

The tool-use evidence reader accepts labelled multiline JSON from an observed
literal `Workspace.execute` result serialized by an imported `json.dumps` (or
import alias). It does not execute that program on the host. Failed commands,
wrong input paths, unrelated printed objects, shadowed encoders and incomplete
outputs remain insufficient evidence. This is bounded observation of ordinary
routes, not a security proof against deliberately forged guest evidence.

Optional paired [workflow experiments](workflow-experiments.md) add edit feedback,
advisory syntax diagnostics, observation masking, focused phases, optional
withheld final inputs, public submission feedback, precise source context and
one evidence-backed lesson. See the [v0.3.0 preparation](seed-v0.3.0-preparation.md).
They require explicit selection and leave the default seed behavior unchanged.

The app's connection qualification permits the same two response-format repairs
per decision as ordinary agent use, within one fixed deadline. Receipts report
actual request count, repair count and first-pass success. A valid wrong action
still fails; connection errors are not format repairs. Qualification does not
establish seed-editing ability.

`model_plan.py` owns preparation, fingerprints and scripted input calibration;
`model_study.py` owns trial execution, deadlines, queues and reporting. Frozen
plans include both modules in their trusted inventory. Prepare new plans after
this refactor; old results and cache receipts remain historical evidence.

This opt-in host runner leaves the editable seed, app preferences, isolation and
acceptance rules alone. Start a local inference service using a verified engine
and checkpoint, then prepare one frozen queue. No downloads or inference happen
during preparation. All candidate execution and grading use disposable VMs.

The v0.5.0 seed can isolate repairs with `seed.py check --test tests/test_NAME.py`.
These records are labelled focused checks, and do not replace the full suite or
independent acceptance checks. A focused pass cannot clear a recorded full-suite
failure. Prepare a new frozen plan for this revision; retain earlier verdicts
under their original source identities.

Supply a JSON list of profiles. Each profile has a unique lowercase `id`, a
`config` dictionary using the normal provider settings, and optionally an `assets`
dictionary mapping model/runtime file paths to expected SHA-256 values. Use
`provider: "ollama"` for its API, or `provider: "hosted"` for an OpenAI-compatible
local endpoint such as `http://127.0.0.1:8080/v1`. The latter name describes the
wire format; the runner accepts loopback endpoints by default. Configure sampling
parameters not exposed by the production adapter on the inference server and
retain its command/configuration as evidence. Never enable a separate server-side
agent/tool execution loop.

### Explicit paid OpenAI studies

The protected provider adapter uses Responses for the official OpenAI endpoint
in `api_format: "auto"`, or explicitly with `api_format: "responses"`. Other
hosted services keep Chat Completions unless Responses is explicitly selected.
Set `reasoning_effort: "low"` for GPT-6.1 Sol. No temperature or inference seed
is sent on Responses; `--sampling-seed-mode provider-default` records that the
fixed case schedule is not a reproducible model RNG seed. Optional tool
arguments stay optional (`strict: false`); no built-in hosted execution tools
are enabled. Incomplete or unknown execution outputs never release an action.

For paid studies the profile must explicitly name `provider: "hosted"`,
`base_url: "https://api.openai.com/v1"`, `api_format: "responses"` and
`model: "gpt-6.1-sol"`. Both preparation and execution require `--allow-hosted`.
The runner's current price guard supports this model at up to 128K context.
Tasks, source and tool results go to OpenAI; commands still run only in the VM.

Save the key using Windows protection, never in a profile or CLI argument:

```powershell
.\.runtime\python\python.exe -c "import getpass; from pathlib import Path; from controller.config import protect; Path('.data/openai-api-key.bin').write_bytes(protect(getpass.getpass('OpenAI API key: ').encode()))"
```

Prepare the existing full protocol with `--allow-hosted
--sampling-seed-mode provider-default`; run with:

```powershell
.\.runtime\python\python.exe evaluations/model_study.py run --input .data/openai-study --allow-hosted --api-key-file .data/openai-api-key.bin --max-api-cost-usd 25
```

This does not change normal app preferences or copy the key into the guest.
Requests use `store: false`. Matching in-memory host histories can replay opaque
reasoning items and their original call IDs; changed/trimmed histories and new
clients use the neutral journal without stale provider state. Resume therefore
does not promise preservation of opaque reasoning. Traces record requests,
responses, reported usage and returned model IDs without authorization headers.
`api-spend.json` conservatively counts all input at $2.50/M and output at $10/M,
including reasoning once. It reserves the full configured request envelope and
charges unmeasured sent calls that amount. This is a study guard and upper
estimate, not an OpenAI billing receipt or a guarantee against price changes.

References: [Responses reasoning](https://developers.openai.com/api/docs/guides/reasoning),
[function calling](https://developers.openai.com/api/docs/guides/function-calling),
[Sol model settings and pricing](https://developers.openai.com/api/docs/models/gpt-6.1-sol).

Example profile (replace the model with an already installed checkpoint):

```json
[
  {
    "id": "local-9b",
    "config": {
      "provider": "ollama",
      "base_url": "http://127.0.0.1:11435",
      "model": "your-local-model",
      "protocol": "native",
      "context_tokens": 65536,
      "response_tokens": 4096,
      "temperature": 0.6,
      "thinking": false,
      "max_steps": 128,
      "request_timeout": 300
    }
  }
]
```

Run with Python from the project directory. The current Windows launcher installs
`.runtime/python-<pinned-version>/python.exe`; Linux installs
`.runtime/python-linux/bin/python3`. See [the model-testing handoff](local-model-test-handoff.md)
for commands resolving the pinned Windows path and a profile template.

```text
python evaluations/model_study.py prepare --profiles profiles.json --output .data/model-study --mode full --repeats 1
python evaluations/model_study.py run --input .data/model-study
```

Modes:

| Mode | Work | Meaning |
| --- | --- | --- |
| `benchmark` | Short and longer-prompt inference requests with bounded output | Compare runtime configurations cheaply; no tool executes and no VM is needed. Not a capability qualification. |
| `basic` | Benchmark, protected starter checks and all five basic tasks for each repeat | Measure artifact correctness and explicit completion without any extension request. |
| `screen` | Benchmark, three basic tasks, hashing and JSON-formatting extensions, then growth from accepted parents | Select promising profiles. CSV remains untested. One repeat by default. |
| `full` | Benchmark, five basic tasks, all three extensions, then growth from every accepted parent | Full exploratory qualification. Three repeats by default; explicitly select one for a bounded pilot. |

`--first-only` omits second extensions for a focused first-package/use comparison;
complete growth is unmeasured in that mode. `--experiment source-outline` adds
one opt-in navigation tool to a copied seed, with exact character ranges. Neither
option changes the default seed.

The basic gate is at least four of five passes in full mode, or two of three in
screen mode. The inference gate checks protocol behaviour, not a minimum speed:
a slow but compatible CPU model is not rejected for low throughput. Basic tasks
allow 240 seconds / 8,192 generated tokens. Upgrade tasks retain 30 minutes /
65,536 generated tokens by default, with the profile's action/response settings.
Second-pass development and activation share one allowance. Grading time is
reported separately, and is subtracted from the remaining second-pass wall time.
The three feature tasks rotate order across repeats. Models stay grouped to
avoid unnecessary reloads. Larger balanced repetitions are a separate explicit
full run; screening decisions and untested tasks must remain visible.

Rerun the same `run` command after an interruption. Completed cells are reused
from their saved results. Launched unfinished cells are recorded as interrupted
and are never automatically retried. For an explicit additional attempt use
`--retry CELL_ID`. This adds an attempt directory and preserves the old attempt;
it does not replace a completed failure or select the best response. A new
independent repeat requires a fresh plan. An unlaunched dependent cell can start
after its interrupted prerequisite is explicitly retried successfully.

Frozen plans include source snapshots, prompts, fixtures, tools, runner hashes
and the VM inventory. Root and reported model identities are checked before and
after each executed cell, including the final cell. A change during an attempt
leaves an error record and cannot earn completed-study credit. Changing these
inputs or the environment requires a new plan.
Model assets are fully verified at preparation and each launch. Ollama identity
includes its digest/version when available; compatible endpoints often expose
only a model name. Without independent asset/server receipts, their live identity
is weaker and no automatic immutable-runtime claim is made.

Calibration results are reused only with matching seed, trusted files and
environment after actual appliance integrity verification. Candidate check reuse
is limited to identical successful scripted checks within one attempt; fresh
model repetitions receive fresh independent executions. Every cache hit retains
its original provenance and is not a new test execution. Failures/exceptions are
not cached as successful checks. Guest state is never shared between attempts.

Reports distinguish attempted, interrupted, untested, verified and fully accepted
upgrades. All launched attempts, including explicit retries, remain in the queue.
Provider token/timing coverage remains explicit: partial sums cannot be treated
as complete costs. Server-reported loading, prompt-processing and generation
times are extracted when available. VM, guest-tool and orchestration overhead is
a combined residual, not a measured VM boot time. Nonstreaming APIs do not expose
true time to first token. Cache reuse is reported only when explicitly measured
by the provider, never inferred from prompt token totals. Benchmark calls are
labelled by prompt length; cold/warm cache state is not controlled by this runner.

The endpoint's owner controls service lifecycle. The runner does not stop a
running app's model server. Keep one GPU model active on memory-constrained
hardware; lightweight report preparation can proceed while inference runs.
