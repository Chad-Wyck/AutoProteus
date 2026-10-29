# Study outcome report

Read-only report. Saved records are unchanged. Score fractions cover fully evaluated attempts only; all launched attempts, resource stops, infrastructure errors and interruptions remain visible separately. Correct artifacts, explicit completion and actual capability use are separate observations. Not-run cells are untested, not failed attempts. Artifact counts cover recorded checks (including behavior checks), not arbitrary feature correctness. Legacy first autonomous use and complete chains are unmeasured, not zero. Labels are overlapping observations, not proven causes.

Known sums retain completeness flags. Token enforcement charges are not measured generation. No efficiency ranking is made here.

## Basic tasks

| Profile / arm | Correct checked artifacts | Explicit completion | Strict task passes / evaluated | Basic not run |
| --- | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-csv-feedback/public-verifier-feedback+task-reminder | 5/5 | 5/5 | 5/5 | 0 |

## Extensions and use

| Profile / arm | First packages | First use | Second verified | Second use | Complete chains | Diagnostic second-stage attempts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-csv-feedback/public-verifier-feedback+task-reminder | 6/9 | 5/6 | 6/6 | 6/6 | 5 | 1 |

## Experimental public verifier

These checks were disclosed before inference. They are separate from hidden qualification; extension/use scores above include any automatic correction. Public success alone does not establish a complete workflow.

| Profile / arm | Public stages checked | Passed before feedback | Corrections | Passed after feedback |
| --- | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-csv-feedback/public-verifier-feedback+task-reminder | 12 | 11 | 1 | 1 |

## Execution accounting

| Profile / arm | Launched | Finished | Resource stops | Other infrastructure errors | Interrupted |
| --- | ---: | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-csv-feedback/public-verifier-feedback+task-reminder | 21 | 21 | 0 | 0 | 0 |

## Cells not run

| Profile / arm | Basic | First extension | Second extension | Inference |
| --- | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-csv-feedback/public-verifier-feedback+task-reminder | 0 | 0 | 3 | 0 |

## Sampling

- qwen35-9b-q6-csv-feedback: per-request; initial request seed 104729; declared initial server seed None. Server initialization is unverified by this report.

## Runtime receipts

Load time is recorded separately from trial time. Reported seed matches are not proof of RNG determinism.

| Cell | Fresh owned service | Initial server seed | Reported seed matches | Load seconds |
| --- | --- | --- | --- | --- |
| qwen35-9b-q6-csv-feedback_benchmark_01 | True | 104729 | None | 7.3356 |
| qwen35-9b-q6-csv-feedback_basic_exact-file | True | 104729 | None | 7.200885 |
| qwen35-9b-q6-csv-feedback_basic_precise-edit | True | 104729 | None | 7.216911 |
| qwen35-9b-q6-csv-feedback_basic_recovery | True | 104729 | None | 7.156534 |
| qwen35-9b-q6-csv-feedback_basic_unicode | True | 104729 | None | 7.240414 |
| qwen35-9b-q6-csv-feedback_basic_bug-fix | True | 104729 | None | 7.197173 |
| qwen35-9b-q6-csv-feedback_first_01_sha256_file | True | 104729 | None | 7.163645 |
| qwen35-9b-q6-csv-feedback_growth_01_sha256_file | True | 104729 | None | 7.171873 |
| qwen35-9b-q6-csv-feedback_first_01_format_json | True | 104729 | None | 7.18077 |
| qwen35-9b-q6-csv-feedback_growth_01_format_json | True | 104729 | None | 7.217684 |
| qwen35-9b-q6-csv-feedback_first_01_csv_preview | True | 104729 | None | 7.165584 |
| qwen35-9b-q6-csv-feedback_growth_01_csv_preview | True | 104729 | None | 7.217197 |
| qwen35-9b-q6-csv-feedback_first_02_format_json | True | 130363 | None | 7.273388 |
| qwen35-9b-q6-csv-feedback_growth_02_format_json | True | 130363 | None | 7.191242 |
| qwen35-9b-q6-csv-feedback_first_02_csv_preview | True | 130363 | None | 7.169511 |
| qwen35-9b-q6-csv-feedback_first_02_sha256_file | True | 130363 | None | 7.35938 |
| qwen35-9b-q6-csv-feedback_growth_02_sha256_file | True | 130363 | None | 7.187761 |
| qwen35-9b-q6-csv-feedback_first_03_csv_preview | True | 155921 | None | 7.578739 |
| qwen35-9b-q6-csv-feedback_first_03_sha256_file | True | 155921 | None | 7.215423 |
| qwen35-9b-q6-csv-feedback_growth_03_sha256_file | True | 155921 | None | 7.232097 |
| qwen35-9b-q6-csv-feedback_first_03_format_json | True | 155921 | None | 7.306636 |

## Attempt details

| Cell | State | Phase | Artifacts | Explicit completion | Capability used | Failures / checks |
| --- | --- | --- | --- | --- | --- | --- |
| qwen35-9b-q6-csv-feedback_benchmark_01 | completed | inference | unmeasured | unmeasured | unmeasured | No recorded failure label |
| qwen35-9b-q6-csv-feedback_basic_exact-file | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-csv-feedback_basic_precise-edit | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-csv-feedback_basic_recovery | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-csv-feedback_basic_unicode | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-csv-feedback_basic_bug-fix | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_01_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_growth_01_sha256_file | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_01_format_json | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_growth_01_format_json | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_01_csv_preview | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_growth_01_csv_preview | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_02_format_json | completed | first | yes | yes | no | first_use |
| qwen35-9b-q6-csv-feedback_growth_02_format_json | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_02_csv_preview | completed | first | unmeasured | unmeasured | unmeasured | submission_scope, implementation, provider_or_format, quoted_5, quoted_20 |
| qwen35-9b-q6-csv-feedback_growth_02_csv_preview | not_run | second | unmeasured | unmeasured | unmeasured | Not run: First upgrade not fully accepted; no accepted parent exists |
| qwen35-9b-q6-csv-feedback_first_02_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_growth_02_sha256_file | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_03_csv_preview | completed | first | unmeasured | unmeasured | unmeasured | implementation, exact_1, unicode_exact_1 |
| qwen35-9b-q6-csv-feedback_growth_03_csv_preview | not_run | second | unmeasured | unmeasured | unmeasured | Not run: First upgrade not fully accepted; no accepted parent exists |
| qwen35-9b-q6-csv-feedback_first_03_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_growth_03_sha256_file | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_03_format_json | completed | first | unmeasured | unmeasured | unmeasured | submission_scope, missing_candidate_tests |
| qwen35-9b-q6-csv-feedback_growth_03_format_json | not_run | second | unmeasured | unmeasured | unmeasured | Not run: First upgrade not fully accepted; no accepted parent exists |
