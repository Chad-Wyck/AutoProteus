# Evidence report — November 4, 2026

**No demonstrated downstream improvement:** the most recent completed
frontier/Builder-authored teacher intervention tied its untouched control on
four synthetic tasks and used more tokens. Its real-student comparison was
not run. The newer focused continuation subsequently stopped because its
conditional probes found no consistent surrogate effect. No downstream student
inference ran in that continuation.

The local teacher is Qwen3.5-4B Q8_0; the real student is Qwen3.5-0.8B.
4B and 0.4B are illustrative sizes for future tests. No 0.4B model was tested
in these reports. Other model sizes/families may change the result and cost.
Builder/frontier code authored the interventions; the exact frontier provider,
model revision and assistant usage are not established by these source reports.
These were direct numerical edits, not gradient training or teacher-authored
self-improvement.

## Completed, stopped and unrun work

| Work | Status and reported result | Interpretation |
| --- | --- | --- |
| Published p50c 0.8B repair reconstruction and native quantization check | Completed: original F32 0/4, repaired F32 3/4; original Q6_K 0/4, repaired Q6_K 3/4 | Exact published-patch reconstruction and four-case evidence; not autonomous discovery or a full benchmark replication |
| Earlier layer-31 manual 4B intervention, real 0.8B comparison | Completed: edited teacher's retained target 0/8; untouched teacher control 1/8 after restoring original target | No useful student repair; the control's 1/8 is baseline-equivalent |
| Operator-recovered intermediate student patches | Completed: original 1/8; early five-weight QKV patch 0/8; normalization plus historical rounding 1/8; rounding-only 1/8 | Selected intermediate artifacts, not final submissions; familiar cases; no extra solved case |
| Earlier executable eight-fixture diagnostic | Completed: untouched numeric state/testing 6/8, complete cells 6/8; edited 7/8 and 5/8 respectively | Separate metrics; helper-signature and fixture-shape limitations; stubs performed no student inference |
| Corrected overnight diagnostics | Completed: paired explicit completions 7/8 untouched vs 5/8 retained manual edit; fresh clarified untouched 6/8; standalone synthetic recovery passed; neutral selection 0/2 complete | These are distinct experiments, not a pooled pass. No real student pilot qualified |
| Sole layer-26 teacher patch, completed bounded screen | Completed: untouched 4/4, edited 4/4; 2,019 vs 7,751 sampled tokens | No completion gain; untouched at ceiling. Spending gate stopped subsequent stages |
| Behavioral confirmation, ordinary preservation and real 0.8B comparison for that layer-26 patch | UNRUN | Missing outcomes, not zero scores and not successful gates |
| Focused one-channel study, initial attempt and strict-policy continuation | Interrupted: 2 attempted responses, 0 completed; 128 charged/uncertain tokens; no patch or student inference | Infrastructure/ownership incomplete, not scored model failures; one rejection captured background Compute activity |
| Memory-availability continuation, publication 005 | Final receipt observed at 23:08 UTC: `conditional_support_stop`; no consistent conditional surrogate effect; no replacement channels/doses; no student inference | Local receipt reports owned workers/VMs closed and originals unchanged. This is a probe-selection stop, not a student-improvement result; final independent review is not established here |
| Proposed 5% background-load tolerance | Assessment only; superseded before use | Not an applied policy or inference result |

The completed layer-26 patch halved 16 canonical BF16 FFN down-projection
columns. It intentionally changed 40,960 canonical values. Reported deployed
Q8 matrix delta norm was 2.0666823%, including measured quantization spillover
into neighboring columns. The edited teacher's hash was
`700b169bcaafdb588b2d6686b613acc6a20f70c15f862a9734254f4a361be534`.
Construction validity does not establish behavioral usefulness. The exact
coordinate/payload artifact is private and not shipped.

## What to test next

Use real tensor shapes and explicit helper contracts to find genuine untouched
teacher failures on development tasks. A screen at ceiling cannot show an
accuracy gain. Freeze a new bounded candidate, verify numerical effects and
preservation, then test whether the edited teacher creates better final student
artifacts than an untouched teacher under matched conditions. The new protocol
must preserve this negative history instead of relabeling an old gate as passed.

Primary claims should concern held-out student correctness and retention.
Synthetic execution, margin changes, reduced tokens, valid patches and attractive
weight geometry are intermediate evidence only. Cross-size transfer, different
families, training, self-editing and recursive improvement remain unestablished.

## Provenance and confidence

This summary is based on local project reports, whose names and SHA-256 hashes
are recorded in SOURCE-MANIFEST.json. The branch preparer reviewed those reports
and source code but did not independently rerun model inference, reconstruct
the real artifacts or regrade private responses. Reported historical scores and
independent-review findings are attributed to those local records. Private raw
evidence and hidden cases are excluded, so another user must run a new independent
comparison rather than claim byte-for-byte historical result verification.

Prepublication update: publication 005's RESULT.json and host-closure receipt
became available after the original report snapshot. Their hashes are recorded
separately in SOURCE-MANIFEST.json; their raw contents are not distributed.
The result records 16,384 sampled untouched-development tokens plus 128 inherited
charged/uncertain tokens, for 16,512 charged tokens. No completed downstream
student comparison follows from that expenditure. This update reads the receipts
without rerunning the study or claiming an independent scientific result audit.

Upstream provenance: [Sparks of Weight-Space Programming](https://rikiyat.github.io/blog/weight-space-programming/)
and [Experiment 8 pinned at 4d09ba6d6a7e891dd8063974dfe81b3d78e3494f](https://github.com/RikiyaT/lm_understand-logs/tree/4d09ba6d6a7e891dd8063974dfe81b3d78e3494f/exp8_math).
These are references from the source reports, not newly verified external
benchmark claims. No third-party logs or weights were copied into this handoff.
