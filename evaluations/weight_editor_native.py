"""Minimal ctypes binding to the exact pinned b10777 Windows x64 llama C API.

    Native sampling is initialized AFTER prefill, so presence history contains
    generated tokens only. No prompt token is accepted by the sampler.
"""
import ctypes as C
import os
from pathlib import Path
from weight_editor_runtime import require


class ModelParams(C.Structure):
    _fields_ = [(n, C.c_void_p) for n in ('dspark_head_source', 'devices', 'tensor_buft_overrides')] + [
        (n, C.c_int32) for n in ('n_gpu_layers', 'split_mode', 'load_mode', 'main_gpu')] + [
        (n, C.c_void_p) for n in ('tensor_split', 'progress_callback', 'progress_callback_user_data', 'kv_overrides')] + [
        (n, C.c_bool) for n in ('vocab_only', 'check_tensors', 'use_extra_bufts', 'no_host', 'no_alloc', 'load_mtp')]


class ContextParams(C.Structure):
    _fields_ = [(n, C.c_uint32) for n in ('n_ctx', 'n_batch', 'n_ubatch', 'n_seq_max', 'n_rs_seq',
        'n_outputs_max', 'n_outputs_max_per_seq')] + [(n, C.c_int32) for n in
        ('n_threads', 'n_threads_batch', 'ctx_type', 'rope_scaling_type', 'pooling_type', 'attention_type', 'flash_attn_type')] + [
        (n, C.c_float) for n in ('rope_freq_base', 'rope_freq_scale', 'yarn_ext_factor', 'yarn_attn_factor', 'yarn_beta_fast', 'yarn_beta_slow')] + [
        ('yarn_orig_ctx', C.c_uint32), ('defrag_thold', C.c_float), ('cb_eval', C.c_void_p), ('cb_eval_user_data', C.c_void_p),
        ('type_k', C.c_int32), ('type_v', C.c_int32), ('path_kv_mean_center', C.c_void_p),
        ('abort_callback', C.c_void_p), ('abort_callback_data', C.c_void_p)] + [(n, C.c_bool) for n in
        ('embeddings', 'offload_kqv', 'no_perf', 'op_offload', 'swa_full', 'kv_unified')] + [
        ('samplers', C.c_void_p), ('n_samplers', C.c_size_t), ('ctx_other', C.c_void_p)]


class Batch(C.Structure):
    _fields_ = [('n_tokens', C.c_int32)] + [(n, C.c_void_p) for n in ('token', 'embd', 'pos', 'n_seq_id', 'seq_id', 'logits')]


class ChainParams(C.Structure):
    _fields_ = [('no_perf', C.c_bool)]


class TokenData(C.Structure):
    _fields_ = [('id', C.c_int32), ('logit', C.c_float), ('p', C.c_float)]


class TokenArray(C.Structure):
    _fields_ = [('data', C.POINTER(TokenData)), ('size', C.c_size_t), ('selected', C.c_int64), ('sorted', C.c_bool)]


class API:
    def __init__(self, engine, initialize=False):
        if os.name != 'nt' or C.sizeof(C.c_void_p) != 8: raise RuntimeError('Pinned ABI requires Windows x64')
        self.engine = Path(engine).resolve()
        self.search = os.add_dll_directory(str(self.engine))
        self.base = C.CDLL(str(self.engine / 'ggml-base.dll'))
        self.registry = C.CDLL(str(self.engine / 'ggml.dll'))
        self.lib = C.CDLL(str(self.engine / 'llama.dll'))
        signatures = {
            'llama_model_default_params': ([], ModelParams), 'llama_context_default_params': ([], ContextParams),
            'llama_sampler_chain_default_params': ([], ChainParams), 'llama_backend_init': ([], None),
            'llama_backend_free': ([], None),
            'llama_model_load_from_file': ([C.c_char_p, ModelParams], C.c_void_p),
            'llama_model_free': ([C.c_void_p], None), 'llama_model_get_vocab': ([C.c_void_p], C.c_void_p),
            'llama_vocab_n_tokens': ([C.c_void_p], C.c_int32),
            'llama_init_from_model': ([C.c_void_p, ContextParams], C.c_void_p), 'llama_free': ([C.c_void_p], None),
            'llama_n_ctx': ([C.c_void_p], C.c_uint32),
            'llama_batch_get_one': ([C.POINTER(C.c_int32), C.c_int32], Batch),
            'llama_decode': ([C.c_void_p, Batch], C.c_int32),
            'llama_tokenize': ([C.c_void_p, C.c_char_p, C.c_int32, C.POINTER(C.c_int32), C.c_int32, C.c_bool, C.c_bool], C.c_int32),
            'llama_sampler_chain_init': ([ChainParams], C.c_void_p),
            'llama_sampler_chain_add': ([C.c_void_p, C.c_void_p], None),
            'llama_sampler_init_penalties': ([C.c_int32, C.c_int32, C.c_float, C.c_float, C.c_float], C.c_void_p),
            'llama_sampler_init_temp': ([C.c_float], C.c_void_p),
            'llama_sampler_init_top_k': ([C.c_int32], C.c_void_p),
            'llama_sampler_init_top_p': ([C.c_float, C.c_size_t], C.c_void_p),
            'llama_sampler_init_dist': ([C.c_uint32], C.c_void_p),
            'llama_sampler_sample': ([C.c_void_p, C.c_void_p, C.c_int32], C.c_int32),
            'llama_sampler_apply': ([C.c_void_p, C.POINTER(TokenArray)], None),
            'llama_sampler_accept': ([C.c_void_p, C.c_int32], None), 'llama_sampler_free': ([C.c_void_p], None)}
        for name, (args, result) in signatures.items():
            function = getattr(self.lib, name); function.argtypes = args; function.restype = result
        require(C.sizeof(ModelParams) == 80 and C.sizeof(ContextParams) == 168 and C.sizeof(Batch) == 56, 'C ABI structure size mismatch')
        model = self.lib.llama_model_default_params(); ctx = self.lib.llama_context_default_params()
        if (not -1 <= model.n_gpu_layers <= 1000 or not 1 <= ctx.n_ctx <= 2**22
                or not 1 <= ctx.n_batch <= 2**20 or ctx.type_k != 1 or ctx.type_v != 1):
            raise RuntimeError('C API default-parameter ABI sanity check failed')
        self.initialized = initialize
        if initialize:
            loader = self.registry.ggml_backend_load_all_from_path
            loader.argtypes = [C.c_char_p]; loader.restype = None
            loader(str(self.engine).encode())
            self.lib.llama_backend_init()
            gpu = self.registry.ggml_backend_dev_by_type
            gpu.argtypes = [C.c_int]; gpu.restype = C.c_void_p
            if not gpu(1): raise RuntimeError('Pinned native CUDA backend unavailable; CPU fallback refused')

    def penalty_control(self):
        sampler = self.lib.llama_sampler_init_penalties(4, 34816, 1., 0., 1.5)
        if not sampler: raise RuntimeError('Penalty sampler missing')
        def apply():
            data = (TokenData * 4)(*(TokenData(i, value, 0.) for i, value in enumerate((2., -1., 0., 1.))))
            view = TokenArray(data, 4, -1, False)
            self.lib.llama_sampler_apply(sampler, C.byref(view))
            return [data[i].logit for i in range(4)]
        try:
            require(apply() == [2., -1., 0., 1.], 'Fresh sampler penalty mismatch')
            for token in (1, 1, 3): self.lib.llama_sampler_accept(sampler, token)
            require(apply() == [2., -2.5, 0., -.5], 'Generated-only penalty mismatch')
            return {'fresh_history_unpenalized': True, 'generated_unique_presence_only': True,
                    'repeat_penalty': 1., 'frequency_penalty': 0., 'presence_penalty': 1.5}
        finally: self.lib.llama_sampler_free(sampler)

    def load(self, path):
        params = self.lib.llama_model_default_params()
        params.n_gpu_layers = -1; params.main_gpu = 0; params.check_tensors = True
        params.load_mtp = False
        model = self.lib.llama_model_load_from_file(str(Path(path).resolve()).encode(), params)
        if not model: raise RuntimeError('Native model load failed')
        return model

    def context(self, model):
        params = self.lib.llama_context_default_params()
        params.n_ctx = 34816; params.n_batch = 128; params.n_ubatch = 64
        params.n_seq_max = 1; params.n_rs_seq = 0
        params.n_threads = 2; params.n_threads_batch = 2
        params.type_k = 1; params.type_v = 1; params.flash_attn_type = 1
        params.offload_kqv = True; params.no_perf = False
        ctx = self.lib.llama_init_from_model(model, params)
        if not ctx: raise RuntimeError('Native context creation failed')
        if self.lib.llama_n_ctx(ctx) < 34816:
            self.lib.llama_free(ctx); raise RuntimeError('Native context below frozen allowance')
        return ctx

    def encode(self, model, text):
        vocab = self.lib.llama_model_get_vocab(model)
        raw = text.encode('utf-8'); array = (C.c_int32 * (len(raw) + 32))()
        count = self.lib.llama_tokenize(vocab, raw, len(raw), array, len(array), False, True)
        if count < 0: raise RuntimeError('Native tokenizer buffer unexpectedly too small')
        return list(array[:count])

    def decode(self, ctx, tokens):
        raw = (C.c_int32 * len(tokens))(*tokens)
        batch = self.lib.llama_batch_get_one(raw, len(tokens))
        result = self.lib.llama_decode(ctx, batch)
        if result != 0: raise RuntimeError(f'Native decode status {result}')

    def sampler(self, model, seed):
        vocab = self.lib.llama_model_get_vocab(model)
        n = self.lib.llama_vocab_n_tokens(vocab)
        params = self.lib.llama_sampler_chain_default_params(); params.no_perf = False
        sampler = self.lib.llama_sampler_chain_init(params)
        if not sampler: raise RuntimeError('Sampler chain allocation failed')
        for child in (self.lib.llama_sampler_init_penalties(n, 34816, 1., 0., 1.5),
            self.lib.llama_sampler_init_temp(.6), self.lib.llama_sampler_init_top_k(20),
            self.lib.llama_sampler_init_top_p(.95, 1), self.lib.llama_sampler_init_dist(seed)):
            if not child: raise RuntimeError('Native sampler initialization failed')
            self.lib.llama_sampler_chain_add(sampler, child)
        return sampler

    def close(self):
        if self.initialized: self.lib.llama_backend_free(); self.initialized = False
        self.search.close()




class BatchAPI(API):
    def __init__(self, engine):
        super().__init__(engine, initialize=True)
        self.lib.llama_get_logits_ith.argtypes = [C.c_void_p, C.c_int32]
        self.lib.llama_get_logits_ith.restype = C.POINTER(C.c_float)
        self.lib.llama_synchronize.argtypes = [C.c_void_p]
        self.lib.llama_n_ctx_seq.argtypes = [C.c_void_p]
        self.lib.llama_n_ctx_seq.restype = C.c_uint32

    def context_slots(self, model, slots):
        require(type(slots) is int and slots in (1, 2), 'Only qualified one/two-slot scored execution is supported')
        p = self.lib.llama_context_default_params()
        p.n_ctx = 34816 * slots; p.n_batch = 128; p.n_ubatch = 64
        p.n_seq_max = slots; p.n_rs_seq = 0
        p.n_threads = p.n_threads_batch = 2
        p.type_k = p.type_v = 1; p.flash_attn_type = 1
        p.offload_kqv = True; p.no_perf = False
        ctx = self.lib.llama_init_from_model(model, p)
        if not ctx: raise RuntimeError('Multi-sequence context creation failed')
        if self.lib.llama_n_ctx_seq(ctx) < 34816:
            self.lib.llama_free(ctx); raise RuntimeError('Context per slot below frozen limit')
        return ctx

    def batch(self, ctx, entries):
        # Own every C buffer through synchronization; one explicit sequence per token.
        n = len(entries)
        tokens = (C.c_int32*n)(*(v[0] for v in entries))
        pos = (C.c_int32*n)(*(v[1] for v in entries))
        counts = (C.c_int32*n)(*([1]*n))
        seqs = [(C.c_int32*1)(v[2]) for v in entries]
        pointers = (C.POINTER(C.c_int32)*n)(*(C.cast(s,C.POINTER(C.c_int32)) for s in seqs))
        logits = (C.c_int8*n)(*(int(v[3]) for v in entries))
        ptr = lambda value: C.cast(value,C.c_void_p)
        b = Batch(n,ptr(tokens),None,ptr(pos),ptr(counts),ptr(pointers),ptr(logits))
        status = self.lib.llama_decode(ctx,b)
        if status: raise RuntimeError('Explicit batch decode failed: '+str(status))
        self.lib.llama_synchronize(ctx)

    def prefill(self,ctx,ids,seq,check=lambda: None):
        for start in range(0,len(ids),128):
            check()
            chunk=ids[start:start+128]
            self.batch(ctx,[(t,start+i,seq,start+i==len(ids)-1) for i,t in enumerate(chunk)])

    def logits(self,ctx,index=-1):
        import numpy as np
        pointer=self.lib.llama_get_logits_ith(ctx,index)
        if not pointer: raise RuntimeError('Expected logits row absent')
        values=np.ctypeslib.as_array(pointer,shape=(248320,)).copy()
        if not np.isfinite(values).all(): raise RuntimeError('Nonfinite logits')
        return values
