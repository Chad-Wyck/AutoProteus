# AutoProteus Seed

A small autonomous agent with a local browser interface. The seed connects a model to workspace tools, displays an optional checklist, and records complete interactions. Models can inspect and change a copy of the harness without overwriting the running seed.

## Start

On **64-bit Windows**, double-click **Start AutoProteus.cmd**. The launcher opens the app in your browser and reuses an existing instance. If Python 3.10 or newer is unavailable, it downloads a portable Python runtime into `.runtime/`. No administrator access or pip packages are needed.

In the app, choose:

- **Local model** (default): choose an installed Ollama model, or let AutoProteus download the official portable engine and a model. Initial downloads require an internet connection, several GB of free space, and time. Subsequent runs reuse the downloads. Model speed depends on your hardware.
- **Hosted connection**: supply a compatible chat-completions service address, model ID, and optional key. The app tests a short model response when you connect. Requests go to that provider and may incur its usual charges.
- **Interactive demo**: a scripted tour creates a welcome file, reads it back, and completes a checklist. It exercises real tools and persistence but does not use an AI model.

Describe a task, inspect actions and generated files, and reply when the model needs more information. **Stop** saves the session. **Resume** tells the model to inspect current state before continuing. Use **Settings → Quit AutoProteus** to close the background app. Closing the browser alone leaves it running.

The local UI can also be started with `python app.py`. Use `python app.py --no-browser` for a console-managed instance. Windows is the supported one-click experience; on other systems, use an existing Python and Ollama installation.

## Models and execution

The adapters support Ollama and services implementing a compatible `/chat/completions` API. Hosted service addresses should normally end in `/v1`. Hosted keys are encrypted using Windows DPAPI; on other platforms, keys entered in the UI last only until the app exits. `AUTOPROTEUS_API_KEY` is also supported. Keys are not included in journals or source snapshots.

Adapters normalize native tool calls into the same small internal action protocol. Hosted setup also offers a strict JSON text fallback for models without native tools. There are no heuristic Markdown command extractors. A response must be complete and parse successfully before any action can execute. Models that do not reliably produce actions may require configuration changes or a different adapter; compatibility is not a guarantee of task competence. Local models use their default thinking behavior unless you change it in Settings.

Native replies must use `finish` to report completion or request input. Prose-only replies enter the bounded format repair loop. Checklists are optional: the model writes `todo.txt` using `write_file` when requested or helpful, and the UI displays it.

`read_file` returns bounded UTF-8 text with `next_offset` and `eof`. Offsets are **byte positions**; the optional `length` is **characters** (default 1,000, maximum 12,000). Continue using `next_offset`, rather than calculating line numbers or guessing positions. If a read is shortened to fit model context, its continuation position still matches the visible content. Full results stay in the journal.

For small changes, `edit_file` replaces one exact `old_text` with `new_text`. Missing, empty, or ambiguous matches are rejected without changing the file; include surrounding text to select one occurrence. Surrounding bytes and line endings are preserved. `write_file` writes the supplied content as UTF-8 without changing line endings. Writes and edits are limited to 100,000 characters and use the same workspace checks.

The starter is [Qwen3 4B Instruct](https://ollama.com/library/qwen3:4b-instruct). The lighter 1.7B option uses less memory but can be less reliable. Tool batches run in order; after a failed action, remaining dependent calls are skipped so the model can replan. Completion requested alongside tools is deferred until the model receives their results.

File tools are constrained to the session workspace. **Terminal access is off initially.** Enable it in Settings when a task needs commands. Commands run as your account using PowerShell on Windows or `sh` elsewhere. This is **not an OS sandbox**; shell commands can access paths and resources beyond the workspace. Docker is not required.

“Finished” means the model reported completion. Review artifacts or use independent checks to verify task success. Response/context limits are configurable; history budgeting is a conservative character estimate, not a model tokenizer. Original instructions and current todo state stay in the prompt, while full request/response events remain in the journal.

## Where things live

| Path | Purpose |
| --- | --- |
| `app.py` | Entry point and single-instance discovery |
| `autoproteus/agent.py` | Seed prompt, action validation, execution loop |
| `autoproteus/providers.py` | Model adapters and scripted demo |
| `autoproteus/tools.py` | File tools and optional terminal |
| `autoproteus/storage.py` | Atomic snapshots and append-only journal |
| `autoproteus/runtime.py` | Optional portable Ollama setup |
| `autoproteus/server.py` | Loopback UI and API |
| `web/` | Interface; no frontend build step or CDN |
| `.data/settings.json` | Preferences |
| `.data/sessions/<id>/` | `session.json`, `events.jsonl`, and task workspace |
| `.data/models/` | Model cache for the managed engine |
| `.runtime/` | Optional portable Python and Ollama |
| `old/` | Earlier experiments, left untouched |

The local server listens only on loopback. API requests require a per-launch token, and requests from unrelated website origins are rejected. All UI assets are local.

Each task workspace contains `harness/`, a source snapshot with a recorded version and SHA-256. If asked to improve its own harness, the model edits that snapshot. Activating a modified harness is intentionally a separate development step: inspect it, run checks, then launch the copy from its own directory. Automatic promotion, model training, and state-dependent sampling are not part of this seed.

**Save trace** exports the session snapshot and complete event journal as a ZIP. It may contain private task text, file contents, and model responses; share it intentionally. Generated files can be downloaded individually or opened in the workspace folder.

## Verify

Run `python -m unittest discover -s tests -v`. Tests cover action validation, workspace boundaries, cancellation, recovery, provider responses, journaling, and the local API. `python evaluate.py` runs the deterministic demo against filesystem checks; it is a plumbing check, not a model benchmark. `python evaluate.py --live` evaluates the configured real model on the tasks in `evaluations/tasks.json` with independent file checks, writing a report to `.data/evaluations/`. Hosted live evaluation sends requests to the selected provider.

The current seed has no claim of improved model performance. Compare models and future harness changes on repeatable tasks before promoting them.

Use `python evaluate.py --live --model MODEL_NAME` to compare another installed model on the same service without changing your saved connection. `--task exact-file` selects a single evaluation.

Use `python evaluate.py --live --self-improve --timeout 3600` for the separate harness feature task. The model chooses and implements a small feature in its source copy, adds a test, and explains its use. The criteria in `evaluations/harness-feature.json` require independent functional checks and the trusted seed regression suite against the copy. The evaluator checks artifacts and changed runtime/test files without executing model-authored code. A ready submission reports `REVIEW`, `passed: null`, and exit code 2 until those independent checks are recorded; unsuccessful submissions exit 1. No changes activate automatically.

The self-improvement evaluation always disables terminal access for that run, even if it is enabled in Settings. Your saved preference stays unchanged. This evaluation restriction does not provide an OS sandbox for other runs or for separately launched modified code.

## Runtime references

Local setup uses the [official Ollama standalone Windows distribution](https://docs.ollama.com/windows), its [chat API](https://docs.ollama.com/api/chat), and [model pull API](https://docs.ollama.com/api/pull). The optional Python bootstrap uses the [official Python 3.13.12 embeddable distribution](https://www.python.org/downloads/release/python-31312/).
