"""Pinned native activation inspection for opt-in, gradient-free diagnosis."""
import ctypes as C
import re

from weight_editor_native import BatchAPI
from weight_editor_runtime import require


class TraceAPI(BatchAPI):
    """Read one-token activations; optionally intervene in transient activations."""
    def __init__(self, engine):
        super().__init__(engine)
        for name, args, result in (
            ('ggml_get_name', [C.c_void_p], C.c_char_p),
            ('ggml_nelements', [C.c_void_p], C.c_int64),
            ('ggml_nrows', [C.c_void_p], C.c_int64),
            ('ggml_nbytes', [C.c_void_p], C.c_size_t),
            ('ggml_element_size', [C.c_void_p], C.c_size_t),
            ('ggml_is_contiguous', [C.c_void_p], C.c_bool),
        ):
            fn=getattr(self.base,name);fn.argtypes=args;fn.restype=result
        for name in ('ggml_backend_tensor_get','ggml_backend_tensor_set'):
            fn=getattr(self.base,name);fn.argtypes=[C.c_void_p,C.c_void_p,C.c_size_t,C.c_size_t];fn.restype=None
        self.active=False;self.capture=False;self.intervention=None;self.values={};self.errors=[]
        self.feature_amplitude=None
        callback_type=C.CFUNCTYPE(C.c_bool,C.c_void_p,C.c_bool,C.c_void_p)
        self.callback=callback_type(self._callback)

    def _callback(self,tensor,ask,user_data):
        try:
            if not self.active:
                return False if ask else True
            name=self.base.ggml_get_name(tensor).decode('utf8')
            wanted=bool(self.capture and re.fullmatch(r'(ffn_swiglu|ffn_out|l_out|attn_residual)-\d+|result_norm',name))
            operation=self.intervention if self.intervention and self.intervention['name']==name else None
            feature=bool(self.intervention and self.intervention['kind']=='feature_add'
                         and self.intervention['feature_name']==name)
            if ask:
                return wanted or operation is not None or feature
            if not wanted and operation is None and not feature:
                return True
            import numpy as np
            count=int(self.base.ggml_nelements(tensor));size=int(self.base.ggml_nbytes(tensor))
            require(self.base.ggml_nrows(tensor)==1 and self.base.ggml_is_contiguous(tensor)
                    and self.base.ggml_element_size(tensor)==4 and size==count*4 and 0<count<=9216,
                    'Unexpected activation layout: '+name)
            value=np.empty(count,dtype=np.float32)
            self.base.ggml_backend_tensor_get(tensor,C.c_void_p(value.ctypes.data),0,size)
            require(np.isfinite(value).all(),'Nonfinite captured activation')
            if wanted:
                self.values[name]=value.copy()
            if feature:
                coefficients=np.asarray(self.intervention['coefficients'],dtype=np.float32)
                require(coefficients.shape==value.shape and np.isfinite(coefficients).all(),'Invalid input feature')
                self.feature_amplitude=float(np.dot(value,coefficients))
            if operation:
                if operation['kind']=='scale':
                    value*=float(operation['scale'])
                elif operation['kind']=='project':
                    direction=np.asarray(operation['direction'],dtype=np.float32)
                    require(direction.shape==value.shape,'Direction width mismatch')
                    value-=float(operation['strength'])*np.dot(value,direction)*direction
                elif operation['kind']=='columns':
                    columns=operation['columns']
                    require(value.shape==(9216,) and type(columns) is list and 1<=len(columns)<=16
                        and len(set(columns))==len(columns) and all(type(i) is int and 0<=i<9216 for i in columns)
                        and operation['scale']==.5,'Invalid bounded column attenuation')
                    value[columns]*=.5
                elif operation['kind']=='feature_add':
                    direction=np.asarray(operation['direction'],dtype=np.float32)
                    require(self.feature_amplitude is not None and direction.shape==value.shape
                            and np.isfinite(direction).all(),'Feature was not captured before FFN output')
                    value+=float(operation['strength'])*self.feature_amplitude*direction
                else:
                    raise ValueError('Unknown transient intervention')
                self.base.ggml_backend_tensor_set(tensor,C.c_void_p(value.ctypes.data),0,size)
            return True
        except BaseException as error:
            self.errors.append(type(error).__name__+': '+str(error))
            return False

    def trace_context(self,model,*,hook=True):
        p=self.lib.llama_context_default_params()
        p.n_ctx=34816;p.n_batch=128;p.n_ubatch=64;p.n_seq_max=1;p.n_rs_seq=0
        p.n_threads=p.n_threads_batch=2;p.type_k=p.type_v=1;p.flash_attn_type=1
        p.offload_kqv=True;p.no_perf=False
        if hook:
            p.cb_eval=C.cast(self.callback,C.c_void_p);p.cb_eval_user_data=None
        ctx=self.lib.llama_init_from_model(model,p)
        require(bool(ctx),'Trace context allocation failed')
        return ctx

    def forward(self,model,ids,deadline,*,capture=False,intervention=None,hook=True):
        self.active=False;self.capture=capture;self.intervention=intervention;self.values={};self.errors=[];self.feature_amplitude=None
        ctx=None
        try:
            deadline.remaining();ctx=self.trace_context(model,hook=hook)
            if len(ids)>1:self.prefill(ctx,ids[:-1],0,check=deadline.remaining)
            self.active=hook
            self.batch(ctx,[(ids[-1],len(ids)-1,0,True)])
            require(not self.errors,'Native callback failure: '+'; '.join(self.errors))
            logits=self.logits(ctx)
            return logits,{k:v.copy() for k,v in self.values.items()}
        finally:
            self.active=False
            if ctx:self.lib.llama_free(ctx)
