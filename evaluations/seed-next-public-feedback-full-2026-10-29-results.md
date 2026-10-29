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
| qwen35-9b-q6-csv-feedback/public-verifier-feedback+task-reminder | 7/9 | 7/7 | 7/7 | 7/7 | 7 | 0 |

## Experimental public verifier

These checks were disclosed before inference. They are separate from hidden qualification; extension/use scores above include any automatic correction. Public success alone does not establish a complete workflow.

| Profile / arm | Public stages checked | Passed before feedback | Corrections | Passed after feedback |
| --- | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-csv-feedback/public-verifier-feedback+task-reminder | 14 | 12 | 2 | 2 |

## Execution accounting

| Profile / arm | Launched | Finished | Resource stops | Other infrastructure errors | Interrupted |
| --- | ---: | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-csv-feedback/public-verifier-feedback+task-reminder | 23 | 22 | 0 | 0 | 1 |

## Cells not run

| Profile / arm | Basic | First extension | Second extension | Inference |
| --- | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-csv-feedback/public-verifier-feedback+task-reminder | 0 | 0 | 2 | 0 |

## Sampling

- qwen35-9b-q6-csv-feedback: per-request; initial request seed 104729; declared initial server seed None. Server initialization is unverified by this report.

## Runtime receipts

Load time is recorded separately from trial time. Reported seed matches are not proof of RNG determinism.

| Cell | Fresh owned service | Initial server seed | Reported seed matches | Load seconds |
| --- | --- | --- | --- | --- |
| qwen35-9b-q6-csv-feedback_benchmark_01 | True | 104729 | None | 7.702311 |
| qwen35-9b-q6-csv-feedback_basic_exact-file | True | 104729 | None | 7.630025 |
| qwen35-9b-q6-csv-feedback_basic_precise-edit | True | 104729 | None | 7.660064 |
| qwen35-9b-q6-csv-feedback_basic_recovery | True | 104729 | None | 7.632203 |
| qwen35-9b-q6-csv-feedback_basic_unicode | True | 104729 | None | 7.6661 |
| qwen35-9b-q6-csv-feedback_basic_bug-fix | True | 104729 | None | 7.669695 |
| qwen35-9b-q6-csv-feedback_first_01_sha256_file | True | 104729 | None | 7.654918 |
| qwen35-9b-q6-csv-feedback_growth_01_sha256_file | True | 104729 | None | 7.436189 |
| qwen35-9b-q6-csv-feedback_first_01_format_json | True | 104729 | None | 8.288325 |
| qwen35-9b-q6-csv-feedback_growth_01_format_json | True | 104729 | None | 7.435119 |
| qwen35-9b-q6-csv-feedback_first_01_csv_preview | True | 104729 | None | 8.064041 |
| qwen35-9b-q6-csv-feedback_growth_01_csv_preview | True | 104729 | None | 7.710543 |
| qwen35-9b-q6-csv-feedback_first_02_format_json | True | 130363 | None | 10.679782 |
| qwen35-9b-q6-csv-feedback_growth_02_format_json | True | 130363 | None | 8.070242 |
| qwen35-9b-q6-csv-feedback_first_02_csv_preview | True | 130363 | None | 8.561598 |
| qwen35-9b-q6-csv-feedback_growth_02_csv_preview | True | 130363 | None | 9.977976 |
| qwen35-9b-q6-csv-feedback_first_02_sha256_file | True | 130363 | None | 8.312327 |
| qwen35-9b-q6-csv-feedback_growth_02_sha256_file | True | 130363 | None | 7.849048 |
| qwen35-9b-q6-csv-feedback_first_03_csv_preview | True | 155921 | None | 9.710835 |
| qwen35-9b-q6-csv-feedback_growth_03_csv_preview | True | 155921 | None | 7.219829 |
| qwen35-9b-q6-csv-feedback_first_03_sha256_file | True | 155921 | None | 7.226947 |
| qwen35-9b-q6-csv-feedback_first_03_format_json | True | 155921 | None | 7.271839 |

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
| qwen35-9b-q6-csv-feedback_first_02_format_json | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_growth_02_format_json | interrupted | second | unmeasured | unmeasured | unmeasured | interrupted: Unexpected study-owner process exit; runner, model and VM confirmed absent. Cause unestablished. Completed results preserved; unfinished attempt retried separately under existing authorization. |
| qwen35-9b-q6-csv-feedback_growth_02_format_json | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_02_csv_preview | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_growth_02_csv_preview | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_02_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_growth_02_sha256_file | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_03_csv_preview | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_growth_03_csv_preview | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-csv-feedback_first_03_sha256_file | completed | first | unmeasured | unmeasured | unmeasured | submission_scope |
| qwen35-9b-q6-csv-feedback_growth_03_sha256_file | not_run | second | unmeasured | unmeasured | unmeasured | Not run: First upgrade not fully accepted; no accepted parent exists |
| qwen35-9b-q6-csv-feedback_first_03_format_json | completed | first | unmeasured | unmeasured | unmeasured | submission_scope, missing_candidate_tests |
| qwen35-9b-q6-csv-feedback_growth_03_format_json | not_run | second | unmeasured | unmeasured | unmeasured | Not run: First upgrade not fully accepted; no accepted parent exists |
