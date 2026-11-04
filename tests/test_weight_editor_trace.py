import ctypes
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_editor_trace import TraceAPI


@unittest.skipUnless(importlib.util.find_spec('numpy'),'Native diagnostic uses the separate NumPy research environment')
class CallbackBoundary(unittest.TestCase):
    def api(self,rows=1):
        api=TraceAPI.__new__(TraceAPI)
        stored=(ctypes.c_float*3)(1.,2.,3.)
        api.base=SimpleNamespace(ggml_get_name=lambda _:b'ffn_out-0',ggml_nelements=lambda _:3,
            ggml_nrows=lambda _:rows,ggml_nbytes=lambda _:12,ggml_element_size=lambda _:4,
            ggml_is_contiguous=lambda _:True,
            ggml_backend_tensor_get=lambda _,dest,offset,size:ctypes.memmove(dest,stored,size),
            ggml_backend_tensor_set=lambda _,src,offset,size:ctypes.memmove(stored,src,size))
        api.active=True;api.capture=True;api.values={};api.errors=[];api.intervention=None
        api.feature_amplitude=None
        return api,stored

    def test_observation_does_not_change_tensor(self):
        api,stored=self.api()
        self.assertTrue(api._callback(1,True,None));self.assertTrue(api._callback(1,False,None))
        self.assertEqual(list(stored),[1.,2.,3.]);self.assertEqual(api.values['ffn_out-0'].tolist(),[1.,2.,3.])

    def test_transient_intervention_and_original_capture(self):
        api,stored=self.api();api.intervention={'name':'ffn_out-0','kind':'scale','scale':.5}
        self.assertTrue(api._callback(1,False,None));self.assertEqual(list(stored),[.5,1.,1.5])
        self.assertEqual(api.values['ffn_out-0'].tolist(),[1.,2.,3.])

    def test_bad_shape_stops_without_crossing_callback_exception(self):
        api,stored=self.api(rows=2)
        self.assertFalse(api._callback(1,False,None));self.assertTrue(api.errors)
        self.assertEqual(list(stored),[1.,2.,3.])

    def test_feature_add_requires_prior_feature_then_applies_rank_one_output(self):
        api,stored=self.api();api.intervention={'name':'ffn_out-0','kind':'feature_add','feature_name':'ffn_swiglu-0',
            'coefficients':[1.,0.,0.],'direction':[0.,1.,0.],'strength':.5}
        api.base.ggml_get_name=lambda _:b'ffn_swiglu-0'
        self.assertTrue(api._callback(1,False,None));self.assertEqual(api.feature_amplitude,1.)
        api.base.ggml_get_name=lambda _:b'ffn_out-0'
        self.assertTrue(api._callback(1,False,None));self.assertEqual(list(stored),[1.,2.5,3.])

    def test_missing_feature_stops_without_modification(self):
        api,stored=self.api();api.intervention={'name':'ffn_out-0','kind':'feature_add','feature_name':'ffn_swiglu-0',
            'coefficients':[1.,0.,0.],'direction':[0.,1.,0.],'strength':.5}
        self.assertFalse(api._callback(1,False,None));self.assertEqual(list(stored),[1.,2.,3.])


if __name__=='__main__':unittest.main()
