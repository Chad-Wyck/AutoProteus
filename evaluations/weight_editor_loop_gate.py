"""CPU-only preparation of a sparse, state-gated loop-closing intervention."""
import math
from weight_editor_runtime import require


def fit_signed_gate(activations, *, columns=64):
    """Minimum-norm analytic fit to four development states; not qualification."""
    import numpy as np
    x=np.asarray(activations,dtype=np.float64);y=np.array([-1,1,-1,1],dtype=np.float64)
    require(x.ndim==2 and x.shape[0]==4 and np.isfinite(x).all(),'Four finite early/late states required')
    require(type(columns) is int and 4<=columns<=64 and columns<=x.shape[1],'Sparse column bound')
    selected=np.argsort(-np.abs(x.T@y),kind='stable')[:columns]
    a=x[:,selected];s=np.linalg.svd(a,compute_uv=False)
    require(s[-1]>1e-8 and s[0]/s[-1]<1e6,'Gate fit is rank-deficient/ill-conditioned')
    f=np.zeros(x.shape[1],dtype=np.float64);f[selected]=a.T@np.linalg.solve(a@a.T,y)
    require(np.isfinite(f).all() and np.max(np.abs(x@f-y))<1e-5,'Gate constraints did not reconstruct')
    return f,selected


def rmsnorm_margin_gradient(hidden,norm_weights,target_row,competing_row, *, epsilon):
    """Analytic derivative of a final RMS-normalized token-logit margin."""
    import numpy as np
    h,n,t,c=[np.asarray(x,dtype=np.float64) for x in (hidden,norm_weights,target_row,competing_row)]
    require(h.ndim==1 and len(h)>0 and n.shape==t.shape==c.shape==h.shape,'Gradient width mismatch')
    require(all(np.isfinite(x).all() for x in (h,n,t,c)) and type(epsilon) in (int,float) and math.isfinite(epsilon) and epsilon>0,'Finite gradient inputs required')
    row=n*(t-c);r=np.sqrt(np.mean(h*h)+epsilon)
    g=row/r-h*np.dot(row,h)/(len(h)*r**3)
    require(np.isfinite(g).all() and np.linalg.norm(g)>1e-12,'Degenerate closing direction')
    return g


def norm_budget_alpha(weights_norm,feature,direction,budget):
    import numpy as np
    f=np.asarray(feature,dtype=np.float64);v=np.asarray(direction,dtype=np.float64)
    require(f.ndim==v.ndim==1 and np.isfinite(f).all() and np.isfinite(v).all(),'Finite vectors required')
    require(math.isfinite(weights_norm) and weights_norm>0 and budget in (.01,.03,.06),'Predeclared relative norm budgets only')
    magnitude=float(np.linalg.norm(f)*np.linalg.norm(v));require(magnitude>1e-12,'Empty intervention')
    return float(budget*weights_norm/magnitude)
