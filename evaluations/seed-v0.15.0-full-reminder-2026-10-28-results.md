# Study outcome report

Read-only report. Saved records are unchanged. Score fractions cover fully evaluated attempts only; all launched attempts, resource stops, infrastructure errors and interruptions remain visible separately. Correct artifacts, explicit completion and actual capability use are separate observations. Not-run cells are untested, not failed attempts. Artifact counts cover recorded checks (including behavior checks), not arbitrary feature correctness. Legacy first autonomous use and complete chains are unmeasured, not zero. Labels are overlapping observations, not proven causes.

Known sums retain completeness flags. Token enforcement charges are not measured generation. No efficiency ranking is made here.

## Basic tasks

| Profile / arm | Correct checked artifacts | Explicit completion | Strict task passes / evaluated | Basic not run |
| --- | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-task-reminder/task-reminder | 5/5 | 5/5 | 5/5 | 0 |

## Extensions and use

| Profile / arm | First packages | First use | Second verified | Second use | Complete chains | Diagnostic second-stage attempts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-task-reminder/task-reminder | 5/9 | 5/5 | 5/5 | 2/5 | 2 | 0 |

## Execution accounting

| Profile / arm | Launched | Finished | Resource stops | Other infrastructure errors | Interrupted |
| --- | ---: | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-task-reminder/task-reminder | 22 | 20 | 0 | 0 | 2 |

## Cells not run

| Profile / arm | Basic | First extension | Second extension | Inference |
| --- | ---: | ---: | ---: | ---: |
| qwen35-9b-q6-task-reminder/task-reminder | 0 | 0 | 4 | 0 |

## Sampling

- qwen35-9b-q6-task-reminder: per-request; initial request seed 104729; declared initial server seed None. Server initialization is unverified by this report.

## Runtime receipts

Load time is recorded separately from trial time. Reported seed matches are not proof of RNG determinism.

| Cell | Fresh owned service | Initial server seed | Reported seed matches | Load seconds |
| --- | --- | --- | --- | --- |
| qwen35-9b-q6-task-reminder_benchmark_01 | True | 104729 | None | 8.146009 |
| qwen35-9b-q6-task-reminder_basic_exact-file | True | 104729 | None | 8.14083 |
| qwen35-9b-q6-task-reminder_basic_precise-edit | True | 104729 | None | 7.882392 |
| qwen35-9b-q6-task-reminder_basic_recovery | True | 104729 | None | 8.087092 |
| qwen35-9b-q6-task-reminder_basic_unicode | True | 104729 | None | 7.891708 |
| qwen35-9b-q6-task-reminder_basic_bug-fix | True | 104729 | None | 7.661334 |
| qwen35-9b-q6-task-reminder_first_01_sha256_file | True | 104729 | None | 8.595597 |
| qwen35-9b-q6-task-reminder_growth_01_sha256_file | True | 104729 | None | 7.450718 |
| qwen35-9b-q6-task-reminder_first_01_format_json | True | 104729 | None | 7.659148 |
| qwen35-9b-q6-task-reminder_first_01_csv_preview | True | 104729 | None | 9.560641 |
| qwen35-9b-q6-task-reminder_growth_01_csv_preview | True | 104729 | None | 9.912103 |
| qwen35-9b-q6-task-reminder_first_02_format_json | True | 130363 | None | 9.671657 |
| qwen35-9b-q6-task-reminder_first_02_csv_preview | True | 130363 | None | 9.597721 |
| qwen35-9b-q6-task-reminder_growth_02_csv_preview | True | 130363 | None | 7.871241 |
| qwen35-9b-q6-task-reminder_first_02_sha256_file | True | 130363 | None | 8.068912 |
| qwen35-9b-q6-task-reminder_growth_02_sha256_file | True | 130363 | None | 8.670796 |
| qwen35-9b-q6-task-reminder_first_03_csv_preview | True | 155921 | None | 9.920696 |
| qwen35-9b-q6-task-reminder_first_03_sha256_file | True | 155921 | None | 8.606873 |
| qwen35-9b-q6-task-reminder_growth_03_sha256_file | True | 155921 | None | 8.840444 |
| qwen35-9b-q6-task-reminder_first_03_format_json | True | 155921 | None | 8.578562 |

## Attempt details

| Cell | State | Phase | Artifacts | Explicit completion | Capability used | Failures / checks |
| --- | --- | --- | --- | --- | --- | --- |
| qwen35-9b-q6-task-reminder_benchmark_01 | completed | inference | unmeasured | unmeasured | unmeasured | No recorded failure label |
| qwen35-9b-q6-task-reminder_basic_exact-file | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-task-reminder_basic_precise-edit | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-task-reminder_basic_recovery | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-task-reminder_basic_unicode | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-task-reminder_basic_bug-fix | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| qwen35-9b-q6-task-reminder_first_01_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-task-reminder_growth_01_sha256_file | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-task-reminder_first_01_format_json | completed | first | unmeasured | unmeasured | unmeasured | candidate_tests, paused_or_action_allowance, development_not_completed |
| qwen35-9b-q6-task-reminder_growth_01_format_json | not_run | second | unmeasured | unmeasured | unmeasured | Not run: First upgrade not fully accepted; no accepted parent exists |
| qwen35-9b-q6-task-reminder_first_01_csv_preview | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-task-reminder_growth_01_csv_preview | interrupted | second | unmeasured | unmeasured | unmeasured | interrupted: User requested pause for gaming |
| qwen35-9b-q6-task-reminder_growth_01_csv_preview | completed | second | no | yes | yes | second_use |
| qwen35-9b-q6-task-reminder_first_02_format_json | completed | first | unmeasured | unmeasured | unmeasured | protected_regressions, fresh_public_invocation, wall_allowance, development_not_completed |
| qwen35-9b-q6-task-reminder_growth_02_format_json | not_run | second | unmeasured | unmeasured | unmeasured | Not run: First upgrade not fully accepted; no accepted parent exists |
| qwen35-9b-q6-task-reminder_first_02_csv_preview | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-task-reminder_growth_02_csv_preview | completed | second | no | yes | yes | second_use |
| qwen35-9b-q6-task-reminder_first_02_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-task-reminder_growth_02_sha256_file | completed | second | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-task-reminder_first_03_csv_preview | completed | first | unmeasured | unmeasured | unmeasured | candidate_tests, paused_or_action_allowance, development_not_completed |
| qwen35-9b-q6-task-reminder_growth_03_csv_preview | not_run | second | unmeasured | unmeasured | unmeasured | Not run: First upgrade not fully accepted; no accepted parent exists |
| qwen35-9b-q6-task-reminder_first_03_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| qwen35-9b-q6-task-reminder_growth_03_sha256_file | completed | second | no | no | no | second_use |
| qwen35-9b-q6-task-reminder_first_03_format_json | interrupted | first | unmeasured | unmeasured | unmeasured | interrupted: User requested pause for gaming |
| qwen35-9b-q6-task-reminder_first_03_format_json | completed | first | unmeasured | unmeasured | unmeasured | implementation, unicode_output_exact, unicode_output_exact_idempotent |
| qwen35-9b-q6-task-reminder_growth_03_format_json | not_run | second | unmeasured | unmeasured | unmeasured | Not run: First upgrade not fully accepted; no accepted parent exists |
