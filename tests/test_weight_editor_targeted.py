import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_editor_targeted import decision_cases, q8_column_edit, metrics, paired_losses, probe_rank


class DiagnosticCases(unittest.TestCase):
    def test_splits_and_answers_are_counterbalanced(self):
        rows = decision_cases()
        self.assertEqual(len(rows),36)
        self.assertEqual(len({r['id'] for r in rows}),36)
        self.assertEqual(len({r['rendered_prompt'] for r in rows}),36)
        for split in ('development','confirmation','ordinary'):
            part = [r for r in rows if r['split'] == split]
            self.assertEqual(len(part),12)
            self.assertEqual([sum(r['correct_letter'] == c for r in part) for c in 'ABCD'],[3,3,3,3])
        self.assertTrue(all('heldout-' not in r['rendered_prompt'] for r in rows))

    @unittest.skipUnless(importlib.util.find_spec('numpy'),'Separate NumPy research environment')
    def test_mask_cannot_escape_columns_or_edit_nonfinite_values(self):
        import numpy as np
        matrix = np.ones((3,64),dtype=np.float32)
        changed = q8_column_edit(matrix,[2,31],.5)
        self.assertEqual(changed[:,[2,31]].tolist(),[[.5,.5]]*3)
        self.assertTrue(np.array_equal(matrix[:,[0,1,32,63]],changed[:,[0,1,32,63]]))
        self.assertTrue(np.all(matrix == 1))
        for cols,scale in [([64],.5),([-1],.5),([1,1],.5),([True],.5),([2],1.1),([],.5)]:
            with self.assertRaises(ValueError): q8_column_edit(matrix,cols,scale)
        matrix[0,0] = np.inf
        with self.assertRaises(ValueError): q8_column_edit(matrix,[2],.5)

    @unittest.skipUnless(importlib.util.find_spec('numpy'),'Separate NumPy research environment')
    def test_metric_uses_requested_correct_position(self):
        import numpy as np
        a = metrics(np.array([-10.,3.,1.,2.,-4.]),[1,2,3,4],2)
        self.assertFalse(a['correct']); self.assertEqual(a['chosen_letter'],'A'); self.assertEqual(a['margin'],-1.)

    def test_loss_gate_requires_complete_matched_coverage(self):
        a = [{'id':'a','split':'ordinary','correct':True,'margin':2.}]
        b = [{'id':'a','split':'ordinary','correct':False,'margin':-1.}]
        self.assertEqual(paired_losses(a,b,'ordinary'),['a'])
        with self.assertRaises(ValueError): paired_losses(a,[],'ordinary')
        self.assertGreater(probe_rank(a),probe_rank(b))


if __name__ == '__main__': unittest.main()
