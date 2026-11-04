import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from weight_editor_loop_gate import fit_signed_gate,rmsnorm_margin_gradient,norm_budget_alpha
try:import numpy as np
except ImportError:np=None


@unittest.skipIf(np is None,'NumPy only in opt-in research environment')
class GateTests(unittest.TestCase):
    def test_sparse_constraints_and_rank_guard(self):
        rng=np.random.default_rng(42);x=rng.normal(size=(4,80))
        f,j=fit_signed_gate(x,columns=16)
        np.testing.assert_allclose(x@f,[-1,1,-1,1],atol=1e-9)
        self.assertEqual(np.count_nonzero(f),16)
        with self.assertRaises(ValueError):fit_signed_gate(np.ones((4,80)))

    def test_margin_gradient_matches_finite_difference(self):
        h=np.array([.3,-.5,.8,1.1]);n=np.array([1,.7,1.3,.8]);t=np.array([.2,.8,-.1,.4]);c=np.array([.1,-.2,.4,.3]);eps=1e-6
        g=rmsnorm_margin_gradient(h,n,t,c,epsilon=eps)
        def margin(v):return np.dot(n*(t-c),v/np.sqrt(np.mean(v*v)+eps))
        numerical=[]
        for i in range(4):
            d=np.zeros(4);d[i]=1e-6;numerical.append((margin(h+d)-margin(h-d))/(2e-6))
        np.testing.assert_allclose(g,numerical,rtol=1e-6,atol=1e-8)

    def test_actual_rank_one_norm_matches_budget(self):
        f=np.array([1,0,-2,0,.5]);v=np.array([.2,.8,-.3]);w_norm=7.
        for budget in (.01,.03,.06):
            alpha=norm_budget_alpha(w_norm,f,v,budget)
            self.assertAlmostEqual(np.linalg.norm(alpha*np.outer(v,f))/w_norm,budget)
        with self.assertRaises(ValueError):norm_budget_alpha(w_norm,f,v,.5)
