# Model-authored feature report

Saved verbatim from the isolated candidate. Independent verification is recorded in the round-two findings and results; this report is the model's own account.

# Feature: file_summary Tool

## Summary
Added a new public tool `file_summary(path)` that returns metadata about a UTF-8 file:
- `path`: relative workspace path
- `bytes`: UTF-8 byte count
- `characters`: Unicode character count
- `lines`: len(text.splitlines())
- `words`: len(text.split())

## Changes Made

### 1. `harness/autoproteus/tools.py`
Added `file_summary` tool implementation in `Workspace.execute`:
- Validates path using `self.path` (workspace path validation)
- Reads file with `newline=""` to preserve CRLF
- Rejects files exceeding 100,000 characters (WRITE_LIMIT)
- Rejects invalid UTF-8 with meaningful error message
- Rejects directories and non-existent files
- Returns object with path, bytes, characters, lines, words

### 2. `harness/autoproteus/providers.py`
Added `file_summary` entry to `TOOL_SPECS`:
```python
"file_summary": ("Count bytes, characters, lines and words in a UTF-8 file.", {"path": STRING}, ["path"]),
```

### 3. `harness/tests/test_file_summary.py`
Created new test file with 11 comprehensive tests:
- `test_empty_file_returns_zero_counts`: Empty file returns zeros
- `test_simple_text_counts_correctly`: Basic text counting
- `test_multiline_text_counts_lines_and_words`: Multi-line text
- `test_unicode_text_counts_characters_and_bytes_separately`: Unicode handling
- `test_crlf_line_endings_preserved_and_counted`: CRLF preservation
- `test_mixed_line_endings_counted_correctly`: Mixed line endings
- `test_large_file_rejected`: Files >100,000 chars rejected
- `test_invalid_utf8_rejected`: Invalid UTF-8 rejected
- `test_directory_path_rejected`: Directories rejected
- `test_outside_workspace_path_rejected`: Paths outside workspace rejected
- `test_very_long_words_counted_correctly`: Long words handled correctly
- `test_multiple_spaces_and_tabs_counted_as_words`: Whitespace handling

### 4. `harness/README.md`
Updated documentation to describe the new `file_summary` tool.

## Test Results

All 42 tests pass successfully:
```
Ran 42 tests in 1.405s
OK
```

Test breakdown:
- FileSummaryTests: 11 tests (all passed)
- AgentTests: 10 tests (all passed)
- ProtocolTests: 2 tests (all passed)
- WorkspaceTests: 19 tests (all passed)

## Manual Exercise

The tool was exercised on a real file:
```python
from autoproteus.tools import Workspace
from pathlib import Path

workspace = Workspace(Path('.data/test-real'))
workspace.execute('write_file', {'path': 'sample.txt', 'content': 'Hello world\nThis is a test file.\nIt has multiple lines.'})
result = workspace.execute('file_summary', {'path': 'sample.txt'})
# Result: {'path': 'sample.txt', 'bytes': 55, 'characters': 55, 'lines': 3, 'words': 11}
```

## Notes

- The tool preserves CRLF line endings (both \r and \n are counted as characters)
- Empty files return zeros for all counts
- Files at exactly 100,000 characters are accepted
- Files exceeding 100,000 characters are rejected with "exceeds" error message
- Invalid UTF-8 is rejected with "UTF-8" error message
- Non-existent files are rejected with "exists" error message
- Directories are rejected as files
- Paths outside the workspace are rejected
