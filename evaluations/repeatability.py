"""Portable fixed-case definition; host-specific plans are prepared separately."""
import json
from pathlib import Path
import re

from activation_use import contract
from study_support import identity, file_identity


SEED_MODES = ('per-request', 'server-initialized', 'provider-default')


def sampling_record(config):
    """Record requests separately from declarations about an external runtime."""
    seed = config.get('sampling_seed')
    mode = config.get('sampling_seed_mode', 'per-request' if seed is not None else 'server-default')
    return {'mode': mode, 'request_seed': seed,
            'case_schedule_seed': config.get('case_schedule_seed'),
            'declared_server_initial_seed': config.get('server_initial_seed'),
            'server_initialization_verified': False,
            'scope': ('Provider-default sampling; the case schedule is not an inference RNG seed. Temperature and request seeds are omitted. '
                      if mode == 'provider-default' else '') + 'Request payloads record the sent seed. Server initialization/restarts and provider honoring '
                     'require separate runtime evidence; this runner does not reset or verify the service RNG.'}


def freeze_cases(plan,path,requested_repeats=None):
    pack=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    if not isinstance(pack,dict):raise ValueError('Case pack must be a JSON object')
    seeds=pack.get('sampling_seeds');cases=pack.get('cases')
    if type(pack.get('schema')) is not int or pack['schema']!=1 or not isinstance(seeds,list) or not seeds or len(seeds)>20:
        raise ValueError('Case pack needs schema 1 and a bounded list of distinct sampling seeds')
    if any(type(seed) is not int or not 0<=seed<=2147483647 for seed in seeds):
        raise ValueError('Invalid per-request sampling seed')
    if len(set(seeds))!=len(seeds):raise ValueError('Sampling seeds must be distinct')
    if requested_repeats is not None and requested_repeats!=len(seeds):
        raise ValueError('Repeats must match the frozen seed schedule')
    if not isinstance(cases,list) or not cases or len(cases)>len(plan['contracts']):
        raise ValueError('Case pack needs existing upgrade cases')
    features=[];specs={}
    for case in cases:
        if not isinstance(case,dict):raise ValueError('Invalid fixed case')
        feature=case.get('feature');nonce=case.get('input_id')
        if not isinstance(feature,str) or feature not in plan['contracts'] or feature in features or not isinstance(nonce,str) or not re.fullmatch('[a-z0-9-]{1,40}',nonce):
            raise ValueError('Invalid or repeated fixed case')
        features.append(feature);specs[feature]=contract(feature,nonce)
    plan['upgrade_tasks']=features;plan['repeats']=len(seeds)
    plan['first_use_contracts']={f'{repeat}-{feature}':specs[feature]
        for repeat in range(1,len(seeds)+1) for feature in features}
    mode = plan.get('sampling_seed_mode', 'per-request')
    plan['repeatability']={'case_pack_sha256':file_identity(path),'sampling_seeds':seeds,
        'sampling_seed_mode':mode,
        'seed_scope': 'Per-request seed.' if mode == 'per-request' else
            'Case schedule only; provider-default sampling has no reproducible inference seed.' if mode == 'provider-default' else
            'Declared initial server seed; external owner must initialize a fresh RNG stream for each attempt. Unverified by runner.',
        'portable_case_sha256':identity({'cases':specs,'contracts':plan['contracts'],'recipe':plan['recipe'],
            'seeds':seeds,'sampling_seed_mode':mode,'deadline':plan['deadline'],'generated_tokens':plan['generated_tokens']})}
    for profile in plan['profiles']:profile['config']['sampling_seed']=seeds[0]
    plan['scope']+=' Fixed task wording and fixtures across repeats; predeclared seed schedule and sampling mode. Provider honoring and determinism are not guaranteed. Prepare a fresh environment-bound plan on each host; compare source/settings and portable case identities.'


def repeat_config(plan,config,repeat):
    seeds=plan.get('repeatability',{}).get('sampling_seeds')
    values = dict(config)
    mode = plan.get('sampling_seed_mode', config.get('sampling_seed_mode', 'per-request'))
    if mode not in SEED_MODES:
        raise ValueError('Unknown sampling seed mode')
    seed = seeds[repeat-1] if seeds else config.get('sampling_seed', config.get('server_initial_seed'))
    if seed is not None and (type(seed) is not int or not 0 <= seed <= 2147483647):
        raise ValueError('Sampling seeds must be integers from 0 to 2147483647')
    if mode == 'provider-default':
        values.pop('sampling_seed', None)
        values.pop('server_initial_seed', None)
        values.update(sampling_seed_mode=mode, case_schedule_seed=seed)
    elif mode == 'server-initialized':
        if seed is None:
            raise ValueError('Server-initialized studies require a declared seed or case-pack seed schedule')
        values.pop('sampling_seed', None)
        values.update(sampling_seed_mode=mode, server_initial_seed=seed)
    else:
        values.pop('server_initial_seed', None)
        if seed is not None:
            values.update(sampling_seed=seed, sampling_seed_mode=mode)
    return values
