# Paired cumulative growth through the normal app connection

This opt-in study keeps the default seed unchanged. It loads the exact frozen
SHA-256 seed accepted in the earlier screening, verifies that first capability,
and asks for JSON formatting followed by an inventory audit using both tools.
All candidate execution and independent checks run in disposable VMs.

Before preparation, `profile-check.py` must have completed at least one accepted
upgrade through production ModelClient and managed Ollama. Its recorded model,
runtime and settings are reused; the standard adapter is not replaced and
tool-call IDs are not rewritten. A single transfer check is not qualification
of the default app profile or proof of repeatability.

```text
.runtime/python/python.exe -X utf8 evaluations/profile-check.py --output .data/profile-check --gguf PATH_TO_RECEIPT_VERIFIED_GGUF
.runtime/python/python.exe -X utf8 evaluations/growth-study.py prepare --profile .data/profile-check/results.json --source PATH_TO_ACCEPTED_SHA_CANDIDATE_JSON --output .data/growth-study
.runtime/python/python.exe -X utf8 evaluations/growth-study.py run --input .data/growth-study
```

Preparation starts no inference and creates `Start tests.cmd`. Defaults are
three repeats, six balanced baseline/procedure attempts, 30 minutes per attempt,
and 65,536 generated tokens. The token budget is shared across development and
activation; the final phase receives only the remaining wall time. The normal
command/request timeouts, action/request quotas and worker watchdog remain.

Both arms receive the same independent development invoker. Only the treatment
also receives the optional procedure: invoke the edited tool, inspect the file,
compare a simple exact expected example, then expand tests and repair failures.
The helper runs independently of failing tests; it does not bypass acceptance.
Source, task, profile, helper and procedure costs are retained in the evidence.

Verification of the second capability, preservation of the first, stage order,
final artifacts, actual use of both tools and direct/native invocation are
separate fields. Only independently verified candidates are activated in a VM.
An interrupted launch remains recorded and is not silently retried. There are
no operator candidate repairs or automatic promotions.

`regrade-screening.py` reassesses saved accepted candidates against the corrected
graders without inference. It writes new records and preserves original verdicts.
Run regrading and live studies serially: they share a single VM lease. Waiting
for another trial can otherwise exhaust a short verifier deadline; such an
infrastructure result must not be presented as a candidate behavior failure.
