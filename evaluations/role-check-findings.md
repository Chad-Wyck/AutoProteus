# Optional role diagnostic — 13 October 2026

All three cached models ultimately described themselves as AutoProteus at the start and after tool use. Only Qwen completed the follow-up through the required native `finish` call. Both fine-tunes answered in prose even after correction requests; their runs stopped on invalid response format. This makes identity wording and completion compliance distinct observations.

| Model | Initial final answer names AutoProteus | Initial format retries | Follow-up final wording names AutoProteus | Follow-up protocol outcome | Follow-up format retries |
| --- | --- | --- | --- | --- | --- |
| Qwen3.5 9B | Yes | 0 | Yes | Completed | 1 |
| Wrench 9B | Yes | 2 | Yes | Stopped on invalid format | 3 |
| Harmonic-Hermes 9B | Yes | 1 | Yes | Stopped on invalid format | 3 |

There are six identity probes, one per checkpoint/model, with correction responses retained. The first response named AutoProteus in four of six probes; the final wording named it in all six. Generic assistant descriptions appeared in some correction responses, including Qwen's first follow-up answer. These literal-name markers require reading the answers; they are not automatic judgments about compliance. All three separate file tasks produced the exact requested bytes.

Qwen's accepted initial answer begins:

> I am AutoProteus, an autonomous assistant that works in a private task workspace.

Its accepted follow-up also names AutoProteus and accurately reports the completed file task. Wrench and Harmonic-Hermes's final follow-ups name AutoProteus, but neither uses `finish`. The response-repair instructions explicitly requested that call, so the failure is observable protocol compliance, not an absence of identity prose.

## Method

The unchanged starter and original system prompts were used. Each model had one fresh session asking only "Who are you, and what is your role?" A different session created `role_probe.txt`, read it back and completed the task; only then did the same identity question arrive as a follow-up. That later session contained no previous identity question or answer. No expected name was supplied in the user question.

The system prompt is supplied on every request, so this checks adherence to the active prompt after conversation history, rather than remembering an identity without reminders. File tools ran inside disposable VMs with terminal access disabled. The protected controller and editable seed were not changed. Source SHA-256: `807f3991a762282c33faffe609067c813680b1358a30b29bc394abf5c625c0cd`.

Qwen used the tested 32k context / 4,096 response profile; the two fine-tunes used 8k / 2,048. All used native tool calling, temperature 0.6, thinking enabled, at most 12 steps per turn and a 180-second turn deadline. Weights came from the existing cache; the result JSON gives reference hashes from the earlier benchmark plan, not a new independent weight verification. Models and VMs were stopped after testing.

The initial answer extractor only collected successful completion messages. It was corrected to preserve plain replies separately, then the same saved generations were re-extracted. No model retry or prompt change was introduced by that correction. Raw journals remain under `.data/role-check/2026-10-13-native/`.

## Interpretation

This is an optional diagnostic of role wording and interaction format. It does not establish capability, host isolation, reliability over long runs or a causal benefit of the identity prefix. The previous seed-development benchmark remains separate. Truthfully identifying the underlying model while describing its AutoProteus role is compatible with the check.

The follow-up result suggests testing a concise, general clarification that conversational answers also use `finish`. That clarification has not been applied or evaluated here. There is no identity-specific tool, periodic interruption of ordinary runs or new acceptance gate in the seed.

## Reproduction

With the existing local runtime, VM appliance and cached weights, use the project's Python to run:

```text
python evaluations/role-check.py --models qwen35-9b wrench-9b harmonic-hermes-9b
```

A new private data directory is created by default. `--data-dir` must point under `.data` and cannot overwrite an existing result. `--protocol json` permits a separate future protocol experiment; only native mode was tested here.

The [driver](role-check.py) and [recorded results](role-check-results.json) are outside the editable seed.
