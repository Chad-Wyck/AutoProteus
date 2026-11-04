from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_parallel_diagnostic import compare


class ParallelDiagnosticTests(unittest.TestCase):
    def test_identical_and_small_rounding_pass(self):
        self.assertTrue(compare([0,1,2],[0,1,2])['passed'])
        self.assertTrue(compare([0,1,2],[0.0001,1,2])['passed'])

    def test_same_argmax_does_not_hide_failed_tolerance(self):
        result=compare([0,1,2],[.01,1,2])
        self.assertTrue(result['argmax_equal']);self.assertFalse(result['passed'])
        self.assertEqual(result['max_abs_token'],0)

    def test_swapped_sequence_logits_fail(self):
        self.assertFalse(compare([0,1,2],[2,1,0])['passed'])

    def test_shape_nonfinite_and_scalar_rejected(self):
        for a,b in [([0,1],[0]),([float('nan'),1],[0,1]),([0,1],[0,float('inf')]),(1,1)]:
            with self.assertRaises(ValueError):compare(a,b)
