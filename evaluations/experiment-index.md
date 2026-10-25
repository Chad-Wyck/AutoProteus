# Experiment index

`experiment-index.jsonl` is a compact, append-only record of recent studies and
their evidence. It includes source-hashed historical findings as well as the recent guidance
and activation records. Historical entries are explicitly marked not regraded.
Later entries record outcomes without rewriting the original trial definition.

Each record identifies the hypothesis, frozen seed versions, grader/plan
fingerprints, model, resource allowance, status and evidence. Completed-chain
entries include known cost measurements and their completeness flags. Missing
measurements mean unknown, not zero. Discovery outcomes remain provisional;
retaining a research candidate does not promote it into the default seed.

| Study | Evidence | Interpretation |
| --- | --- | --- |
| Current versus shortened guidance | [Findings](seed-v0.8.2-guidance-2026-10-24-findings.md) | Current guidance performed better in this small study; original and supplementary scores remain separate. |
| Original activation comparison | `.data/activation-chain-v082-20261024/user-stop.json` | User interrupted after nine actions; no completed chain or comparative result. |
| Fresh activation comparison | `.data/activation-chain-v082-restart-20261024/plan.json` | Three paired chains per arm; complete cumulative workflows are primary. See JSONL status entries for progress/outcomes. |

Search the retained evidence without model calls:

```text
.runtime/python/python.exe -X utf8 evaluations/evidence_index.py search "Qwen default"
.runtime/python/python.exe -X utf8 evaluations/evidence_index.py backfill
```

Backfill appends a new identity when a report changes and leaves every earlier
record intact. Report summaries are discovery aids; read the linked original
conditions and verdicts before comparing results. It never pools success rates.
