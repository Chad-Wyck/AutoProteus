# Local model screening and second-pass growth

## Main findings

- Qwen3.5 **4B** at **128K context**, Q4_K_M, thinking off, temperature 0.6, earned **2/3 fully accepted first-pass upgrades**: SHA-256 and JSON formatting. This is a different model from the default Qwen3 4B. At 64K, its SHA candidate passed behavior, candidate tests, protected regressions and public invocation, but the context guard stopped the task before completion. Its JSON implementation passed the behavior cases but had two failing assertions in its own tests.
- Qwopus3.5 **9B Coder** at **64K** earned **1/3 fully accepted upgrades**, SHA-256. Ministral 3 8B and FineEnvs 2.6B earned no accepted upgrades under their screened profiles. Phi-4-mini did not qualify for upgrade testing: native calls failed compatibility checks, while the separate JSON diagnostic completed 3/5 basic tasks against a 4/5 gate.
- **No second-pass edit passed independent verification.** The exact accepted SHA seeds were used for Qwopus at 64K and a separately labelled 128K diagnostic, and Qwen3.5 4B at 128K. All three retained the original SHA behavior and public invocation, and preserved protected source/tests. Their new JSON capability failed ordinary formatting behavior and their added test suite. The controller therefore did not activate any second edit or run the final audit phase. This was a correctness failure, not a penalty for choosing a development invocation route.
- The 64K Qwopus follow-up stopped at the context guard with a missing import. Both 128K follow-ups reached 128 actions, largely inspecting source, and requested activation with defects remaining. Qwopus did successfully invoke its earlier SHA tool through the development command interface during the 128K follow-up. No final audit receipt or cumulative-use success was established.
- The narrow positive evidence is useful: a 4B model can make independently accepted seed extensions under a suitable profile. These single exploratory attempts do **not** establish repeatability, a best-in-class ranking, or that context alone caused the improvement. No base Qwen3.5 9B comparison was rerun in this batch.

The bounded main queue completed before the two explicitly recorded context diagnostics. Ministral finished before the latest overnight continuation and is included as context. The unfinished Qwopus screening was completed rather than discarded. Sampling was not retried secretly; all failed profiles and attempts remain in the report.

## Suggested next experiment

Freeze the accepted 4B 128K profile and repeat fresh SHA/JSON extension tasks, followed by the same cumulative audit. Measure accepted upgrades first, then source reads, actual usage and elapsed time among matched successes. Test one source-navigation treatment against the unchanged seed rather than adding another general framework. Many failures spent most of their actions on tiny overlapping source reads or unsuccessful exact-text edits.

Also compare conservative context admission with runtime token measurements in a separately reviewed experiment. A context-estimate stop and a server context overflow are different events. Increasing context provided room for accepted work here, while the 128K follow-ups still exposed coding and test-quality failures. Stronger exact-output checks written by the model are another concrete target; passing most of its own tests did not guarantee correct ordinary JSON output.

No candidate was promoted. Production source, user preferences, isolation boundaries and the prepared Qwen studies remain unchanged. All model-written Python was executed only in disposable network-free VMs. GPU model servers were stopped after testing. Private source snapshots, model receipts, requests, responses, journals, diffs and independent grades are retained at [the evidence directory](D:/AI_New/AP/.data/local-model-screen-20261016).


Date: 2026-10-16 (America/Regina). AutoProteus v0.0.12, commit `380c96b`.

Exploratory screening on a GTX 1080 Ti (11,264 MiB VRAM), Windows, driver 581.29. One model at a time; model-generated code and all grading execute only in disposable network-free QEMU/WHPX VMs. No candidate was repaired by the operator or promoted into the normal seed.

Frozen starter: `419c5bf59734066c86c40fbe81206aa20a068226b14eb86b1524dbb832cc37a9`. All three independent graders reuse the identical, hash-checked real-VM calibration from the Bonsai pilot. The normal seed, app preferences and prepared Qwen studies are unchanged.

| Profile | Basic tasks | Independent contracts passed | Fully accepted upgrades | Peak sampled total GPU MiB | State |
| --- | ---: | ---: | ---: | ---: | --- |
| fineenvs-native-64k-thinking | 5/5 | 0/3 | 0/3 | 4818 | finished |
| ministral-native-64k-q8 | 4/5 | 0/3 | 0/3 | 11020 | finished |
| phi4mini-native-64k | 0/5 | 0/0 | 0/0 | 8974 | finished |
| phi4mini-native-64k-json | 3/5 | 0/0 | 0/0 | 8974 | finished |
| qwen35-4b-native-128k | 4/5 | 2/3 | 2/3 | 6880 | finished |
| qwen35-4b-native-64k | 4/5 | 2/3 | 0/3 | 5522 | finished |
| qwopus-native-64k-nonthinking | 5/5 | 1/3 | 1/3 | 7540 | finished |

## Method and limits

Five ordinary tasks screen exact file creation, precise JSON edits, missing-file recovery, Unicode and a small bug fix. A profile needs at least 4/5 passes before hashing, CSV preview and JSON-formatting upgrade attempts. Each upgrade is one attempt on a fresh starter, with independent boundary/Unicode/path checks, protected regressions, candidate tests and public invocation graded separately.

Each profile uses native tools or a separately labeled JSON diagnostic, 4,096 response tokens, 128 actions, a 300-second request limit and a 900-second upgrade-task limit. No fixed sampling seed. The host adapter preserves production context validation and response normalization and uses deterministic nine-digit call IDs consistently across the models. Actual requests/responses and metric-completeness records are retained.

The shared runtime is the verified PrismML llama.cpp `prism-b10777-e3de715` Windows CUDA 12.4 build already used for Bonsai. Text-only inference; no vision projectors or draft models. Model weights are pinned by publisher revision and SHA-256. FineEnvs uses a separately documented offline conversion of its original safetensors, without remote model code.

These profiles use different publisher/family sampling settings and quantization formats. This is not a controlled model ranking or a demonstration of repeatability. A missing/failed independent contract grade is not the same as an implementation that passed behavior but failed its own tests or completion workflow. A context-estimate stop is not an observed GPU memory failure. Runtime and protocol diagnostics must remain separate.

CPU-only conversion dependencies were prepared during Ministral screening; the heavy checkpoint conversion was deferred until its timed run ended. Timings are exploratory and do not establish matched-success efficiency gains.

## Per-profile evidence

### fineenvs-native-64k-thinking

FineEnvs LFM2.5 2.6B multiharness RL Q8_0. Locally converted official full checkpoint. Temperature 0.8 and top-p 1 follow published training settings; these are not a reproduction of its research evaluation. The saved original template unconditionally appends <think>; preserve reasoning with a 1024-token server-side thinking budget inside the 4096-token total response limit. This is a separate inference profile, not the original research harness.

Context 65536, output 4096, temperature 0.8, thinking True, protocol `native`, cache K/V `q8_0` / `q8_0`.

Weight SHA-256: `9acfac46bbb8a2fba22c9a33a52fba7accdc0581fba2f757eda443f1c38a755b`.

- `sha256_file`: 524.23 seconds, 38 actions, status `error`, category `context`. Independent cases 0/0, candidate-suite exit None, accepted=False.
  Runtime changed=False, protected files unchanged=True, allowed files only=True, protected regressions=None, public invocation=None.
- `csv_preview`: 472.63 seconds, 34 actions, status `error`, category `context`. Independent cases 5/27, candidate-suite exit 1, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=False, public invocation=False.
  Failing independent cases: {"registered": false, "schema": false, "empty_1": false, "empty_5": false, "empty_20": false, "quoted_1": false, "quoted_5": false, "quoted_20": false, "exact_1": false, "exact_5": false, "exact_20": false, "many_1": false, "many_5": false, "many_20": false, "default_limit": false, "invalid_limit_0": false, "invalid_limit_21": false, "invalid_limit_True": false, "invalid_limit_'5'": false, "invalid_limit_None": false, "reject_bad": false, "reject_large": false}.

```text
{"check": "candidate tests", "passed": false, "tests": 49, "failures": 0, "errors": 2, "skipped": 0}
test_whole_file_context_omission_never_pretends_to_be_a_full_read (test_seed.AgentTests.test_whole_file_context_omission_never_pretends_to_be_a_full_read)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_seed.py", line 812, in test_whole_file_context_omission_never_pretends_to_be_a_full_read
    result = workspace.execute('read_file', {'path': 'text.txt'})
  File "/work/task/harness/autoproteus/tools.py", line 123, in execute
    raise ValueError(f"This file exceeds {LIMIT} characters; use read_section with start and length")
ValueError: This file exceeds 12000 characters; use read_section with start and length

test_whole_file_returns_complete_text_or_rejects_oversize (test_seed.WorkspaceTests.test_whole_file_returns_complete_text_or_rejects_oversize)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_seed.py", line 123, in test_whole_file_returns_complete_text_or_rejects_oversize
    result = workspace.execute('read_file', {'path': 'text.txt'})
  File "/work/task/harness/autoproteus/tools.py", line 123, in execute
    raise ValueError(f"This file exceeds {LIMIT} characters; use read_section with start and length")
ValueError: This file exceeds 12000 characters; use read_section with start and length


```

- `format_json`: 306.87 seconds, 30 actions, status `completed`, category `None`. Independent cases 8/18, candidate-suite exit 0, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=False.
  Failing independent cases: {"object": false, "object_idempotent": false, "array": false, "array_idempotent": false, "scalar": false, "scalar_idempotent": false, "exact_output_limit": false, "preserve_invalid": false, "preserve_large": false, "preserve_expanded": false}.

GPU after shutdown: NVIDIA GeForce GTX 1080 Ti, 11264, 1177, 75, 0.

### ministral-native-64k-q8

Ministral 3 8B Instruct 2512 Q4_K_M. Mistral official GGUF. Temperature follows publisher recommendation below 0.1.

Context 65536, output 4096, temperature 0.05, thinking False, protocol `native`, cache K/V `q8_0` / `q8_0`.

Weight SHA-256: `33e7a72cf5e6e2cfc2f2847075acc013d68bba023e35310cef86b5cf8fdca761`.

- Basic `unicode`: status `error`, category `connection`, artifact checks [{'path': 'unicode.txt', 'passed': True}], format repairs 1.
- `sha256_file`: 455.46 seconds, 94 actions, status `error`, category `context`. Independent cases 0/0, candidate-suite exit None, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=False, public invocation=False.
- `csv_preview`: 499.49 seconds, 91 actions, status `error`, category `context`. Independent cases 15/27, candidate-suite exit 1, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=False.
  Failing independent cases: {"empty_1": false, "empty_5": false, "empty_20": false, "quoted_1": false, "quoted_5": false, "quoted_20": false, "exact_5": false, "exact_20": false, "many_1": false, "many_5": false, "many_20": false, "reject_large": false}.

```text
{"check": "candidate tests", "passed": false, "tests": 50, "failures": 0, "errors": 1, "skipped": 0}
test_csv_preview (unittest.loader._FailedTest.test_csv_preview)
ImportError: Failed to import test module: test_csv_preview
Traceback (most recent call last):
  File "/usr/lib/python3.14/unittest/loader.py", line 433, in _find_test_path
    module = self._get_module_from_name(name)
  File "/usr/lib/python3.14/unittest/loader.py", line 374, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/work/task/harness/tests/test_csv_preview.py", line 40
    csv_content = "field1,field2\n""quoted, comma",value\n""another, quoted",value"
                                                         ^
SyntaxError: unexpected character after line continuation character



```

- `format_json`: 411.77 seconds, 81 actions, status `error`, category `context`. Independent cases 0/0, candidate-suite exit None, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=False, public invocation=False.

GPU after shutdown: NVIDIA GeForce GTX 1080 Ti, 11264, 1082, 75, 0.

### phi4mini-native-64k

Phi-4-mini-instruct 3.8B Q6_K. Publisher GGUF of Microsoft model; greedy sampling follows official inference examples. Different family and quantization, not a controlled model-only comparison.

Context 65536, output 4096, temperature 0.0, thinking False, protocol `native`, cache K/V `q8_0` / `q8_0`.

Weight SHA-256: `59dba927b98f39c26859aab7fb27d5f577666f8a5db38f0eccf3f207902ba23b`.

Upgrade gate failed; no upgrade attempts were launched.

- Basic `exact-file`: status `error`, category `compatibility`, artifact checks [{'path': 'greeting.txt', 'passed': False}], format repairs 3.
- Basic `precise-edit`: status `error`, category `compatibility`, artifact checks [{'path': 'settings.json', 'passed': False}], format repairs 3.
- Basic `recovery`: status `error`, category `compatibility`, artifact checks [{'path': 'missing.txt', 'passed': False}], format repairs 3.
- Basic `unicode`: status `error`, category `compatibility`, artifact checks [{'path': 'unicode.txt', 'passed': False}], format repairs 3.
- Basic `bug-fix`: status `error`, category `compatibility`, artifact checks [{'path': 'add.py', 'passed': False}], format repairs 3.

GPU after shutdown: NVIDIA GeForce GTX 1080 Ti, 11264, 1177, 74, 0.

### phi4mini-native-64k-json

Phi-4-mini-instruct 3.8B Q6_K. Publisher GGUF of Microsoft model; greedy sampling follows official inference examples. Different family and quantization, not a controlled model-only comparison.

Context 65536, output 4096, temperature 0.0, thinking False, protocol `json`, cache K/V `q8_0` / `q8_0`.

Weight SHA-256: `59dba927b98f39c26859aab7fb27d5f577666f8a5db38f0eccf3f207902ba23b`.

Upgrade gate failed; no upgrade attempts were launched.

- Basic `unicode`: status `completed`, category `task`, artifact checks [{'path': 'unicode.txt', 'passed': False}], format repairs 0.
- Basic `bug-fix`: status `waiting`, category `task`, artifact checks [{'path': 'add.py', 'passed': False}], format repairs 0.

GPU after shutdown: NVIDIA GeForce GTX 1080 Ti, 11264, 1177, 72, 0.

### qwen35-4b-native-128k

Qwen3.5 4B Q4_K_M. Publisher GGUF of Qwen3.5 4B, previously untested here. Same experimental nonthinking 0.6 profile as the Qwen9B/Qwopus screening, not the publisher general-purpose recommended profile.

Context 131072, output 4096, temperature 0.6, thinking False, protocol `native`, cache K/V `q8_0` / `q8_0`.

Weight SHA-256: `13c16f426047e2de38cd075bdade4a7bcbc8c774384876f677740cda65f8a983`.

- Basic `exact-file`: status `completed`, category `task`, artifact checks [{'path': 'greeting.txt', 'passed': False}], format repairs 1.
- `sha256_file`: 255.68 seconds, 50 actions, status `completed`, category `None`. Independent cases 11/11, candidate-suite exit 0, accepted=True.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=True.
- `csv_preview`: 489.54 seconds, 128 actions, status `paused`, category `None`. Independent cases 14/27, candidate-suite exit 1, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=False.
  Failing independent cases: {"empty_1": false, "empty_5": false, "empty_20": false, "quoted_1": false, "quoted_5": false, "quoted_20": false, "exact_1": false, "exact_5": false, "exact_20": false, "many_1": false, "many_5": false, "many_20": false, "default_limit": false}.

```text
{"check": "candidate tests", "passed": false, "tests": 67, "failures": 0, "errors": 14, "skipped": 0}
test_basic_csv_read (test_csv_preview.CSVPreviewTests.test_basic_csv_read)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_csv_preview.py", line 35, in test_basic_csv_read
    result = workspace.execute('csv_preview', {'path': 'test.csv', 'limit': 5})
  File "/work/task/harness/autoproteus/tools.py", line 233, in execute
    raise ValueError("Unknown tool: " + str(tool))
ValueError: Unknown tool: csv_preview

test_crlf_preserved (test_csv_preview.CSVPreviewTests.test_crlf_preserved)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_csv_preview.py", line 109, in test_crlf_preserved
    result = workspace.execute('csv_preview', {'path': 'test.csv', 'limit': 5})
  File "/work/task/harness/autoproteus/tools.py", line 233, in execute
    raise ValueError("Unknown tool: " + str(tool))
ValueError: Unknown tool: csv_preview

test_empty_csv_content (test_csv_preview.CSVPreviewTests.test_empty_csv_content)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_csv_preview.py", line 72, in test_empty_csv_content
    result = workspace.execute('csv_preview', {'path': 'empty.csv', 'limit': 5})
  File "/work/task/harness/autoproteus/tools.py", line 233, in execute
    raise ValueError("Unknown tool: " + str(tool))
ValueError: Unknown tool: csv_preview


```

- `format_json`: 330.32 seconds, 66 actions, status `completed`, category `None`. Independent cases 18/18, candidate-suite exit 0, accepted=True.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=True.

GPU after shutdown: NVIDIA GeForce GTX 1080 Ti, 11264, 1168, 74, 0.

### qwen35-4b-native-64k

Qwen3.5 4B Q4_K_M. Publisher GGUF of Qwen3.5 4B, previously untested here. Same experimental nonthinking 0.6 profile as the Qwen9B/Qwopus screening, not the publisher general-purpose recommended profile.

Context 65536, output 4096, temperature 0.6, thinking False, protocol `native`, cache K/V `q8_0` / `q8_0`.

Weight SHA-256: `13c16f426047e2de38cd075bdade4a7bcbc8c774384876f677740cda65f8a983`.

- Basic `exact-file`: status `completed`, category `task`, artifact checks [{'path': 'greeting.txt', 'passed': False}], format repairs 1.
- `sha256_file`: 191.26 seconds, 46 actions, status `error`, category `context`. Independent cases 11/11, candidate-suite exit 0, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=True.
- `csv_preview`: 102.39 seconds, 52 actions, status `error`, category `context`. Independent cases 0/0, candidate-suite exit None, accepted=False.
  Runtime changed=False, protected files unchanged=True, allowed files only=True, protected regressions=None, public invocation=None.
- `format_json`: 238.78 seconds, 76 actions, status `error`, category `context`. Independent cases 18/18, candidate-suite exit 1, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=True.

```text
{"check": "candidate tests", "passed": false, "tests": 63, "failures": 2, "errors": 0, "skipped": 0}
test_format_json_oversized_input (test_format_json.FormatJSONTests.test_format_json_oversized_input)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_format_json.py", line 145, in test_format_json_oversized_input
    self.assertIn('exceeds 100000', str(ctx.exception))
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'exceeds 100000' not found in 'format_json: input text exceeds 100,000 Unicode characters'

test_format_json_oversized_output (test_format_json.FormatJSONTests.test_format_json_oversized_output)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_format_json.py", line 162, in test_format_json_oversized_output
    self.assertIn('exceeds 100000', str(ctx.exception))
    ~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: 'exceeds 100000' not found in 'format_json: input text exceeds 100,000 Unicode characters'


```


GPU after shutdown: NVIDIA GeForce GTX 1080 Ti, 11264, 1167, 74, 0.

### qwopus-native-64k-nonthinking

Qwopus3.5 9B Coder Q4_K_M. Publisher GGUF; primary screening uses the existing Qwen nonthinking temperature 0.6 profile. Publisher examples use temperature 1 with thinking; that is a separate diagnostic.

Context 65536, output 4096, temperature 0.6, thinking False, protocol `native`, cache K/V `q8_0` / `q8_0`.

Weight SHA-256: `bf7d30e6c973538c422038cb6fce23665f52f444b32c6f44c9b668812515fcb0`.

- `sha256_file`: 255.69 seconds, 29 actions, status `completed`, category `None`. Independent cases 11/11, candidate-suite exit 0, accepted=True.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=True.
- `csv_preview`: 546.67 seconds, 33 actions, status `error`, category `context`. Independent cases 22/27, candidate-suite exit 1, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=False.
  Failing independent cases: {"quoted_1": false, "many_1": false, "many_5": false, "many_20": false, "default_limit": false}.

```text
{"check": "candidate tests", "passed": false, "tests": 70, "failures": 6, "errors": 3, "skipped": 0}
test_limit_truncates_rows_and_sets_truncated (test_csv_preview.CsvPreviewTests.test_limit_truncates_rows_and_sets_truncated)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_csv_preview.py", line 37, in test_limit_truncates_rows_and_sets_truncated
    self.assertEqual(result["truncated"], True)
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: False != True

test_preserves_crlf_inside_quoted_fields (test_csv_preview.CsvPreviewTests.test_preserves_crlf_inside_quoted_fields)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_csv_preview.py", line 79, in test_preserves_crlf_inside_quoted_fields
    self.assertEqual(result["rows"], [["line1\r\nline2", "e", "f"]])
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: Lists differ: [['a', 'b', 'c'], ['line1\r\nline2', 'e', 'f']] != [['line1\r\nline2', 'e', 'f']]

First differing element 0:
['a', 'b', 'c']
['line1\r\nline2', 'e', 'f']

First list contains 1 additional elements.
First extra element 1:
['line1\r\nline2', 'e', 'f']

- [['a', 'b', 'c'], ['line1\r\nline2', 'e', 'f']]
?  -----------------

+ [['line1\r\nline2', 'e', 'f']]

test_preserves_exact_input_bytes (test_csv_preview.CsvPreviewTests.test_preserves_exact_input_bytes)
Traceback (most recent call last):
  File "/work/task/harness/tests/test_csv_preview.py", line 87, in test_preserves_exact_input_bytes
    self.assertEqual(result["rows"], [["1", "2"], ["3", "4"]])
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: Lists differ: [['a', 'b'], ['1', '2'], ['3', '4']] != [['1', '2'], ['3', '4']]

First differing element 0:
['a', 'b']
['1', '2']

First list contains 1 additional elements.
First extra element 2:
['3', '4']

- [['a', 'b'], ['1', '2'], ['3', '4']]
?  ------------

+ [['1', '2'], ['3', '4']]


```

- `format_json`: 445.65 seconds, 128 actions, status `completed`, category `None`. Independent cases 9/18, candidate-suite exit 1, accepted=False.
  Runtime changed=True, protected files unchanged=True, allowed files only=True, protected regressions=True, public invocation=False.
  Failing independent cases: {"object": false, "object_idempotent": false, "array": false, "array_idempotent": false, "scalar": false, "scalar_idempotent": false, "exact_output_limit": false, "preserve_invalid": false, "preserve_expanded": false}.

```text
{"check": "candidate tests", "passed": false, "tests": 50, "failures": 0, "errors": 1, "skipped": 0}
test_format_json (unittest.loader._FailedTest.test_format_json)
ImportError: Failed to import test module: test_format_json
Traceback (most recent call last):
  File "/usr/lib/python3.14/unittest/loader.py", line 433, in _find_test_path
    module = self._get_module_from_name(name)
  File "/usr/lib/python3.14/unittest/loader.py", line 374, in _get_module_from_name
    __import__(name)
    ~~~~~~~~~~^^^^^^
  File "/work/task/harness/tests/test_format_json.py", line 98
    nested = {"a": {"b": {"c": {"d": {"e": "x"}}}}
             ^
SyntaxError: '{' was never closed



```


GPU after shutdown: NVIDIA GeForce GTX 1080 Ti, 11264, 1110, 73, 2.

## Second-pass growth

For each profile with an accepted first pass, the first accepted candidate in the frozen SHA/CSV/JSON order is loaded unchanged into a fresh follow-up VM. The fixed task requires use of its existing tool, a second independently specified tool, preservation of earlier behavior and tests, then activation and actual use of both tools to produce an audit receipt. Development ends requesting activation; verification of the second extension is scored independently of that waiting status. After independent checks, the same task continues with concise activation context and full journals on disk. Functional growth and native invocation are separate scores. No operator candidate repairs are made.

| Follow-up | Second extension verified | Earlier independent behavior checks | Final artifact correct | Functional growth | Direct route success |
| --- | --- | --- | --- | --- | --- |
| qwen35-4b-native-128k-growth | False | True | None | None | None |
| qwopus-native-64k-nonthinking-growth | False | True | None | None | None |
| qwopus-native-64k-nonthinking-growth-128k | False | True | None | None | None |

### qwen35-4b-native-128k-growth

Context: 131072 tokens.
Exact first candidate: `2a079906c7f7e96845a1c4b22895fc1a05a2ce04ccd44a37ad209384f21225c1`. Existing tool `sha256_file`, requested second tool `format_json`.
Development result: {"task": "second-extension-audit", "session": "5e9253ad5f5d4a85b6d88dc220e56fed", "status": "waiting", "execution_mode": "vm", "isolated": true, "passed": false, "checks": [], "steps": 128, "seconds": 493.62, "model_requests": 129, "timed_out": false, "format_repairs": 0, "action_errors": 11, "read_actions": 99, "repeated_reads": 0, "interrupted": false, "failure_kind": null, "detail": "Waiting for your reply"}.
Final result: {}.
Observed final invocation routes: {}.
Verified seed unchanged after final use: None.
Inference costs and completeness: {"calls": 129, "wire_requests": 129, "trace_complete": true, "measurements": {"input_tokens": {"known_sum": 4256937, "measured_calls": 129, "expected_calls": 129, "complete": true, "status": "complete"}, "output_tokens": {"known_sum": 15767, "measured_calls": 129, "expected_calls": 129, "complete": true, "status": "complete"}, "call_seconds": {"known_sum": 454.889, "measured_calls": 129, "expected_calls": 129, "complete": true, "status": "complete"}, "transport_seconds": {"known_sum": 454.857, "measured_calls": 129, "expected_calls": 129, "complete": true, "status": "complete"}}, "trace_read_errors": 0, "finished_calls": 129, "transport_finished_calls": 129, "provider_responses": 129, "statuses": {"returned": 129}, "error_categories": {}, "token_usage_measured_calls": 129, "output_token_usage_measured_calls": 129, "input_tokens": 4256937, "output_tokens": 15767, "call_seconds": 454.889, "transport_seconds": 454.857, "host_history_omissions": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}.
Independent second-tool checks: {"registered": true, "schema": true, "object": false, "object_idempotent": false, "array": false, "array_idempotent": false, "scalar": false, "scalar_idempotent": false, "exact_output_limit": true, "preserve_invalid": true, "preserve_utf8": true, "preserve_large": true, "preserve_expanded": true, "reject_path_directory": true, "reject_path_missing": true, "reject_path_../outside-heldout.txt": true, "reject_path_escape": true, "outside_preserved": true}.
Candidate test-suite exit: 1.

### qwopus-native-64k-nonthinking-growth

Context: 65536 tokens.
Exact first candidate: `9d7cd78603f470657ffd5cab4aff4e14434ef78ebef24e420c175b38d327ee15`. Existing tool `sha256_file`, requested second tool `format_json`.
Development result: {"task": "second-extension-audit", "session": "dfd9a5201b7144f08dcc6a58b9aa23d0", "status": "error", "execution_mode": "vm", "isolated": true, "passed": false, "checks": [], "steps": 29, "seconds": 176.91, "model_requests": 30, "timed_out": false, "format_repairs": 0, "action_errors": 3, "read_actions": 22, "repeated_reads": 0, "interrupted": false, "failure_kind": "context", "detail": "The isolated run stopped"}.
Final result: {}.
Observed final invocation routes: {}.
Verified seed unchanged after final use: None.
Inference costs and completeness: {"calls": 30, "wire_requests": 29, "trace_complete": true, "measurements": {"input_tokens": {"known_sum": 461115, "measured_calls": 29, "expected_calls": 29, "complete": true, "status": "complete"}, "output_tokens": {"known_sum": 4612, "measured_calls": 29, "expected_calls": 29, "complete": true, "status": "complete"}, "call_seconds": {"known_sum": 167.862, "measured_calls": 30, "expected_calls": 30, "complete": true, "status": "complete"}, "transport_seconds": {"known_sum": 167.854, "measured_calls": 30, "expected_calls": 30, "complete": true, "status": "complete"}}, "trace_read_errors": 0, "finished_calls": 30, "transport_finished_calls": 30, "provider_responses": 29, "statuses": {"returned": 29, "error": 1}, "error_categories": {"context": 1}, "token_usage_measured_calls": 29, "output_token_usage_measured_calls": 29, "input_tokens": 461115, "output_tokens": 4612, "call_seconds": 167.862, "transport_seconds": 167.854, "host_history_omissions": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}.
Independent second-tool checks: {"registered": true, "schema": true, "object": false, "object_idempotent": false, "array": false, "array_idempotent": false, "scalar": false, "scalar_idempotent": false, "exact_output_limit": false, "preserve_invalid": false, "preserve_utf8": true, "preserve_large": true, "preserve_expanded": false, "reject_path_directory": true, "reject_path_missing": true, "reject_path_../outside-heldout.txt": true, "reject_path_escape": true, "outside_preserved": true}.
Candidate test-suite exit: 1.

### qwopus-native-64k-nonthinking-growth-128k

Context: 131072 tokens.
Exact first candidate: `9d7cd78603f470657ffd5cab4aff4e14434ef78ebef24e420c175b38d327ee15`. Existing tool `sha256_file`, requested second tool `format_json`.
Development result: {"task": "second-extension-audit", "session": "1ba1b84cfab1495686bde4797883317f", "status": "waiting", "execution_mode": "vm", "isolated": true, "passed": false, "checks": [], "steps": 128, "seconds": 629.97, "model_requests": 129, "timed_out": false, "format_repairs": 0, "action_errors": 18, "read_actions": 83, "repeated_reads": 0, "interrupted": false, "failure_kind": null, "detail": "Waiting for your reply"}.
Final result: {}.
Observed final invocation routes: {}.
Verified seed unchanged after final use: None.
Inference costs and completeness: {"calls": 129, "wire_requests": 129, "trace_complete": true, "measurements": {"input_tokens": {"known_sum": 3668716, "measured_calls": 129, "expected_calls": 129, "complete": true, "status": "complete"}, "output_tokens": {"known_sum": 15379, "measured_calls": 129, "expected_calls": 129, "complete": true, "status": "complete"}, "call_seconds": {"known_sum": 583.551, "measured_calls": 129, "expected_calls": 129, "complete": true, "status": "complete"}, "transport_seconds": {"known_sum": 583.518, "measured_calls": 129, "expected_calls": 129, "complete": true, "status": "complete"}}, "trace_read_errors": 0, "finished_calls": 129, "transport_finished_calls": 129, "provider_responses": 129, "statuses": {"returned": 129}, "error_categories": {}, "token_usage_measured_calls": 129, "output_token_usage_measured_calls": 129, "input_tokens": 3668716, "output_tokens": 15379, "call_seconds": 583.551, "transport_seconds": 583.518, "host_history_omissions": [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]}.
Context diagnostic: Only context changed from 65536 to 131072. Exact same accepted first candidate, task, sampling and grader. Separate from the primary failed follow-up.
Independent second-tool checks: {"registered": true, "schema": true, "object": false, "object_idempotent": false, "array": false, "array_idempotent": false, "scalar": false, "scalar_idempotent": false, "exact_output_limit": true, "preserve_invalid": true, "preserve_utf8": true, "preserve_large": true, "preserve_expanded": true, "reject_path_directory": true, "reject_path_missing": true, "reject_path_../outside-heldout.txt": true, "reject_path_escape": true, "outside_preserved": true}.
Candidate test-suite exit: 1.

The 128K profiles are separately labelled diagnostics added after observing context-limited 64K attempts. They retain the same seed, model, quantization, sampling, output budget, action allowance and graders. The Qwopus diagnostic repeats only the follow-up using its exact accepted SHA candidate. The Qwen3.5 4B diagnostic repeats the fixed basic and first-pass contract batch and runs a follow-up only after full acceptance. No deterministic sampling seed or matched repeat batch was used, so differences cannot be attributed solely to context size.

The complete results, provider traces, journals, candidates, source diffs and independent checks remain under each profile directory. No missing usage measurement is silently treated as zero.

## Model sources

Selection and inference-profile rationale came from the model publishers' cards. These are provenance sources; the capability results above come from the local experiments.

- [Mistral Ministral 3 8B Instruct](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512) and [official GGUF](https://huggingface.co/mistralai/Ministral-3-8B-Instruct-2512-GGUF).
- [Jackrong Qwopus3.5 9B Coder](https://huggingface.co/Jackrong/Qwopus3.5-9B-Coder) and [publisher GGUF](https://huggingface.co/Jackrong/Qwopus3.5-9B-Coder-GGUF).
- [FineEnvs LFM2.5 2.6B multiharness RL](https://huggingface.co/FineEnvs/LFM2.5-2.6B-multiharness-RL). The original saved template's thinking prefix was preserved with a separately pinned bounded-reasoning profile before its first inference call.
- [Microsoft Phi-4-mini-instruct](https://huggingface.co/microsoft/Phi-4-mini-instruct) and [Bartowski GGUF](https://huggingface.co/bartowski/microsoft_Phi-4-mini-instruct-GGUF).
- [Qwen Qwen3.5 4B](https://huggingface.co/Qwen/Qwen3.5-4B) and [Bartowski GGUF](https://huggingface.co/bartowski/Qwen_Qwen3.5-4B-GGUF).

Exact revision, file and SHA-256 receipts are beside the downloaded models. FineEnvs conversion-source and CPU dependency manifests are retained separately. Model repository Python was not executed. The private extra-model preparation initially failed to import its helper in embedded Python; its path was corrected before any of those inference calls. No candidate code was repaired by the operator.
