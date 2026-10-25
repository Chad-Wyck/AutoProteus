# Model compatibility versus useful seed editing

The first-install profile remains Qwen3 4B Instruct, 32K context, 8K responses,
temperature 0.2 and model-selected thinking. Terminal permission starts disabled.
The setup diagnostic checks tool-message transport and result retrieval; it does
not qualify autonomous upgrades. No reproducibly supported self-extension profile
has been established. Keep model/setup claims explicit rather than promoting a
three-run exploratory result.

Our main research control uses Qwen3.5 9B Q6_K, 128K context, 4K responses,
temperature 0.6, thinking off and guest terminal access. It has verified directed
extensions and occasional complete workflows, with inconsistent repeatability.
These settings differ materially from a fresh installation and from Ollama tags
that may resolve to other weight precision or templates.

`profile-check.py --defaults --output .data/default-profile-check` measures the
actual fresh profile on ordinary tasks without silently enabling terminal access.
It uses an already prepared managed Ollama service and downloads nothing. Missing
cached weights or runtime support are setup failures, not model capability
failures. Terminal-dependent development is explicitly not run with that permission
disabled. `--gguf` cannot be combined with `--defaults`.

For an explicitly enabled upgrade profile use `--model NAME --repeats 3` and,
optionally, an already downloaded receipt-verified `--gguf PATH`. Preserve exact
weight/engine hashes, template, context, sampling, cache configuration, hardware
and seed source. Report connection, ordinary tasks, verified extensions, final
artifacts and complete workflows separately. Trial grading shares the task deadline.
Repeated first extensions alone do not qualify cumulative growth.

Before recommending a default upgrade configuration, require repeated completed
workflows on unfamiliar tasks through the ordinary app adapter, followed by a
second model. Do not overwrite user preferences or claim larger contexts guarantee
success. Selection of a future setup profile remains a product decision based on
those receipts, not an automatic benchmark promotion.
