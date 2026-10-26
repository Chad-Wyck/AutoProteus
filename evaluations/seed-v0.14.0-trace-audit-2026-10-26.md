# Closed-trace audit: where successful extensions spent their calls

This audit reads the completed controlled-comparison exports as data. It does
not rerun models, recover a live session, execute candidate code or change any
historical score. The starter remains the v0.14.0 source fingerprint
`944dde7bd0e5185699c292b929d0fd4042031266872fc29a8af4c38a84b88465`.

## The long accepted hashing pair

| Observed timeline | v0.8.2 | v0.14.0 |
| --- | ---: | ---: |
| First runtime source edit, seconds | 101.704 | 179.076 |
| First test edit, seconds | 200.751 | 287.164 |
| First full passing development suite, seconds | 215.340 | 308.919 |
| Last full passing development suite, seconds | 420.971 | 889.300 |
| Explicit model finish, seconds | 438.596 | 916.806 |
| Successful read_file/read_section actions | 8 | 88 |
| Reads after first full passing suite | 2 | 75 |
| Post-check reads of providers.py | 1 | 59 |
| Post-check reads returning at most 100 characters | 0 | 70 |
| Reads repeating the same path, offset and observed content | 0 | 22 |

The current candidate had already made its runtime edits and written its new
tests before the first full passing suite. Its long tail includes many slices
of 20, 50 or 100 characters at nearby offsets in the registration source. This
was primarily post-check reinspection, rather than inability to locate the first
edit. A focused passing check is kept separate from the full passing check.

These counts cover successful file/section reads; the earlier runner's broader
90-read figure uses a different counting scope. The new audit records both the
original navigation metrics and its explicit narrower definition.

The trace supports investigating precise source ranges and finishing behavior.
It does **not** prove that every post-check read was unnecessary, or that the
model confused character offsets with line numbers. A passing development suite
also does not replace independent grading. Repeated identical content is an
observation about returned snippets, not proof that an entire file never changed.

## Limits and chosen next experiment

This pattern was not universal. The second accepted current hashing attempt
needed far fewer reads, and the matched current formatter made fewer model calls
than its older counterpart. The controlled comparison's 5/9 versus 4/9 acceptance
result and matched-success cost totals remain unchanged.

The one prospective intervention is the opt-in `source-outline` copied seed:
exact Unicode-character ranges for functions, classes and module declarations,
including `TOOL_SPECS`, with line numbers explicitly distinguished. No masking,
shorter recipe or new default-seed instruction is mixed into the comparison.
This is a hypothesis test, not an established improvement.

The prepared six-attempt pilot uses the new first-activation/use protocol, so
both arms receive the same prospective workflow and fresh inputs. It measures
package acceptance and first-use completion separately, with efficiency only
among matched successful first tasks with complete measurements. No second
extension is requested in that focused experiment. Live inference has not begun.

Reproduce the offline audit using:

```text
python evaluations/trace_audit.py --input .data/controlled-regression-v014-20261025 --output .data/trace-audit.json
```

Use the bundled Python executable for the platform. The saved audit includes
per-trial timelines, read paths/ranges, phases and SHA-256 identities of the
closed journals. Local audit output is `.data/protocol-v2-trace-audit-20261026.json`.
The two cited journal hashes are
`426252e799f054f38764efe023b382616f096bec58e308c1e2e22797630546b1`
and `833cfb2efde8790bdc9d06041792d17dfd30efec4fdc947737a7c23eb637cfba`.

See [the protocol/measurement guide](activation-use-study.md) and
[original comparison](seed-v0.14.0-controlled-regression-2026-10-25-findings.md).
