"""Explicitly authorized native worker; imports alone never initialize CUDA."""
import ctypes as C
import json
import os
from pathlib import Path
import sys
import time

from lora6k_state import atomic, identity, read, sha
from weight_editor_runtime import Deadline, TokenBudget, check_files, require


def generate(api, model, request, folder, tokenizer, budget, deadline, event):
    """Keep sampled-token receipts and independent sequence state in one loop."""
    result = []
    ctx, samplers = None, []
    try:
        for offset in range(0, len(request['cases']), request['slots']):
            event('context', request_deadlines={})
            deadline.remaining()
            ctx = api.context_slots(model, request['slots'])
            states = []
            batch = request['cases'][offset:offset + request['slots']]
            for seq, case in enumerate(batch):
                limit = deadline.child(request['request_seconds'])
                state = {'case': case, 'tokens': [], 'start': time.monotonic(), 'deadline': limit, 'seq': seq, 'finished': False}
                states.append(state)
                event('prefill', request_deadlines={s['case']['id']: s['deadline'].end for s in states})
                require(api.encode(model, case['rendered_prompt']) == case['input_ids'], 'Prompt/tokenizer mismatch')
                api.prefill(ctx, case['input_ids'], seq, check=limit.remaining)
                sampler = api.sampler(model, case['rng_seed']) if request['kind'] == 'target' else editor_sampler(api, case['rng_seed'])
                samplers.append(sampler)
                sample(api, sampler, ctx, -1, state, budget)
            while not all(s['finished'] for s in states):
                active = []
                for state in states:
                    if state['finished']:
                        continue
                    state['deadline'].remaining()
                    tokens, case = state['tokens'], state['case']
                    if tokens[-1] in request['stop_token_ids'] or len(tokens) == request['output_tokens']:
                        state['finished'] = True
                        row = {'status': 'completed', 'id': case['id'], 'tokens': tokens,
                               'generated_tokens': len(tokens), 'text': tokenizer.decode(tokens, skip_special_tokens=True),
                               'raw_text': tokenizer.decode(tokens, skip_special_tokens=False),
                               'finish_reason': 'eos' if tokens[-1] in request['stop_token_ids'] else 'length',
                               'wall_seconds': time.monotonic()-state['start'], 'rng_seed': case['rng_seed'],
                               'input_tokens': len(case['input_ids']), 'slot': state['seq'], 'slots': request['slots'],
                               'context_per_slot': api.lib.llama_n_ctx_seq(ctx)}
                        atomic(Path(folder) / (case['id'] + '.json'), row)
                        result.append(case['id'])
                    else:
                        active.append(state)
                event('generation', request_deadlines={s['case']['id']: s['deadline'].end for s in active},
                      emitted_tokens=budget.state['emitted'])
                if active:
                    for state in active:
                        state['deadline'].remaining()
                    api.batch(ctx, [(s['tokens'][-1], len(s['case']['input_ids'])+len(s['tokens'])-1, s['seq'], True) for s in active])
                    for index, state in enumerate(active):
                        sample(api, samplers[state['seq']], ctx, index, state, budget)
            for sampler in samplers:
                api.lib.llama_sampler_free(sampler)
            samplers = []
            api.lib.llama_free(ctx)
            ctx = None
            event('between_batches', request_deadlines={})
        return result
    finally:
        for sampler in samplers:
            api.lib.llama_sampler_free(sampler)
        if ctx:
            api.lib.llama_free(ctx)


def sample(api, sampler, ctx, index, state, budget):
    state['deadline'].remaining()
    budget.before_sample()  # Includes the very first token; no uncounted lookahead.
    token = api.lib.llama_sampler_sample(sampler, ctx, index)
    require(type(token) is int and 0 <= token < 248320, 'Invalid native token')
    budget.record(state['case']['id'], token)
    state['tokens'].append(token)


def editor_sampler(api, seed):
    p = api.lib.llama_sampler_chain_default_params()
    p.no_perf = False
    sampler = api.lib.llama_sampler_chain_init(p)
    require(bool(sampler), 'Editor sampler allocation failed')
    try:
        for child in (api.lib.llama_sampler_init_temp(.2), api.lib.llama_sampler_init_top_k(20),
                      api.lib.llama_sampler_init_top_p(.8, 1), api.lib.llama_sampler_init_dist(seed)):
            require(bool(child), 'Editor sampler component failed')
            api.lib.llama_sampler_chain_add(sampler, child)
        return sampler
    except BaseException:
        api.lib.llama_sampler_free(sampler)
        raise


def main(arguments):
    request_path, root, folder, token, end = arguments
    root, folder, request_path = Path(root), Path(folder), Path(request_path)
    deadline = Deadline(end=float(end))
    deadline.remaining()
    plan = read(root / 'manifest.json')
    require(identity(plan) == (root / 'manifest.sha256').read_text().strip(), 'Frozen manifest changed')
    authorization = read(root / 'GPU-AUTHORIZATION.json')
    require(authorization == {'manifest_sha256': identity(plan), 'explicit_user_authorization': True}, 'GPU execution not authorized')
    check_files(root / 'code', plan['code'])
    check_files(plan['engine'], plan['engine_files'])
    require(sys.flags.optimize == 0, 'Worker integrity checks require optimization disabled')
    request = read(request_path)
    require(request['kind'] in ('target', 'editor') and type(request['slots']) is int
            and request['slots'] == (2 if request['kind'] == 'target' else 1), 'Unsupported worker mode/slots')
    require(request['output_tokens'] == (32768 if request['kind'] == 'target' else 4096), 'Output allowance changed')
    require(request['request_seconds'] == 2700 and request['stop_token_ids'] == [248044, 248046], 'Frozen request protocol changed')
    require(len({c['id'] for c in request['cases']}) == len(request['cases']) > 0, 'Empty or duplicate cases')
    require(all(c['id'].replace('-', '').isalnum() and len(c['id']) < 80 for c in request['cases']), 'Invalid case ID')
    require(all(len(c['input_ids']) + request['output_tokens'] <= 34816 for c in request['cases']), 'Frozen context allowance exceeded')
    require(type(request['remaining_tokens']) is int and 0 <= request['remaining_tokens'] <=
            (plan['limits']['target_generated_tokens'] if request['kind'] == 'target' else 4096), 'Invalid generated-token reservation')
    require(sha(request['model']) == request['model_sha256'], 'Model identity changed')
    check_files(request['tokenizer'], request['tokenizer_files'])
    deadline.remaining()
    binding = {'nonce': token, 'request_sha256': sha(request_path)}
    budget = TokenBudget(folder, request['remaining_tokens'], binding)
    progress = {'pid': os.getpid(), 'token': token, 'gpu_loaded': False, 'request_deadlines': {}}
    last_event = 0.

    def event(kind, **data):
        nonlocal last_event
        changed = kind != progress.get('event') or data.get('request_deadlines') != progress.get('request_deadlines')
        progress.update(event=kind, **data)
        now = time.monotonic()
        if changed or now-last_event >= 1:
            atomic(folder / 'progress.json', progress)
            last_event = now

    api = model = None
    result = {'status': 'failed', 'token': token, 'request_sha256': binding['request_sha256'], 'cleanup_complete': False}
    try:
        from weight_editor_native import BatchAPI
        from tokenizers import Tokenizer
        event('loading')
        api = BatchAPI(plan['engine'])
        require(api.penalty_control()['generated_unique_presence_only'], 'Sampler qualification failed')
        model = api.load(request['model'])
        progress['gpu_loaded'] = True
        tokenizer = Tokenizer.from_file(str(Path(request['tokenizer']) / 'tokenizer.json'))
        result['responses'] = generate(api, model, request, folder, tokenizer, budget, deadline, event)
        budget.settle()
        result.update(status='completed', generated_tokens=budget.state['emitted'])
    finally:
        try:
            if model:
                api.lib.llama_model_free(model)
            if api:
                api.close()
            budget.close()
            result['cleanup_complete'] = True
        finally:
            progress['gpu_loaded'] = False
            event('closed', request_deadlines={})
            atomic(folder / 'RESULT.json', result)


if __name__ == '__main__':
    main(sys.argv[1:])
