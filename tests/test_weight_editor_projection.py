import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_editor_projection import proposal,project_columns
try:import numpy as np
except ImportError:np=None


class ProposalTests(unittest.TestCase):
    def test_valid_and_stop(self):
        self.assertEqual(proposal('{"layers":[{"layer":3,"strength":0.5,"columns":32}]}',24),[{'layer':3,'strength':.5,'columns':32}])
        self.assertIsNone(proposal('{"stop":true}',24))

    def test_scope_and_shape(self):
        for text in ['{"layers":[{"layer":24,"strength":0.5,"columns":32}]}',
                     '{"layers":[{"layer":3,"strength":-1,"columns":32}]}',
                     '{"layers":[{"layer":3,"strength":0.5,"columns":1024}]}',
                     '{"layers":[{"layer":3,"strength":0.5,"columns":32,"code":"bad"}]}']:
            with self.assertRaises(ValueError):proposal(text,24)


@unittest.skipIf(np is None,'NumPy only in optional ML environment')
class ProjectionTests(unittest.TestCase):
    def test_project_selected_only(self):
        w=np.array([[2,3,4],[1,2,3]],dtype=np.float32);v=np.array([1,0],dtype=np.float32)
        out=project_columns(w,v,[1],1)
        np.testing.assert_array_equal(out,np.array([[2,0,4],[1,2,3]],dtype=np.float32))

    def test_direction_and_index_guards(self):
        w=np.ones((2,4),dtype=np.float32)
        for v,j in [(np.array([2,0]),[1]),(np.array([1,0]),[-1]),(np.array([1,0]),[1,1])]:
            with self.assertRaises(ValueError):project_columns(w,v,j,.5)
