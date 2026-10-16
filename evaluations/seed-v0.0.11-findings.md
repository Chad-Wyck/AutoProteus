# v0.0.11: release fixes and a frozen generalization pilot

Date: 2026-10-15 (America/Regina). This revision keeps the existing editable tool interface. The only agent-loop change reads the protected controller's response-retry allowance; the study machinery stays outside the editable seed.

## Retry accounting

The starter permits two repair retries per response and resets its repair count after an accepted response. The host now uses the same accounting: `(min(max_steps, 200) + 1) * 3` model requests, including repairs for the free final response. At three allowed actions, alternating two cutoffs with each successful action and then finishing takes twelve requests and completes. Three consecutive invalid responses still stop the starter. The maximum host ceiling is 603 requests; the existing runtime, transfer, journal, frame and VM resource limits remain enforced independently.

## Empty-cache installation

The reported package-index mismatch was reproducible. The index is not consumed by the appliance builder, so it is no longer a required download. The redundant mutable netboot kernel is also removed: the actual boot kernel comes from the pinned, versioned Linux package. The builder now consumes only manifest-listed rootfs/package archives, rechecks their hashes, ignores extra cached APKs and rejects a package set without a kernel.

A real empty-cache install exposed another problem hidden by the development cache: the pinned `linux-virt-6.18.55-r0.apk` URL returned HTTP 404. Both the failed run and the subsequent successful run are retained privately. The replacement is [Alpine's linux-virt 6.18.56-r0 package](https://dl-cdn.alpinelinux.org/alpine/v3.24/main/x86_64/linux-virt-6.18.56-r0.apk), SHA-256 `755deb045cfeb8c2bcaa2b2febe01ab2101d747921e64d4cd54d0312321e8d5d`. Its control checksum matched the official x86_64 index; its payload hash matched the signed control metadata; OpenSSL verified the RSA signature using the Alpine public key from the already-pinned root filesystem.

The second run downloaded every pinned VM component into a new cache, built the appliance and completed a real isolated fixture task on Windows/WHPX. This check covers VM runtime setup; launcher Python and model-engine setup have separate existing tests. Existing model weights and saved preferences were preserved. The new manual **Empty-cache release check** workflow prepares Windows and Linux builds; this local result does not establish that the new Linux CI lane has run. Hardware boot remains a separate prepared-runner check.

## Functional growth and invocation route

Functional growth now requires an independently verified extension, preserved earlier behavior, a correctly completed task, and observed use of the required capabilities. A separate score records direct public-tool calls. Successful development-check invocation or the observed Python `Workspace(...).execute(...)` route can establish use without earning the direct-route score. Commands are parsed as inert data on the host. These observations are diagnostic evidence about cooperative candidates, not proof that arbitrary hostile code ran a particular branch.

The [derived scoring supplement](seed-v0.0.11-growth-rescoring.json) applies this distinction to two saved v0.0.10 staged candidates. Both count as functional growth and both still fail direct routing. One used the development checker; the other imported its edited Workspace inside the guest. Their original reports, original strict verdicts and the exploratory pooled **11/32** figure remain unchanged. This is rescoring saved evidence, not two additional trials. One candidate previously required a grader correction for a disposable sample file; neither received operator code repairs.

## Frozen study

The [study runner](generalization.py) records starter bytes, source fingerprint, trusted runner/grader hashes, contracts, inference profiles and qualification criteria before model calls. It calibrates each independent grader with an absent-tool negative control and a human-written positive control, executed only inside disposable VMs. Positive controls are never supplied to the model. The first calibration fixture used overly verbose descriptions and failed small-context regressions; shortened calibration descriptions passed. Both calibration attempts remain saved.

Three previously untested capabilities are checked independently: binary SHA-256, bounded CSV preview, and canonical JSON formatting. Checks cover registration, actual values, Unicode, CRLF, exact limits, rejected inputs, preserved bytes and workspace boundaries. Existing tests must remain unchanged, and candidates must add focused tests. Guest test claims alone cannot earn acceptance.

| Inference profile | Model | Context / response | Temperature | Thinking |
| --- | --- | --- | --- | --- |
| Default | Qwen3 4B Instruct | 32,768 / 8,192 | 0.2 | Model default |
| Experimental | Qwen3.5 9B Q4_K_M | 65,536 / 4,096 | 0.6 | Off |

Both trials explicitly enable terminal commands inside the VM, allow 128 actions and retain the 300-second model-request timeout. Saved application preferences are untouched. This tests the default **inference** configuration with upgrade permission enabled, rather than the literal first-launch permission state (terminal off).

A further concrete inventory-audit task lets the model choose which of two specified missing capabilities to implement first. This is bounded model selection, not arbitrary capability discovery. If the first extension passes independent checks, its exact saved checkpoint is forked for full-history and concise-context continuations. Both branches must reuse the first capability, add the second while preserving the first, activate again and finish the audit. Usage after the last activation is scored separately from development usage. Full journals and parent journals remain on disk.

Concise mode preserves complete recorded human instructions, the existing activation notice and new-phase results in inference context. It adds no activation instructions, and ordinary activation still uses full history. The experiment must produce matched viable branches before any claim about the handoff's effect is justified.

The release pilot uses one repeat per capability/profile and a fifteen-minute ceiling per model task. Qualification requires at least three repeats, all nine feature upgrades accepted and both growth branches functional. A pilot cannot qualify a profile even if every attempt succeeds. Infrastructure failures, time ceilings and operator interventions must remain visible in the results; no candidate is automatically promoted into the starter.

## Pilot results

The frozen starter fingerprint was `45c8e95c7915eb294747946fdf0696cde09f1d51b4ab2c73db8b297ac09e58ba`. The [pilot evidence](seed-v0.0.11-pilot.json) records model digests, engine version, configurations, trusted-file hashes and separate outcome components. All inference used cached models on the GTX 1080 Ti; no candidate was repaired or promoted by the operator.

| Profile | Capability | Independent contract checks | Full acceptance | Main limitation |
| --- | --- | --- | --- | --- |
| 4B default inference | SHA-256 | 11/11 | No | Added test was a placeholder with its invocation commented out |
| 4B default inference | CSV preview | 22/27 | No | Empty files, bool limit and oversized input failed |
| 4B default inference | JSON formatting | 7/18 | No | Unrepaired behavior failures; task reached 900 seconds |
| 9B experimental | SHA-256 | 11/11 | No | Valid tool and tests; source-reading loop exhausted 128 actions without finishing |
| 9B experimental | CSV preview | 27/27 | No | Two added tests expected error text inconsistent with the implementation |
| 9B experimental | JSON formatting | 18/18 | **Yes** | Completed in 92 actions, about 641 seconds; one attempt only |

The default profile accepted **0/3** upgrades; the 9B profile accepted **1/3**. The correct hashing implementations and the 9B CSV implementation remain useful partial evidence, despite failing the complete submission criteria. A correct simple example, a correct independent implementation, a green candidate suite and a completed workflow are recorded separately. The 9B results extend capability evidence beyond the previously repeated text-summary/append tasks. They do not establish repeatability or a causal performance improvement from this revision.

The 4B model's staged audit selected SHA-256 but requested activation before implementing it. The 9B model selected JSON formatting, then used 122 of its 128 actions on reads/searches and exhausted its allowance without registration or new tests. Neither first checkpoint qualified for activation. As a result, **no live-model full-history/concise comparison ran**. The implementation has a real VM regression check, but its effect on model behavior remains unmeasured. Full-history activation remains the default.

The starter fingerprint stayed unchanged throughout the study. There were no provider or VM startup failures, no operator candidate repairs, one task-level time ceiling (4B JSON), and two action-limit pauses (9B hashing and its staged audit). These limits are recorded separately from transport/infrastructure errors. Neither inference profile has a supported-repeatability claim.

## Release validation

The [validation record](seed-v0.0.11-validation.json) preserves the failed cold installation, successful verified download/build/boot, kernel provenance and regression results. The final suite ran **172 tests: 156 passed and 16 platform skips**, including **all 16 real VM checks**, in about 176 seconds. The additional VM tests cover interleaved cutoffs and concise handoff preservation. The released starter and recorded trusted runner files match the frozen study bytes. The pilot unloaded its model afterward; GPU utilization returned to zero. Linux platform checks remain separate from the Windows/WHPX hardware run reported here.
