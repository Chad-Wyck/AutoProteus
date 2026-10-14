# Seed v0.6: Qwen3.5 9B and K2-Horizon 7B

Tested on 2026-10-14, using the local GTX 1080 Ti (11 GiB) and Windows/WHPX. Inference ran on the host; all model-written commands, candidate modules and functional probes ran in disposable VMs. No candidate was promoted. The starter and protected host-file fingerprints were unchanged at the end of both benchmark batches.

The implementation is in commits `f5e67d6` and `4ca6258`. The normalized starter fingerprint was `2374610af0dad05854e29f606c4edb5a066d525bdc7c8fb48dde42ce11160078`. [Machine-readable results](seed-v0.6-local-results.json) contain settings, source hashes, model digests, engine identity, timings, checks and read metrics. Full private journals and exported candidates remain under `.data/seed-v06-model-tests/`.

## Results

| Model, Q4_K_M | Ordinary tasks, native protocol | Upgrade implementations passing every independent functional check | Fully accepted upgrades |
| --- | ---: | ---: | ---: |
| Qwen3.5 9B | 16/16 | 0/4 | 0/4 |
| K2-Horizon 7B | 14/16 | 1/4 | 0/4 |

Each model attempted `file_summary` and `append_text` twice, starting from fresh copies. Full acceptance additionally required completion, the requested documentation and separate new test file, unchanged existing source outside the allowed scope, protected regressions, the candidate's suite, and invocation through a fresh worker. A working implementation can therefore remain an unfinished submission.

Qwen's ordinary tasks all passed, including the actual bug-fix function, deletion/recreation, long-source lookup, follow-up correction, multiple files and interruption/resume. K2 passed those except recovery and deletion/recreation: both saved the requested text without its required final newline.

A separate JSON fallback diagnostic repeated only those two K2 failures. **Both passed.** This supports offering the existing protocol choice when exact output fails. It does not establish that every K2 task is better in JSON mode, or prove whether the original omission came from generation or native tool parsing. The main 14/16 score remains unchanged.

## Upgrade details

| Model | Feature / repeat | Outcome |
| --- | --- | --- |
| Qwen | Summary / 1 | Hit 48 actions; appended tests to the existing test file instead of creating the requested file. A supplemental isolated diagnostic found the tool worked on a small sample but rejected a valid large Unicode file. |
| Qwen | Append / 1 | Hit 48 actions. Existing-file appends tried to write through a stream opened in read mode. |
| Qwen | Summary / 2 | Completed in 45 actions and passed its own 46 tests. Independent checks rejected its byte limit where the task required a character limit. Fresh-worker invocation on the small Unicode sample passed. |
| Qwen | Append / 2 | Its response was cut off after 27 actions; no partial action ran. Small-sample invocation worked, but size boundaries and invalid UTF-8 checks failed. |
| K2 | Summary / 1 | All independent functional and fresh-worker checks passed. It hit 48 actions without the requested documentation, new test file or final report. |
| K2 | Append / 1 | Hit 48 actions. Appends failed with a string-versus-bytes error; the independent checks rejected the implementation. |
| K2 | Summary / 2 | Spent the 48-action budget on exploration; exported no implementation change. |
| K2 | Append / 2 | Hit 48 actions with no implementation change. |

These results show why a model's completion statement or its own tests cannot establish upgrade success. They also show that the action budget and navigation interface contribute to unfinished attempts: K2 produced one correct implementation, even though it did not finish the submission workflow.

## Read cost and limits

Qwen used 107 read/search actions out of 168 upgrade actions (64%); K2 used 153 out of 192 (80%). The existing consecutive-identical-read metric was zero in these attempts. Many reads changed their position or length, so that metric does not capture prolonged exploration. One Qwen append attempt used 21 sections of 100 characters; one K2 summary attempt used 33 sections of 600 characters. Increasing the default section length alone would not address these explicitly chosen sizes.

The smallest useful follow-up would make remaining actions visible to the model and clarify efficient source navigation and character units. The model currently receives the task and tools without a remaining-action counter. The fixed 48-action cap is an evaluation setting, not evidence that unfinished tools could never be completed with more time or Resume. This run did not test such a continuation or add a planner.

## Reproduction and hardware

The common profile was native tools, 32,768 context tokens, 4,096 response tokens, temperature 0.6 and no fixed sampling seed. Ordinary tasks had 32 actions / 180 seconds; upgrades had 48 actions / 900 seconds. Model requests allowed 300 seconds and commands 60 seconds. There were two independent attempts per feature, and one ordinary-suite run per model. This is a small practical sample.

Ollama **0.40.4** was installed from its pinned, verified Windows archive. Qwen advertised thinking support, which was enabled; K2 did not advertise that capability, so its thinking option stayed unset. Qwen's placement report showed the whole model on the GPU. K2 used 35/37 layers on the GPU, with some host-memory offload at this context size.

- [Qwen quantization](https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF), revision `182be2fd6c7bc44887d88a91cb03ff009cc9f549`: 6,169,341,984-byte weight file; SHA-256 `d784ce9eda1a5a7b51e8f705a9e6310844bf4f173654d115823c775fdea56d43`. The existing cached weight was rehashed.
- [Official IFM K2 quantization](https://huggingface.co/IFM/K2-Horizon-7B-GGUF), revision `9fb01f7b397994455262f4b8256e4e00e4949ea9`: 5,592,217,984-byte weight file; SHA-256 `eb89c15a0ae9712be2ee462bf43802de14200f20f93b73da6eb68c2ebdd28e4e`. It was downloaded and rehashed before inference. Its metadata reports about 9B total parameters despite the 7B-core name.

K2's [model card](https://huggingface.co/IFM/K2-Horizon-7B-GGUF) recommends high reasoning, temperature 1.0, top-p 0.95 and at least 32,768 output tokens for its reported evaluations. This local comparison used a much smaller response allowance and a common practical profile. It is not a reproduction of those published scores or a claim about optimal K2 performance.

The unchanged starter's 34 guest tests passed before the model runs. The upgrade graders were calibrated with absent-tool negatives and human-written reference positives, including fresh-worker calls. Windows and Linux regression suites passed (124 discovered tests with platform-specific skips), including nine real VM checks on each platform. Linux native fixtures also passed; the verified private Python inventory remained unchanged afterward. GitHub's [Windows/Linux CI run](https://github.com/Chad-Wyck/AutoProteus/actions/runs/38623578938) passed. Browser checks covered imports, persistent Stop after New task, title search, Trash/Restore and preservation of imported bytes.

Functional checks remain diagnostics over known cases, not proof that hostile candidate code is honest. The isolation boundary does not rely on accepting a candidate, its tests or its claims.
