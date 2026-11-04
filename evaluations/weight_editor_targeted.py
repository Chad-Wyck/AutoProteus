"""Opt-in, gradient-free diagnosis of candidate retention and finishing.

This host-owned research program never executes model-written Python. The
subsequent editing experiment uses the existing diskless tensor workspace.
Importing this module does not initialize inference or read model weights.
"""
import copy
import ctypes as C
import json
import os
from pathlib import Path
import random
import shutil
import struct
import sys
import time

from lora6k_state import atomic, read, sha, identity, exclusive
from weight_editor_runtime import Deadline, TokenBudget, require, check_files, verify_unchanged_bytes


def decision_cases():
    """Distinct scenario values by split; counterbalanced A/B/C/D positions.

    Labels qualify explicit decisions, not mechanistic understanding. No target
    held-out problem or published repair enters this diagnostic.
    """
    rows = []
    for split, start in [('development', 1), ('confirmation', 101), ('ordinary', 201)]:
        for index in range(12):
            family = index % 4
            n = start + index
            if split == 'ordinary':
                specs = [
                    (f'The array is [{n}, {n+1}, {n+2}]. Which expression returns its final element?',
                     'array[-1]', ['array[0]', 'array[len(array)]', 'array[-2]']),
                    (f'A dictionary has keys "k{n}" and "k{n+1}". How many keys are present?',
                     '2', ['1', '0', '3']),
                    (f'The input file must stay unchanged. You need only inspect its length. What operation fits?',
                     'Read the file without writing it', ['Overwrite it with its length', 'Delete it', 'Append a length record']),
                    (f'A 2 by 3 matrix is multiplied by a 3 by 4 matrix. What is the resulting shape?',
                     '2 by 4', ['3 by 3', '4 by 2', '2 by 3']),
                ]
            else:
                # Opposite cases prevent a generic submit/undo preference from
                # satisfying every item. Numerical receipts, not prose, govern.
                if index < 4:
                    specs = [
                        (f'Baseline solved 0/3. Saved candidate r{n} solved 2/3. Later candidate r{n+1} solved 0/3. Both preserve two ordinary checks. No tests remain. Which final candidate is supported?',
                         f'Restore and submit tested r{n}', [f'Submit r{n+1} because it is newer', 'Erase all improvements and submit baseline', 'Invent and submit an untested edit']),
                        (f'Current revision r{n+1} has a new edit. The last generated test belongs to r{n}. One test remains. What establishes current task correctness?',
                         f'Generate and check answers using r{n+1}', [f'Quote the passing result for r{n}', 'Inspect next-token logits only', 'Submit because saving succeeded']),
                        (f'All eight forward calls are consumed. A saved, tested r{n} improves practice and retains every baseline-correct case. No further change is needed. What should happen next?',
                         f'Submit tested r{n} without changing weights', ['Call test_candidate again despite exhaustion', 'Make an untestable noise edit before submitting', 'Read tensors forever instead of finishing']),
                        ('An attention tensor has a negative mean. No causal intervention or task check has been run. What can be concluded?',
                         'Its mean alone does not establish a defect or useful repair', ['Negative weights prove instability', 'Zeroing its mean is a proven repair', 'Absolute values must improve accuracy']),
                    ]
                elif index < 8:
                    specs = [
                        (f'Baseline solved 2/3. Candidate r{n} solved 1/3 and lost a baseline-correct case. No better candidate or test allowance remains. What is supported?',
                         'Restore the immutable baseline and report no improvement', [f'Submit r{n} as an improvement', 'Claim fewer tokens proves correctness', 'Invent an untested repair']),
                        (f'Current revision r{n} was tested successfully. No weights have changed afterward. The task is complete. Which action is needed?',
                         f'Submit current tested r{n}', ['Reinspect the registration file indefinitely', 'Change weights so another test becomes necessary', 'Claim its test belongs to a different revision']),
                        (f'Candidate r{n} solves 0/2, including an output cutoff. There are three tests left. A baseline-correct case was lost. What is the next justified step?',
                         'Revert the failed change before investigating another measured candidate', ['Submit the failed candidate as correct', 'Treat the cutoff as a correct answer', 'Repeat the identical test without changing anything or justification']),
                        ('A model answered one practice problem after five tensor entries changed. There are no other independent measurements. Which claim is supported?',
                         'One practice success; general improvement remains unverified', ['All math ability is repaired', 'The five entries are proven universal reasoning neurons', 'The model can now recursively improve itself']),
                    ]
                else:
                    specs = [
                        (f'Candidate r{n} is measured correct on 3/3 versus baseline 1/3 and keeps that baseline success. Candidate r{n+1} has never generated answers. Which should be kept?',
                         f'Keep tested r{n} and discard the untested change', [f'Prefer r{n+1} because its explanation sounds good', 'Declare both candidates verified', 'Discard every measured success']),
                        (f'The receipt says candidate revision r{n} was used. A cached original-baseline answer is also displayed. Which result measures the edited weights?',
                         f'The candidate result bound to r{n}', ['The cached original result', 'Any answer in the conversation regardless of source', 'The edit-save acknowledgment alone']),
                        (f'Both previous candidates failed. There are no tests remaining and no independently verified improvement. What final report is accurate?',
                         'Report no verified improvement and retain the original as fallback', ['Report success because editing occurred', 'Call a ninth test after an eight-call cap', 'Claim a logit increase proves task completion']),
                        ('A trial emits fewer tokens but all answers become incorrect. What does this establish?',
                         'Lower measured token use without successful task completion', ['An efficiency improvement among correct answers', 'Verified improved reasoning', 'Preserved capability']),
                    ]
            question, correct, wrong = specs[family]
            question = f'Case {n}. ' + question
            correct_position = index % 4
            # Different permutations within every four-item block.
            correct_position = (correct_position + index // 4) % 4
            options = list(wrong)
            options.insert(correct_position, correct)
            letter = 'ABCD'[correct_position]
            prompt = ('<|im_start|>system\nYou are AutoProteus. Read the evidence and choose the best supported option. '
                      'Answer with only its uppercase letter, A, B, C, or D.<|im_end|>\n<|im_start|>user\n' + question + '\n' +
                      '\n'.join(f'{label}. {text}' for label, text in zip('ABCD', options)) +
                      '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n')
            rows.append({'id':split+'-'+str(index), 'split':split, 'family':family,
                         'rendered_prompt':prompt, 'correct_letter':letter})
    return rows


def metrics(logits, choice_ids, correct):
    import numpy as np
    x = np.asarray(logits)[choice_ids].astype(np.float64)
    p = np.exp(x-x.max()); p /= p.sum()
    others = [i for i in range(4) if i != correct]
    return {'correct':int(x.argmax()) == correct, 'chosen_letter':'ABCD'[int(x.argmax())],
            'margin':float(x[correct]-x[others].max()), 'correct_probability_among_choices':float(p[correct]),
            'choice_logits':x.tolist()}


def summarize(rows):
    return {split:{'correct':sum(r['correct'] for r in rows if r['split'] == split),
                   'count':sum(r['split'] == split for r in rows),
                   'mean_margin':sum(r['margin'] for r in rows if r['split'] == split) /
                   max(1,sum(r['split'] == split for r in rows))}
            for split in sorted({r['split'] for r in rows})}


def q8_column_edit(canonical, columns, scale):
    """Sparse canonical BF16 edit; quantization neighbors are checked by caller."""
    import numpy as np
    from weight_editor_sparse import bf16_round
    w = np.asarray(canonical, dtype=np.float32)
    require(w.ndim == 2 and w.shape[1] >= 64 and np.isfinite(w).all(), 'Invalid canonical matrix')
    require(isinstance(columns,list) and 1 <= len(columns) <= 64 and len(set(columns)) == len(columns)
            and all(type(i) is int and 0 <= i < w.shape[1] for i in columns), 'Invalid sparse column mask')
    require(type(scale) in (float,int) and scale in (0., .5), 'Only frozen attenuation doses')
    result = w.copy(); result[:,columns] = bf16_round(result[:,columns]*np.float32(scale))
    return result


def build_candidate(plan, proposal, folder, deadline):
    import numpy as np
    folder = Path(folder); require(not folder.exists(), 'Never overwrite a candidate')
    layer, columns, scale = proposal['layer'], proposal['columns'], proposal['scale']
    require(type(layer) is int and 0 <= layer < 32, 'Invalid 4B layer')
    check_files(plan['cpu_vendor_sources']['path'],plan['cpu_vendor_sources']['files'])
    sys.path.insert(0,plan['cpu_vendor_sources']['path'])
    from gguf import GGUFReader, GGMLQuantizationType
    from gguf.quants import quantize
    base = plan['models']['unchanged']; require(sha(base['path']) == base['sha256'], 'Immutable 4B changed')
    hf = Path(plan['tokenizers']['editor_tokenizer']['path'])
    key = f'model.language_model.layers.{layer}.mlp.down_proj.weight'
    source = hf / read(hf/'model.safetensors.index.json')['weight_map'][key]
    require(sha(source) == plan['canonical_shards'][source.name], 'Canonical shard changed')
    with source.open('rb') as stream:
        n = struct.unpack('<Q',stream.read(8))[0]; info = json.loads(stream.read(n))[key]
    require(info['dtype'] == 'BF16' and info['shape'] == [2560,9216], 'Canonical tensor shape/type mismatch')
    raw = np.memmap(source,dtype='<u2',mode='r',offset=8+n+info['data_offsets'][0],shape=(2560,9216))
    original = (raw.astype(np.uint32)<<16).view(np.float32)
    edited = q8_column_edit(original,columns,scale)
    reader = GGUFReader(base['path']); t = next(t for t in reader.tensors if t.name == f'blk.{layer}.ffn_down.weight')
    require(t.tensor_type == GGMLQuantizationType.Q8_0, 'Not Q8_0')
    encoded_base = quantize(original,GGMLQuantizationType.Q8_0)
    require(np.array_equal(encoded_base,t.data), 'Canonical quantization does not reconstruct deployed base')
    encoded = quantize(edited,GGMLQuantizationType.Q8_0)
    a,b = encoded_base.reshape(2560,-1,34), encoded.reshape(2560,-1,34)
    allowed = {c//32 for c in columns}; forbidden = [i for i in range(288) if i not in allowed]
    require(np.array_equal(a[:,forbidden],b[:,forbidden]), 'Edit escaped selected quantization blocks')
    require(not np.array_equal(a,b), 'Edit disappeared during Q8 quantization')
    deadline.remaining(); require(shutil.disk_usage(folder.parent).free >= 20*2**30, 'Disk floor')
    folder.mkdir(); output = folder/'model-q8.gguf'; shutil.copyfile(base['path'],output)
    target = np.memmap(output,dtype=np.uint8,mode='r+',offset=t.data_offset,shape=encoded.shape)
    target[:] = encoded; target.flush(); del target
    check = verify_unchanged_bytes(base['path'],output,[(int(t.data_offset),int(encoded.nbytes))],deadline)
    blocks = np.flatnonzero(np.any(a.reshape(-1,34) != b.reshape(-1,34),axis=1))
    np.savez_compressed(folder/'numeric-patch.npz', columns=np.array(columns,dtype='<u4'),
                        canonical_bf16=(edited[:,columns].view(np.uint32)>>16).astype('<u2'),
                        q8_block_ids=blocks,q8_new_blocks=b.reshape(-1,34)[blocks])
    rebuilt = a.reshape(-1,34).copy()
    with np.load(folder/'numeric-patch.npz',allow_pickle=False) as patch:
        rebuilt[patch['q8_block_ids']] = patch['q8_new_blocks']
    require(np.array_equal(rebuilt.reshape(encoded.shape),encoded), 'Patch reconstruction failed')
    actual = next(t for t in GGUFReader(output).tensors if t.name == f'blk.{layer}.ffn_down.weight')
    require(np.array_equal(actual.data,encoded), 'Saved artifact differs from patch')
    model = {'path':str(output),'sha256':sha(output)}
    atomic(folder/'MANIFEST.json',{'model':model,'base':base,'proposal':proposal,'canonical_shard_sha256':sha(source),
        'authorship':'Codex-authored sparse attenuation selected by frozen development-only causal probes',
        'canonical_changed_entries':int(np.count_nonzero(original != edited)), 'changed_q8_blocks':len(blocks),
        'q8_block_neighbor_effects_possible':True,'byte_comparison':check,'patch_roundtrip_exact':True,
        'relative_canonical_delta_norm':float(np.linalg.norm(edited-original)/np.linalg.norm(original)),
        'general_improvement_unproven':True})
    return model


def worker(arguments):
    request_path,root,folder,token,end = arguments
    root,folder,request_path = map(Path,(root,folder,request_path)); deadline = Deadline(end=float(end))
    plan = read(root/'manifest.json'); require(identity(plan) == (root/'manifest.sha256').read_text().strip(), 'Plan changed')
    check_files(root/'code',plan['code']); check_files(plan['engine'],plan['engine_files'])
    require(read(root/'GPU-AUTHORIZATION.json') == {'manifest_sha256':identity(plan),'explicit_user_authorization':True}, 'Missing authorization')
    require(request_path.resolve().is_relative_to((root/'requests').resolve()), 'Request outside owned directory')
    r = read(request_path); require(read(root/'active-request.json')['sha256'] == sha(request_path), 'Request binding changed')
    require(sha(r['model']['path']) == r['model']['sha256'], 'Model changed')
    check_files(plan['tokenizers']['editor_tokenizer']['path'],plan['tokenizers']['editor_tokenizer']['files'])
    require(r['mode'] in ('choices','retention','replay'), 'Unknown diagnostic mode')
    budget = TokenBudget(folder,r.get('remaining_tokens',0),{'nonce':token,'request_sha256':sha(request_path)})
    progress = {'token':token,'pid':os.getpid(),'gpu_loaded':False,'request_deadlines':{}}
    def event(kind,**kw):
        progress.update(event=kind,**kw); atomic(folder/'progress.json',progress)
    api = model = None; result = {'status':'failed','token':token,'request_sha256':sha(request_path),'cleanup_complete':False}
    try:
        import numpy as np
        from tokenizers import Tokenizer
        from weight_editor_trace import TraceAPI
        from weight_editor_native import BatchAPI
        class SelectiveTrace(TraceAPI):
            def _callback(self,tensor,ask,user_data):
                op = self.intervention
                if not self.active or not op or op['kind'] != 'columns':
                    return super()._callback(tensor,ask,user_data)
                name = self.base.ggml_get_name(tensor).decode('utf8')
                if name != op['name']:
                    return super()._callback(tensor,ask,user_data)
                if ask: return True
                try:
                    require(self.base.ggml_nrows(tensor) == 1 and self.base.ggml_is_contiguous(tensor)
                        and self.base.ggml_element_size(tensor) == 4 and self.base.ggml_nelements(tensor) == 9216
                        and self.base.ggml_nbytes(tensor) == 9216*4, 'Selective callback layout mismatch')
                    value = np.empty(9216,dtype=np.float32)
                    self.base.ggml_backend_tensor_get(tensor,C.c_void_p(value.ctypes.data),0,value.nbytes)
                    require(np.isfinite(value).all(), 'Nonfinite activation')
                    if self.capture: self.values[name] = value.copy()
                    value[op['columns']] *= np.float32(op['scale'])
                    self.base.ggml_backend_tensor_set(tensor,C.c_void_p(value.ctypes.data),0,value.nbytes)
                    return True
                except BaseException as error:
                    self.errors.append(type(error).__name__+': '+str(error)); return False
        event('loading'); api = SelectiveTrace(plan['engine']) if r['mode'] == 'choices' else BatchAPI(plan['engine'])
        model = api.load(r['model']['path']); progress['gpu_loaded'] = True
        tokenizer = Tokenizer.from_file(str(Path(plan['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
        if r['mode'] == 'choices':
            choice_ids = [tokenizer.encode(c,add_special_tokens=False).ids for c in 'ABCD']
            require(all(len(ids) == 1 for ids in choice_ids), 'Choices must each be a single token')
            choice_ids = [ids[0] for ids in choice_ids]; rows = []
            for trial in r['trials']:
                op = trial.get('intervention')
                require(op is None or (op['kind'] == 'scale' and op['scale'] == .5 and op['name'].startswith('ffn_out-'))
                        or (op['kind'] == 'columns' and 1 <= len(op['columns']) <= 64 and op['scale'] in (0.,.5)
                            and op['name'].startswith('ffn_swiglu-')), 'Unfrozen intervention')
                for case in trial['cases']:
                    ids = tokenizer.encode(case['rendered_prompt'],add_special_tokens=False).ids
                    require(api.encode(model,case['rendered_prompt']) == ids and 0 < len(ids) <= 4096, 'Input mismatch/limit')
                    name = trial['id']+'-'+case['id']; event('probe',case_id=name,request_deadlines={name:min(deadline.end,time.monotonic()+120)})
                    logits,values = api.forward(model,ids,deadline.child(120),capture=trial.get('capture',False),intervention=op)
                    row = {'id':case['id'],'trial':trial['id'],'split':case['split'],**metrics(logits,choice_ids,'ABCD'.index(case['correct_letter']))}
                    if trial.get('capture'):
                        np.savez_compressed(folder/(name+'.npz'),logits=logits,**values)
                        row['activations_file'] = str(folder/(name+'.npz'))
                    rows.append(row); atomic(folder/'observations.json',rows)
            result['observations'] = rows
        else:
            import weight_editor_worker as generation
            retention = r['mode'] == 'retention'
            if retention: require(api.penalty_control()['generated_unique_presence_only'], 'Math sampler control failed')
            else:
                def sampler(native,seed):
                    p = native.lib.llama_sampler_chain_default_params(); chain = native.lib.llama_sampler_chain_init(p)
                    require(bool(chain), 'Sampler allocation failed')
                    for child in (native.lib.llama_sampler_init_temp(.6),native.lib.llama_sampler_init_top_k(20),
                                  native.lib.llama_sampler_init_top_p(.95,1),native.lib.llama_sampler_init_dist(seed)):
                        require(bool(child), 'Sampler child failed'); native.lib.llama_sampler_chain_add(chain,child)
                    return chain
                generation.editor_sampler = sampler
            result['responses'] = generation.generate(api,model,{'kind':'target' if retention else 'editor','cases':r['cases'],'slots':2 if retention else 1,
                'output_tokens':32768 if retention else 8192,'request_seconds':1800 if retention else 600,
                'stop_token_ids':[248044,248046]},folder,tokenizer,budget,deadline,event)
        budget.settle(); result.update(status='completed',generated_tokens=budget.state['emitted'])
    finally:
        try:
            if model: api.lib.llama_model_free(model)
            if api: api.close()
            budget.close(); result['cleanup_complete'] = True
        finally:
            progress['gpu_loaded'] = False; event('closed',request_deadlines={}); atomic(folder/'RESULT.json',result)


def prepare(project,root):
    project,root = Path(project).resolve(),Path(root).resolve()
    require(not root.exists(), 'Never overwrite diagnostic publication')
    prior = project/'.data/tensor-workspace-clarity-pair-20261103'; old = read(prior/'manifest.json')
    require(read(prior/'RESULT.json')['status'] == 'completed' and read(prior/'CLOSED-REPORT.json')['all_owned_native_workers_closed'], 'Prior study not closed')
    root.mkdir(); (root/'code').mkdir(); (root/'requests').mkdir(); (root/'runs').mkdir(); (root/'artifacts').mkdir()
    for name in old['code']:
        shutil.copyfile(prior/'code'/name,root/'code'/name)
    shutil.copyfile(project/'evaluations/weight_editor_targeted.py',root/'code/weight_editor_targeted.py')
    shutil.copyfile(project/'evaluations/weight_editor_loop_gate.py',root/'code/weight_editor_loop_gate.py')
    plan = copy.deepcopy(old); plan.pop('predecessor_completion',None); plan.pop('baseline_import',None)
    plan.update(scope='Targeted 4B decision diagnosis and manual sparse attenuation, followed by matched original-0.8B editing',
        code={p.name:sha(p) for p in (root/'code').iterdir()},data={},
        canonical_shards={'model.safetensors-00001-of-00002.safetensors':'26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61',
                          'model.safetensors-00002-of-00002.safetensors':'cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188'},
        diagnostic_design={'development':12,'confirmation':12,'ordinary':12,'layers':list(range(16,32)),
            'whole_ffn_transient_dose':.5,'selected_layers':2,'column_counts':[16,64],'column_doses':[.5,0.],
            'ranking':'Development causal half-FFN margin change first; then local logit-margin attribution of down-projection columns; no semantic neuron claims',
            'selection':'Development correct count, then minimum margin, then mean margin; one candidate, one equal-size shuffled control',
            'confirmation_not_used_to_select':True,'no_gradients_or_optimizer_training':True,'no_weight_update_fitting':True,
            'editor_comparison':'One edited arm, same exact prior cases/interface/seeds/limits, with old unchanged arm and original-target controls reused and pinned',
            'downstream_admission':'Actual Q8 ordinary decision checks lose zero baseline-correct items and four existing correct math cases are retained; decision gains exploratory',
            'total_seconds':21600,'diagnostic_seconds':3600,'maximum_full_q8_candidates':2,
            'saved_context_replay_turns':[5,12,28,44],
            'replay_policy':'Exact unchanged-editor prompts/seeds and saved original replies; candidate-only generation, inert review, no code execution or candidate selection',
            'no_repeats_or_hidden_feedback':True})
    cases = decision_cases(); atomic(root/'decision-inputs.json',cases); plan['data']['decision-inputs.json'] = sha(root/'decision-inputs.json')
    plan['reference'] = {'root':str(prior),'manifest_sha256':identity(old),'files':{name:sha(prior/name) for name in
        ('manifest.json','RESULT.json','CLOSED-REPORT.json','inputs.json','hidden-golds.json','independent-results.json','baseline-results.json','unchanged/FROZEN.json')}}
    retention = project/'.data/manual4b-math-retention-20261103'
    plan['retention_reference'] = {'root':str(retention),'files':{name:sha(retention/name) for name in
        ('cases-input.json','golds-private.json','control-request.json','control/RESULT.json','control/CLOSED.json','control/usage.json','control/tokens.jsonl','FINAL.json')}}
    atomic(root/'manifest.json',plan); (root/'manifest.sha256').write_text(identity(plan))
    atomic(root/'GPU-AUTHORIZATION.json',{'manifest_sha256':identity(plan),'explicit_user_authorization':False})
    return {'root':str(root),'plan_sha256':identity(plan),'cases':len(cases)}


def probe_rank(rows):
    require(bool(rows), 'Empty causal selection')
    return (sum(r['correct'] for r in rows), min(r['margin'] for r in rows),
            sum(r['margin'] for r in rows)/len(rows))


def paired_losses(before,after,split):
    a = {r['id']:r for r in before if r['split'] == split}
    b = {r['id']:r for r in after if r['split'] == split}
    require(set(a) == set(b), 'Mismatched diagnostic coverage')
    return sorted(i for i,r in a.items() if r['correct'] and not b[i]['correct'])


def publish_comparison(plan,model,folder):
    """Reuse exact old original controls and unchanged editor observations.

    Only the manually edited arm is run. Verify source closure and raw usage,
    rather than treating a printed summary as sufficient control evidence.
    """
    from weight_editor_runtime import usage
    prior = Path(plan['reference']['root']); old = read(prior/'manifest.json')
    require(identity(old) == plan['reference']['manifest_sha256'], 'Reference plan changed')
    check_files(prior,plan['reference']['files']); check_files(prior/'code',old['code'])
    control_files = dict(plan['reference']['files']); calls = []
    for request_path in sorted((prior/'requests').glob('*.json')):
        request = read(request_path)
        if request['mode'] != 'editor' or request['study_context']['editor_arm'] != 'unchanged': continue
        run = prior/'runs'/request_path.stem
        closed,result,ledger = (read(run/n) for n in ('CLOSED.json','RESULT.json','usage.json'))
        require(closed['status'] == result['status'] == 'completed' and closed['owned_worker_closed']
                and not closed['guard'] and result['cleanup_complete'], 'Unclosed unchanged-editor inference')
        require(result['request_sha256'] == sha(request_path) == ledger['binding']['request_sha256']
                and result['token'] == closed['token'] == ledger['binding']['nonce'], 'Unchanged request binding mismatch')
        measured = usage(run,ledger['binding']); require(measured['measurement_complete'], 'Partial unchanged usage')
        require(request['model'] == old['models']['unchanged'], 'Unchanged model mismatch')
        paths = [request_path,run/'CLOSED.json',run/'RESULT.json',run/'usage.json',run/'tokens.jsonl',run/'checked.json']
        paths += [run/(c['id']+'.json') for c in request['cases']]
        for path in paths: control_files[str(path.relative_to(prior))] = sha(path)
        calls.append(request_path.stem)
    require(len(calls) == read(prior/'runner.json')['arms']['unchanged']['calls'] == 48, 'Missing unchanged control calls')
    source = old['baseline_import']; check_files(source['root'],source['files'])
    require(not folder.exists(), 'Never overwrite a matched comparison')
    folder.mkdir(); (folder/'code').mkdir(); (folder/'requests').mkdir(); (folder/'runs').mkdir()
    for name in old['code']: shutil.copyfile(prior/'code'/name,folder/'code'/name)
    for name in old['data']: shutil.copyfile(prior/name,folder/name)
    new = copy.deepcopy(old); new['scope'] = 'Manual targeted 4B arm against pinned completed unchanged editor; exact original 0.8B cases'
    new['models']['targeted'] = model; new['design']['arms'] = ['targeted']
    new['comparison_reference'] = {'root':str(prior),'files':control_files,'editor_calls':calls,
        'unchanged_editor_not_rerun':True,'sampling_interface_cases_seeds_limits_identical':True,
        'scope':'Single historical matched control, fixed familiar evaluation set; no repeatability or globally unseen claim'}
    atomic(folder/'manifest.json',new); (folder/'manifest.sha256').write_text(identity(new))
    atomic(folder/'GPU-AUTHORIZATION.json',{'manifest_sha256':identity(new),'explicit_user_authorization':False})
    return identity(new)


def execute(root):
    from weight_editor_owned import launch
    from weight_editor_runtime import account_before_grading
    import numpy as np
    root = Path(root).resolve(); plan = read(root/'manifest.json')
    sys.path.insert(0,plan['project'])
    require(identity(plan) == (root/'manifest.sha256').read_text().strip(), 'Plan changed')
    check_files(root/'code',plan['code']); check_files(root,plan['data']); check_files(plan['reference']['root'],plan['reference']['files'])
    check_files(plan['retention_reference']['root'],plan['retention_reference']['files'])
    with exclusive(root):
        require(not (root/'runner.json').exists(), 'No implicit replay of a stopped diagnostic')
        deadline = Deadline(plan['diagnostic_design']['total_seconds']); diagnostic = deadline.child(plan['diagnostic_design']['diagnostic_seconds'])
        state = {'status':'running','pid':os.getpid(),'began_unix':time.time(),'phase':'baseline_decisions'}
        def save(**values):
            state.update(values); atomic(root/'runner.json',state)
        serial = 0
        def run_request(label,request,limit):
            nonlocal serial
            serial += 1; name = f'call-{serial:03d}-{label}'
            path = root/'requests'/(name+'.json'); atomic(path,request); atomic(root/'active-request.json',{'sha256':sha(path)})
            save(current_call=name)
            folder = root/'runs'/name
            try:
                result = launch(root,folder,[plan['interpreters']['python']['path'],'-X','utf8',
                    str(root/'code/weight_editor_targeted.py'),'worker',str(path)],limit)
            finally:
                if (folder/'usage.json').exists():
                    binding = read(folder/'usage.json')['binding']; account_before_grading(root/'usage.json',name,folder,binding)
            require(result['request_sha256'] == sha(path), 'Native result/request mismatch')
            return result,folder
        try:
            cases = read(root/'decision-inputs.json'); dev = [c for c in cases if c['split'] == 'development']
            base = plan['models']['unchanged']
            trials = [{'id':'base-dev','cases':dev,'capture':True},
                      {'id':'base-other','cases':[c for c in cases if c['split'] != 'development']}]
            result,baseline_folder = run_request('baseline',{'mode':'choices','model':base,'trials':trials},diagnostic)
            baseline = result['observations']; atomic(root/'BASELINE-DECISIONS.json',{'summary':summarize(baseline),'rows':baseline})
            save(phase='causal_layer_probes',baseline=summarize(baseline))
            layer_trials = [{'id':f'layer-{layer}','cases':dev,
                             'intervention':{'kind':'scale','name':f'ffn_out-{layer}','scale':.5}}
                            for layer in plan['diagnostic_design']['layers']]
            result,_ = run_request('layer-causal',{'mode':'choices','model':base,'trials':layer_trials},diagnostic)
            layer_rows = {t['id']:[r for r in result['observations'] if r['trial'] == t['id']] for t in layer_trials}
            layers = sorted(plan['diagnostic_design']['layers'],key=lambda layer:probe_rank(layer_rows[f'layer-{layer}']),reverse=True)[:2]
            atomic(root/'CAUSAL-LAYERS.json',{'selected_layers':layers,'results':{k:summarize(v) for k,v in layer_rows.items()},
                'scope':'Last-token intervention only; identifies local decision effects, not a global causal neuron interpretation'})
            # CPU ranking occurs only after the native child has closed.
            save(phase='local_column_attribution',selected_layers=layers)
            check_files(plan['cpu_vendor_sources']['path'],plan['cpu_vendor_sources']['files']); sys.path.insert(0,plan['cpu_vendor_sources']['path'])
            from gguf import GGUFReader
            from gguf.quants import dequantize
            from tokenizers import Tokenizer
            reader = GGUFReader(base['path']); tensors = {t.name:t for t in reader.tensors}
            tokenizer = Tokenizer.from_file(str(Path(plan['tokenizers']['editor_tokenizer']['path'])/'tokenizer.json'))
            choice_ids = [tokenizer.encode(c,add_special_tokens=False).ids[0] for c in 'ABCD']
            head = tensors.get('output.weight',tensors.get('token_embd.weight'))
            require(head is not None, 'Readout tensor absent')
            readout = np.stack([dequantize(head.data[i:i+1],head.tensor_type).reshape(-1) for i in choice_ids])
            norm_t = tensors['output_norm.weight']; norm = dequantize(norm_t.data,norm_t.tensor_type).reshape(-1)
            require(readout.shape == (4,2560) and norm.shape == (2560,), 'Readout layout mismatch')
            proposals = {}; column_trials = []
            for layer in layers:
                tensor = tensors[f'blk.{layer}.ffn_down.weight']; weights = dequantize(tensor.data,tensor.tensor_type)
                require(weights.shape == (2560,9216), 'Down-projection layout mismatch')
                harmful = np.zeros(9216,dtype=np.float64)
                for c in dev:
                    diagnostic.remaining(); path = baseline_folder/('base-dev-'+c['id']+'.npz')
                    with np.load(path,allow_pickle=False) as capture:
                        x = capture[f'ffn_swiglu-{layer}'].astype(np.float64)
                        logits = capture['logits'][choice_ids]
                    good = 'ABCD'.index(c['correct_letter']); bad = max((i for i in range(4) if i != good),key=lambda i:logits[i])
                    direction = norm.astype(np.float64)*(readout[good].astype(np.float64)-readout[bad].astype(np.float64))
                    direction /= max(1e-12,np.linalg.norm(direction))
                    harmful -= x*(direction@weights)
                order = np.argsort(-harmful,kind='stable')
                np.savez_compressed(root/(f'layer-{layer}-column-attribution.npz'),harmful_score=harmful,ranking=order)
                for count in plan['diagnostic_design']['column_counts']:
                    columns = sorted(map(int,order[:count]))
                    for scale in plan['diagnostic_design']['column_doses']:
                        name = f'layer-{layer}-n{count}-scale{str(scale).replace(".","p")}'
                        proposals[name] = {'layer':layer,'columns':columns,'scale':scale,'name':name}
                        column_trials.append({'id':name,'cases':dev,'intervention':{'kind':'columns','name':f'ffn_swiglu-{layer}',
                            'columns':columns,'scale':scale}})
                del weights
            del reader,tensors,head,readout,norm
            save(phase='causal_column_probes')
            result,_ = run_request('column-causal',{'mode':'choices','model':base,'trials':column_trials},diagnostic)
            groups = {t['id']:[r for r in result['observations'] if r['trial'] == t['id']] for t in column_trials}
            winner = max(sorted(groups),key=lambda k:probe_rank(groups[k])); proposal = proposals[winner]
            frozen = {'proposal':proposal,'development_rows':groups[winner],
                'all_candidates':{k:summarize(v) for k,v in groups.items()},
                'baseline_development_rank':probe_rank([r for r in baseline if r['split'] == 'development']),
                'candidate_development_rank':probe_rank(groups[winner]),'confirmation_unread_at_selection':True,
                'attribution':'Local readout dot-product proxy followed by causal column attenuation; no autodiff, derivative fitting or optimizer'}
            atomic(root/'FROZEN-CANDIDATE.json',frozen)
            save(phase='build_actual_q8',selected_proposal=proposal)
            candidate = build_candidate(plan,proposal,root/'artifacts/targeted',deadline)
            available = sorted(set(range(9216))-set(proposal['columns']))
            random_columns = sorted(random.Random(2026110321).sample(available,len(proposal['columns'])))
            shuffled_proposal = {**proposal,'columns':random_columns,'name':'shuffled-equal-column-count'}
            shuffled = build_candidate(plan,shuffled_proposal,root/'artifacts/shuffled',deadline)
            actual = {}
            for label,model in [('targeted',candidate),('shuffled',shuffled)]:
                save(phase='actual_q8_decisions',actual_arm=label)
                result,_ = run_request(label+'-q8',{'mode':'choices','model':model,'trials':[{'id':label,'cases':cases}]},deadline.child(1800))
                actual[label] = {'rows':result['observations'],'summary':summarize(result['observations']),
                    'ordinary_lost':paired_losses(baseline,result['observations'],'ordinary'),
                    'confirmation_lost':paired_losses(baseline,result['observations'],'confirmation')}
                atomic(root/'ACTUAL-Q8-DECISIONS.json',actual)
            if actual['targeted']['ordinary_lost']:
                save(status='completed_no_qualification',phase='ordinary_retention_failed',reason='Candidate lost baseline-correct ordinary choices; no downstream editor launch')
            else:
                save(phase='saved_editor_context_replay')
                prior = Path(plan['reference']['root']); wanted = set(plan['diagnostic_design']['saved_context_replay_turns'])
                replay_cases, replay_refs = [], []
                for path in sorted((prior/'requests').glob('*.json')):
                    request = read(path)
                    if request['mode'] != 'editor' or request['study_context']['editor_arm'] != 'unchanged': continue
                    c = request['cases'][0]; turn = int(c['id'].split('-')[-1])
                    if turn not in wanted: continue
                    run = prior/'runs'/path.stem
                    require(read(run/'CLOSED.json')['owned_worker_closed'] and read(run/'RESULT.json')['status'] == 'completed', 'Replay source not closed')
                    replay_cases.append(c)
                    replay_refs.append({'id':c['id'],'request_file':str(path),'request_sha256':sha(path),
                        'response_file':str(run/(c['id']+'.json')),'response_sha256':sha(run/(c['id']+'.json'))})
                require(len(replay_cases) == len(wanted), 'Missing fixed replay prefixes')
                atomic(root/'REPLAY-REFERENCES.json',replay_refs)
                result,folder = run_request('context-replay',{'mode':'replay','model':candidate,'cases':replay_cases,'remaining_tokens':32768},deadline.child(3000))
                atomic(root/'REPLAY-COMPLETED.json',{'folder':str(folder),'rows':result['responses'],
                    'authorship':'Actual edited-4B native continuations; no model-written code was executed',
                    'control_reused':replay_refs,'selection_used_these_results':False})
                save(phase='actual_q8_math_retention')
                ref = Path(plan['retention_reference']['root']); math_cases = read(ref/'cases-input.json'); golds = read(ref/'golds-private.json')
                expected = read(ref/'control-request.json')
                require(expected['cases'] == math_cases and expected['model_sha256'] == base['sha256'], 'Math control mismatch')
                require(all(r['correct'] for r in read(ref/'FINAL.json')['outcomes']['control']['rows']), 'Math preservation baseline not correct')
                result,folder = run_request('math-retention',{'mode':'retention','model':candidate,'cases':math_cases,'remaining_tokens':131072},deadline.child(3600))
                from weight_repair_protocol import grade
                retained = []
                for c in math_cases:
                    row = read(folder/(c['id']+'.json')); deadline.remaining()
                    checked = grade(plan['interpreters']['cpu_python']['path'],row['text'],golds[c['id']],timeout=min(10,deadline.remaining()))
                    retained.append({'id':c['id'],**checked,'generated_tokens':row['generated_tokens'],'finish_reason':row['finish_reason']})
                atomic(root/'MATH-RETENTION.json',{'rows':retained,'baseline_reused':plan['retention_reference'],
                    'correct':sum(r['correct'] for r in retained),'count':len(retained)})
                if not all(r['correct'] for r in retained):
                    save(status='completed_no_qualification',phase='math_retention_failed',reason='Candidate lost an existing correct math case; downstream editor not launched')
                else:
                    save(phase='publish_matched_editor_comparison')
                    comparison = root/'comparison'; fingerprint = publish_comparison(plan,candidate,comparison)
                    atomic(root/'DOWNSTREAM-PUBLICATION.json',{'root':str(comparison),'manifest_sha256':fingerprint,
                        'candidate_frozen_before_target_hidden_checks':True,'decision_scores_not_target_quality_evidence':True})
                    from tensor_workspace_study import Study
                    with exclusive(comparison):
                        study = Study(comparison); study.deadline = deadline; study.worker_deadline = deadline
                        save(phase='targeted_editor_vs_original08b',comparison=str(comparison)); study.run()
                    result = read(comparison/'RESULT.json')
                    require(result['status'] == 'completed', 'Downstream study stopped: '+str(result.get('error')))
                    save(status='completed',phase='all_stages_completed')
        except BaseException as error:
            save(status='stopped',error=type(error).__name__+': '+str(error))
        finally:
            save(ended_unix=time.time(),elapsed_seconds=plan['diagnostic_design']['total_seconds']-max(0,deadline.end-time.monotonic()))
            atomic(root/'RESULT.json',state)
    return state


if __name__ == '__main__':
    if sys.argv[1] == 'worker': worker(sys.argv[2:])
    elif sys.argv[1] == 'prepare': print(prepare(*sys.argv[2:]))
    elif sys.argv[1] == 'run': print(execute(sys.argv[2]))
