# Vultr A16 activation comparison — stopped October 24, 2026

The user stopped this run after the A16's measured generation speed failed to demonstrate an advantage over their GTX 1080 Ti. **Both seed variants successfully implemented, independently verified, activated and directly used `sha256_file`.** The planned six-chain comparison is incomplete and establishes no effectiveness winner.

| Arm | First hash workflow | First-stage time / actions | Inventory extension | Complete two-extension chains |
| --- | --- | --- | --- | --- |
| Current baseline | Passed, including native use and correct inspected `hash.json` | 433.482 s / 28 actions | Failed independent optional-argument schema check; no new second-stage test | 0 of 1 completed chain; 3 originally scheduled |
| Activation history | Passed, including native use and correct inspected `hash.json` | 627.479 s / 36 actions | Interrupted by the user after 6 actions; no final grade | No completed chain; 3 originally scheduled |

The baseline's second extension ran for 215.800 seconds and five actions. Protected regressions, direct public invocation, retained hashing and retained public hashing passed, but `optional_argument_schema` failed and no new focused inventory test was added. The candidate was not activated for final inventory use. Its failed attempt is not a speed win. The history arm's second-stage partial measurements include one canceled response with unknown token usage; those totals remain explicitly partial.

Four scheduled chains were never started. The interrupted history chain is not a model failure, and unstarted chains are not failed model attempts. The original primary denominator was three scheduled chains per arm; this early stop does not fulfill that schedule or permit a valid primary comparison. No candidate or variant was promoted.

## Exact setup and validation

The supplied source bundle verified against its manifest (ZIP SHA-256 `ca16a7306b465342805874f87e6b6c035f619780018025ee1ec3d782e0449fd1`). Two omitted trusted files, `evaluations/lessons/verified-submission.md` and `evaluations/local-upgrade-tasks.json`, were recovered from the local workspace only after their bytes matched the frozen plan hashes. All 57 trusted-file hashes remained unchanged. The two source packs retained identities `443ac88ee62ac0ee5c495ab93e9b32059c6f1f12fbb3a6058ce322cd45272eef` and `6b3b1290d449623f1c8d5a51ebdcb92dcffb9e8c6e6fe4fcbde276806a7a5070`.

The model was the exact Qwen3.5 9B Q6_K checkpoint, SHA-256 `073a9275e65d9c8cd2819cf5f77b99fbaa6e87ba591da6bbaa86ec073a64bfef`, without LoRA. The official Prism Linux CUDA 12.4 release matched source commit `e3de715222b2667c54a267441159a5729f11155e` and reported build 10777. Its archive verified as `380eaf66b2140e8022532626041e7bd71600eb4fa434edca1d499b7fc878d46e`. Version-pinned NVIDIA CUDA runtime 12.4.127 and cuBLAS 12.4.5.8 wheels were verified against PyPI metadata and unpacked separately; they did not replace system drivers.

Settings matched the handoff: 131,072 context tokens, 4,096 response tokens, one slot, temperature 0.6, top-p 0.8, top-k 20, min-p 0, repeat penalty 1.0, presence penalty 0, thinking disabled and reasoning budget zero. The standard production native adapter and the arm-specific `StudyBroker` were unchanged. Each extension shared 3,600 seconds, 128 actions and 65,536 generated tokens across development, independent grading, activation and final use. No automatic trial retries, candidate repairs, supplied parents or extra final-use coaching were introduced.

Vultr exposed six logical CPUs (three cores/two threads), approximately 60 GB system RAM, and an A16 reporting 15,356 MiB usable GPU memory. The inference runtime selected three CPU threads. The cloud VM had no `/dev/kvm` or exposed VMX support; loading `kvm_intel` returned “Operation not supported.” Consequently, the cloud supplied inference only, reached through an owned SSH tunnel between loopback endpoints. Candidate execution and grading used local Windows WHPX disposable network-free VMs with the exact bundled worker and verified original appliance bytes. The model server was fresh for each chain, with ordinary cache reuse within that chain. This preserves VM isolation, while Linux inference binaries, hardware, SSH latency and possible local VM contention differ from the local reference run. This is not a pure hardware-only comparison.

Fresh calibration passed both protected starter suites, 13 constructed controls, four real candidate fixtures and both actual VM/worker/broker activation-delivery paths. An accidentally duplicated calibration process was stopped; its partial work did not enter model trial scores. The retained calibration report completed all required checks. Production native connection qualification passed before the six-chain queue began.

## Inference speed evidence

The separate fixed-input diagnostic used a 9,138-token prompt and the same model, context and sampling settings. Cold prompt processing took 17.363 seconds (**526.28 input tokens/s**), followed by 116 generated tokens at **15.39 tokens/s**, for 24.853 seconds total. Repeating the input reused 9,134 cached tokens and generated 100 tokens at **15.39 tokens/s**, for 6.563 seconds total. These are separate inference measurements, not coding success results. The loaded service initially used about 8,900 MiB GPU memory. GPU use was confirmed, but the default log did not expose a verified layer-by-layer offload count; do not infer one from the `-ngl auto` request.

The user reported **17.4 generated tokens/s on their GTX 1080 Ti**. The cloud fixed-input figure is about 12% lower, but the inputs were not matched, so this is not a controlled throughput ranking. No matching local cold-prefill measurement or matched successful complete two-extension chain was obtained. Faster prompt processing remains a possible benefit, not a demonstrated end-to-end advantage. Raw call time, reported input/output tokens, stage time, grading and activation overhead remain separate in `partial-results.json` and the original stage results; cached prompt counts are not recomputed GPU work.

## Stop, saved artifacts and handoff

The user requested the stop at **10:08:00 UTC / 04:08:00 America/Regina**. The runner detected it at 10:08:06 and completed cleanup at 10:08:29. The final inference service needed a forced shutdown after its 20-second graceful-stop limit; its `Result=timeout` describes shutdown, not exhaustion of a model task allowance. A post-stop check showed `MainPID=0` and no inference-user processes; local owned driver/tunnel/test-VM checks found no remaining study processes. The subsequent extra remote audit upload timed out, so that additional audit is unavailable. All model trial evidence was already local, including per-chain runtime records and retrieved logs.

Automatic APT maintenance was masked, automatic package reboots were disabled and `needrestart` was set to list-only. No reboot was pending at preflight or either chain launch; no update-driven restart occurred during the trial. The cloud instance itself was not destroyed by this chat, and billing continues while it remains provisioned.

The source snapshot, exact arms/tasks, calibration, provider traces, journals, checkpoints, submitted candidate packs, derived candidate patches, partial results and available cloud runtime records are saved in `.data/vultr-activation-20261024/`. Successful first-extension patches are evidence for development review, not promoted defaults. The normal development workspace was not modified by this experiment.
