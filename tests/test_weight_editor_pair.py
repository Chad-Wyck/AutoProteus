import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_editor_pair import proposal,distinct_paths


class PairedControls(unittest.TestCase):
    def test_numeric_interface_and_fence(self):
        value=proposal('```json\n{"layers":[{"layer":2,"scale":0.8}]}\n```',24)
        self.assertEqual(value,[{'layer':2,'scale':.8}])
        self.assertIsNone(proposal('{"stop":true}',24))

    def test_invalid_coordinates_or_no_op(self):
        for raw in ['{"layers":[{"layer":24,"scale":0.8}]}','{"layers":[{"layer":true,"scale":0.8}]}',
                    '{"layers":[{"layer":2,"scale":1}]}','{"layers":[{"layer":2,"scale":0.8},{"layer":2,"scale":1.2}]}',
                    '{"layers":[{"layer":2,"scale":0.8,"code":"x"}]}']:
            with self.assertRaises(ValueError):proposal(raw,24)

    def test_windows_case_collision(self):
        with self.assertRaises(ValueError):distinct_paths(['confirmation.json','CONFIRMATION.json'])
        distinct_paths(['confirmation-input.json','confirmation-result.json'])


if __name__=='__main__':unittest.main()
