# Test the current seed with your own local model

Use **`evaluations/model_study.py`**. This is the published runner used for the
v0.14.0 first/second-extension pilot. It tests the checked-out starter; no old
seed, experimental treatment or human-written parent is needed.

For the next fixed-case repeatability and outcome-choice studies, use
[the portable study guide](next-studies.md). Prepare fresh plans on the test
machine; a frozen plan is tied to its source, runner and execution environment.

Newly prepared plans use **`activation-use-v2`**, adding first activation/use.
If a friend is already running commit `d8e7175`, keep that checkout frozen until
it finishes. Its older protocol did not separately measure first autonomous use;
retain those results under their original revision and protocol.

## What it tests

With `--mode full --repeats 1`, each model receives:

1. A short and longer-prompt inference/protocol check.
2. Five ordinary tasks: exact file, precise edit, recovery, Unicode and code fix.
3. Three fresh first extensions: hashing, CSV preview and JSON formatting.
4. First activation and model-led use on fresh inputs withheld during development,
   requiring the actual new tool result, correct saved files, unchanged seed and
   explicit completion. Independent grader calls do not count as model use.
5. A second extension from each verified submitted first parent. The grown seed
   must preserve its earlier capability, pass independent checks, activate, and
   use both capabilities to finish an audit with correct files.

Every first attempt starts from a fresh starter. Invalid implementation packages
do not receive second attempts. If a verified first package fails first use, the
second task is explicitly a diagnostic from the frozen checked parent; it earns
no complete-chain credit even if it succeeds. First-use mutations are not promoted.
The full-mode basic gate requires at least four of five passes,
after the inference check passes. If that gate fails, upgrades remain untested;
they do not count as failed implementations.

The commands below allow **128 actions, 60 minutes and 65,536 generated tokens**
per extension trial, shared across development, checking and final use. Ordinary
tasks have a separate 240-second/8,192-token allowance. These are ceilings, not
duration estimates. One repeat is exploratory; three repeats schedule nine first
extensions and up to nine second extensions per model.

Activation uses the **remaining** action allowance. The second task receives a
fresh task allowance. Earlier baseline protocol runs could refresh actions at
activation; their original counts remain historical evidence, not v2 results.

## Machine setup

1. Download or clone the current repository. Record `git rev-parse HEAD` if
   using Git. Do not edit or update the checkout during a frozen study.
2. Launch AutoProteus normally and prepare the isolated environment. Windows
   requires WHPX; x86-64 Linux requires KVM. This VM suite currently does not
   support macOS. Launchers install the project-local runtime dependencies.
3. Make the model available through an Ollama or OpenAI-compatible **loopback**
   endpoint on the same machine. Inference uses the host GPU; model-written
   code runs in disposable VMs. The test runner does not start the model service
   or download weights.
4. Keep inference ownership and execution contention controlled:
   Updated v0.14.1 controllers yield idle caches to waiting work without unloading
   the model. Active tasks retain their slot. Restart the controller once after
   upgrading; old running controllers/runners do not gain this behavior in memory.
   The following shutdown workaround remains useful for older versions or for
   measuring cold-start behavior:
   - For an independently managed model engine, choose **Settings → Quit
     AutoProteus**, then leave/start that engine independently.
   - For AutoProteus's managed Ollama service, close **all** AutoProteus browser
     tabs and wait at least 10 seconds. Browser cleanup releases its model and
     VM, while the background service remains available. Test requests reload
     the model. Keep the tabs closed until testing finishes.
   - Do not run another AutoProteus task or study concurrently. Shared-VM waits
     consume the test's wall allowance. Inspect CLI output/saved reports for
     progress instead of reopening the app.

## Profile

Copy `evaluations/model-test-profile.example.json` to `profiles.json` at the
repository root. Replace the placeholder with the engine's exact model ID.

| Model interface | `provider` | Example `base_url` |
| --- | --- | --- |
| AutoProteus-managed Ollama | `ollama` | `http://127.0.0.1:11435` |
| Separately installed Ollama | `ollama` | `http://127.0.0.1:11434` |
| Local OpenAI-compatible server | `hosted` | `http://127.0.0.1:8080/v1` |

Here `hosted` names the wire format: this runner accepts loopback endpoints,
not remote API addresses. A cloud GPU can be used when the runner and prepared
VM environment run on that same host. Use a local endpoint accessible to the
runner without an API key; do not put secrets in a profile or frozen plan.

The example requests native tools, 128K context, 4K responses, temperature 0.6,
thinking off and a 600-second request timeout. Match context to the model and
available memory and record any change. Keep settings fixed across repeats.
For compatible servers, set reasoning, context, top-p/top-k, KV cache and
offload in the **engine**: the hosted adapter does not forward `thinking`.
Save the engine command/settings and distinguish requested from verified values.

Record publisher/model revision, quantization, engine/version, GPU/VRAM, RAM and
OS. An optional profile `assets` object maps checkpoint/runtime file paths to
SHA-256 values for verification. Compatible-server model names alone provide a
weaker identity than pinned weights and engine files.

## Run from the repository root

Use a new output folder for each independent study.

**Windows PowerShell**, using the Python installed by the launcher:

```powershell
$testPin = Get-Content .\controller\managed-runtime-lock.json -Raw | ConvertFrom-Json
$testPython = Join-Path (Get-Location).Path ".runtime\python-$($testPin.python_windows.version)\python.exe"
& $testPython -X utf8 evaluations/model_study.py prepare --profiles profiles.json --output .data/friend-model-full --mode full --repeats 1 --timeout 3600 --output-token-budget 65536
if ($LASTEXITCODE -eq 0) {
    & $testPython -X utf8 evaluations/model_study.py run --input .data/friend-model-full --check-only
    if ($LASTEXITCODE -eq 0) { & $testPython -X utf8 evaluations/model_study.py run --input .data/friend-model-full }
}
```

**Linux shell:**

```sh
.runtime/python-linux/bin/python3 -X utf8 evaluations/model_study.py prepare --profiles profiles.json --output .data/friend-model-full --mode full --repeats 1 --timeout 3600 --output-token-budget 65536 &&
.runtime/python-linux/bin/python3 -X utf8 evaluations/model_study.py run --input .data/friend-model-full --check-only &&
.runtime/python-linux/bin/python3 -X utf8 evaluations/model_study.py run --input .data/friend-model-full
```

Preparation freezes source, tasks, settings, graders and environment without
inference. `--check-only` calibrates scripted graders in VMs without model calls.
Only the last command starts live-model work. Stop if preparation or calibration
fails; preserve the diagnostics and resolve setup before preparing a fresh plan.

For repeatability, prepare a **different** folder with `--repeats 3`. A profile
list can contain several models with unique IDs. Use separate plans to compare
sampling/context settings, rather than editing an existing frozen plan.

## Resume and share results

Rerun the same `run --input ...` command after an interruption. Completed cells
are retained. A launched unfinished attempt becomes interrupted and is not
silently retried. `--retry CELL_ID` creates an explicit additional attempt while
preserving the old one; agree before using it and report both. Changed source,
graders, assets or environment require a fresh plan.

Send back the study folder, especially `plan.json`, `plan.sha256`, `summary.json`,
`queue.json`, `queue-summary.json`, model identities, calibration receipts and
`trials/`. Trials contain candidate sources, independent reviews, provider traces
and results. Include the hardware and engine settings noted above. Archive this
study folder, not all of `.data/` or the model weights.

The summary separates `first_verified`, `first_accepted`, `second_verified` and
`complete_growth`, plus `first_use_attempts`, `first_use_passed`,
`second_use_passed` and `diagnostic_second_attempts`. In v2, `first_accepted`
means an independently verified, submitted package; a development `needs_input`
request for activation is valid. Use `first_use_passed` to assess completion of
the first user task. `complete_growth` requires both first and second use.
The legacy development review is retained separately rather than rescored.
Working code, correct outputs, explicit finish and complete
verified growth are different outcomes. Preserve failures and missing usage
measurements. Do not coach the model, repair its code or weaken checks to get a
pass. These familiar directed tools do not establish broad capability discovery.

Generate a compact report from a finished study without recovering sessions:

```text
python evaluations/study_report.py --input .data/friend-model-full --output .data/friend-model-report
```

Use the same bundled Python executable as above. This writes Markdown and JSON
with separate implementation, candidate-test, scope, provider/format and final-use
observations. Legacy first use and full chains are labelled unmeasured. Partial
cost sums retain completeness flags. The reporter refuses actively running queues
and does not execute candidate code or change historical scores.

If another coding agent is helping, give it this guide and ask it to configure
the local endpoint, freeze one profile, calibrate, run the full study and return
the source revision and all recorded outcomes. See [runner details](model-study.md).
