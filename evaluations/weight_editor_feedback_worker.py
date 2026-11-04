"""Explicitly authorized bounded feedback-only GPU worker; inert on import."""
import os
from pathlib import Path
import sys
import time

from lora6k_state import atomic, identity, read, sha
from weight_editor_feedback import PROFILES
from weight_editor_runtime import Deadline, TokenBudget, check_files, require


def main(arguments):
    request_path, root, folder, token, end = arguments
    root, folder, request_path = Path(root), Path(folder), Path(request_path)
    deadline = Deadline(end=float(end))
    plan, request = read(root/'manifest.json'), read(request_path)
    require(identity(plan) == (root/'manifest.sha256').read_text().strip(), 'Manifest changed')
    require(read(root/'GPU-AUTHORIZATION.json') == {'manifest_sha256': identity(plan), 'explicit_user_authorization': True}, 'GPU not authorized')
    check_files(root/'code', plan['code']); check_files(plan['engine'], plan['engine_files'])
    require(sha(request_path) in plan['diagnostic_requests'].values(), 'Unfrozen diagnostic request')
    require(request['model_sha256'] == plan['models']['editor_model']['sha256'] == sha(request['model']), 'Editor model changed')
    check_files(request['tokenizer'], request['tokenizer_files'])
    require(sys.flags.optimize == 0 and request['remaining_tokens'] <= 50000, 'Invalid worker limits')
    cases = request['cases']
    require(0 < len(cases) <= 24 and len({c['id'] for c in cases}) == len(cases), 'Case coverage invalid')
    require(all(c['profile'] in PROFILES and c['output_tokens'] <= PROFILES[c['profile']]['output_tokens']
                and len(c['input_ids']) + c['output_tokens'] <= 34816 for c in cases), 'Case limits invalid')
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
            atomic(folder/'progress.json', progress); last_event = now
    api = model = None
    result = {'status': 'failed', 'token': token, 'request_sha256': binding['request_sha256'], 'cleanup_complete': False}
    try:
        from tokenizers import Tokenizer
        from weight_editor_native import BatchAPI
        import weight_editor_worker as generation
        def sampler(profile):
            def create(native, seed):
                params = native.lib.llama_sampler_chain_default_params()
                chain = native.lib.llama_sampler_chain_init(params)
                require(bool(chain), 'Sampler allocation failed')
                try:
                    for child in (native.lib.llama_sampler_init_temp(profile['temperature']),
                                  native.lib.llama_sampler_init_top_k(profile['top_k']),
                                  native.lib.llama_sampler_init_top_p(profile['top_p'], 1),
                                  native.lib.llama_sampler_init_dist(seed)):
                        require(bool(child), 'Sampler component missing')
                        native.lib.llama_sampler_chain_add(chain, child)
                    return chain
                except BaseException:
                    native.lib.llama_sampler_free(chain)
                    raise
            return create
        event('loading'); deadline.remaining()
        api = BatchAPI(plan['engine']); model = api.load(request['model'])
        progress['gpu_loaded'] = True
        tokenizer = Tokenizer.from_file(str(Path(request['tokenizer'])/'tokenizer.json'))
        result['responses'] = []
        for case in cases:
            deadline.remaining()
            progress['case_id'] = case['id']
            generation.editor_sampler = sampler(PROFILES[case['profile']])
            payload = {**request, 'kind': 'editor', 'cases': [case], 'slots': 1,
                       'output_tokens': case['output_tokens'], 'request_seconds': 180,
                       'stop_token_ids': [248044, 248046]}
            result['responses'].extend(generation.generate(api, model, payload, folder, tokenizer, budget, deadline, event))
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
            atomic(folder/'RESULT.json', result)


if __name__ == '__main__':
    main(sys.argv[1:])
