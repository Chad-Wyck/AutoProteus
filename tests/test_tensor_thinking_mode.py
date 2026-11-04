"""Mode-specific cell parsing; no generated closing tag required in nonthinking mode."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_study import code_cell


class ThinkingParserControls(unittest.TestCase):
    def test_enabled_keeps_closing_tag_requirement(self):
        with self.assertRaises(ValueError):code_cell('```python\nprint(1)\n```',thinking_enabled=True)
        self.assertEqual(code_cell('reason</think>\n```python\nprint(1)\n```',thinking_enabled=True)[0],'print(1)\n')

    def test_disabled_accepts_direct_code_without_generated_tag(self):
        self.assertEqual(code_cell('```python\nprint(1)\n```<|im_end|>',thinking_enabled=False)[0],'print(1)\n')

    def test_disabled_handles_optional_wrapper_and_literal_tag(self):
        self.assertEqual(code_cell('<think>optional</think>\n```python\nprint(1)\n```',thinking_enabled=False)[0],'print(1)\n')
        code='print("</think>")\n'
        self.assertEqual(code_cell('```python\n'+code+'```',thinking_enabled=False)[0],code)

    def test_disabled_rejects_unclosed_wrapper_and_multiple_cells(self):
        for text in ('<think>unfinished\n```python\nprint(1)\n```','```python\nprint(1)\n```\n```python\nprint(2)\n```'):
            with self.assertRaises(ValueError):code_cell(text,thinking_enabled=False)
