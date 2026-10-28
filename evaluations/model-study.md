# Faster local model comparisons

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
wire format; this runner accepts loopback endpoints only. Configure sampling
parameters not exposed by the production adapter on the inference server and
retain its command/configuration as evidence. Never enable a separate server-side
agent/tool execution loop.

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
