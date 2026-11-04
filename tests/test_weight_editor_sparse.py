import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_editor_sparse import bf16_round,rank_one_columns
try:
    import numpy as np
except ImportError:
    np=None


@unittest.skipIf(np is None,'NumPy is only in the opt-in ML environment')
class SparseTests(unittest.TestCase):
    def test_rank_one_application_and_column_boundary(self):
        w=np.arange(24,dtype=np.float32).reshape(4,6)/16
        f=np.array([0,1,0,-2,0,0],dtype=np.float32);v=np.array([1,2,3,4],dtype=np.float32)
        out,cols=rank_one_columns(w,f,v,.25)
        np.testing.assert_array_equal(cols,[1,3]);np.testing.assert_array_equal(out[:,[0,2,4,5]],w[:,[0,2,4,5]])
        np.testing.assert_array_equal(out[:,cols],bf16_round(w[:,cols]+.25*v[:,None]*f[None,cols]))

    def test_reject_invalid_data_and_non_sparse_inputs(self):
        w=np.ones((2,129),dtype=np.float32)
        for f,v,s in [(np.ones(129),np.ones(2),.25),(np.zeros(129),np.ones(2),.25),
                      (np.ones(3),np.ones(2),.25),(np.r_[1,np.zeros(128)],np.array([np.nan,1]),.25),
                      (np.r_[1,np.zeros(128)],np.ones(2),2)]:
            with self.assertRaises(ValueError):rank_one_columns(w,f,v,s)

    def test_round_even_and_preserve_bf16_values(self):
        x=np.array([1,2,-.5,0],dtype=np.float32)
        np.testing.assert_array_equal(bf16_round(x),x)
        with self.assertRaises(ValueError):bf16_round([float('inf')])
