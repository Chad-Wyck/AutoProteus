# Study outcome report

Read-only report. Saved records are unchanged. Score fractions cover fully evaluated attempts only; all launched attempts, resource stops, infrastructure errors and interruptions remain visible separately. Correct artifacts, explicit completion and actual capability use are separate observations. Not-run cells are untested, not failed attempts. Artifact counts cover recorded checks (including behavior checks), not arbitrary feature correctness. Legacy first autonomous use and complete chains are unmeasured, not zero. Labels are overlapping observations, not proven causes.

Known sums retain completeness flags. Token enforcement charges are not measured generation. No efficiency ranking is made here.

## Basic tasks

| Profile / arm | Correct checked artifacts | Explicit completion | Strict task passes / evaluated | Basic not run |
| --- | ---: | ---: | ---: | ---: |
| gpt61-sol-low/public-verifier-feedback+task-reminder | 5/5 | 5/5 | 5/5 | 0 |

## Extensions and use

| Profile / arm | First packages | First use | Second verified | Second use | Complete chains | Diagnostic second-stage attempts |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| gpt61-sol-low/public-verifier-feedback+task-reminder | 9/9 | 9/9 | 9/9 | 9/9 | 9 | 0 |

## Experimental public verifier

These checks were disclosed before inference. They are separate from hidden qualification; extension/use scores above include any automatic correction. Public success alone does not establish a complete workflow.

| Profile / arm | Public stages checked | Passed before feedback | Corrections | Passed after feedback |
| --- | ---: | ---: | ---: | ---: |
| gpt61-sol-low/public-verifier-feedback+task-reminder | 18 | 18 | 0 | 0 |

## Execution accounting

| Profile / arm | Launched | Finished | Resource stops | Other infrastructure errors | Interrupted |
| --- | ---: | ---: | ---: | ---: | ---: |
| gpt61-sol-low/public-verifier-feedback+task-reminder | 24 | 24 | 0 | 0 | 0 |

## Cells not run

| Profile / arm | Basic | First extension | Second extension | Inference |
| --- | ---: | ---: | ---: | ---: |
| gpt61-sol-low/public-verifier-feedback+task-reminder | 0 | 0 | 0 | 0 |

## Sampling

- gpt61-sol-low: provider-default; initial request seed None; declared initial server seed None. Server initialization is unverified by this report.

## Attempt details

| Cell | State | Phase | Artifacts | Explicit completion | Capability used | Failures / checks |
| --- | --- | --- | --- | --- | --- | --- |
| gpt61-sol-low_benchmark_01 | completed | inference | unmeasured | unmeasured | unmeasured | No recorded failure label |
| gpt61-sol-low_basic_exact-file | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| gpt61-sol-low_basic_precise-edit | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| gpt61-sol-low_basic_recovery | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| gpt61-sol-low_basic_unicode | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| gpt61-sol-low_basic_bug-fix | completed | ordinary | yes | yes | unmeasured | No recorded failure label |
| gpt61-sol-low_first_01_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_growth_01_sha256_file | completed | second | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_first_01_format_json | completed | first | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_growth_01_format_json | completed | second | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_first_01_csv_preview | completed | first | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_growth_01_csv_preview | completed | second | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_first_02_format_json | completed | first | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_growth_02_format_json | completed | second | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_first_02_csv_preview | completed | first | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_growth_02_csv_preview | completed | second | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_first_02_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_growth_02_sha256_file | completed | second | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_first_03_csv_preview | completed | first | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_growth_03_csv_preview | completed | second | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_first_03_sha256_file | completed | first | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_growth_03_sha256_file | completed | second | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_first_03_format_json | completed | first | yes | yes | yes | No recorded failure label |
| gpt61-sol-low_growth_03_format_json | completed | second | yes | yes | yes | No recorded failure label |
