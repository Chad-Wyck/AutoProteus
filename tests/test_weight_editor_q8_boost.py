import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_editor_q8_boost import boost_bytes
try:import numpy as np
except ImportError:np=None


@unittest.skipIf(np is None,'NumPy only in opt-in environment')
class BoostTests(unittest.TestCase):
    def test_only_q8_scales_change(self):
        a=np.arange(68,dtype=np.uint8).reshape(1,68);blocks=a.reshape(-1,34)
        blocks[:,:2]=np.array([1,-.5],dtype='<f2').view(np.uint8).reshape(-1,2);original=a.copy()
        out=boost_bytes(a).reshape(-1,34)
        np.testing.assert_array_equal(out[:,2:],blocks[:,2:]);np.testing.assert_array_equal(a,original)
        np.testing.assert_array_equal(np.ascontiguousarray(out[:,:2]).view('<f2').reshape(-1),np.array([1.1,-.55],dtype='<f2'))

    def test_shape_and_nonfinite_guards(self):
        with self.assertRaises(ValueError):boost_bytes(np.zeros((1,35),dtype=np.uint8))
        a=np.zeros((1,34),dtype=np.uint8);a[0,:2]=np.array([np.nan],dtype='<f2').view(np.uint8)
        with self.assertRaises(ValueError):boost_bytes(a)
