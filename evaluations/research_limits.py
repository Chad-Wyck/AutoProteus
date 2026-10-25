"""Explicit research limits, independent of normal application preferences."""
import math
from controller.config import DEFAULTS


def research_config(values):
    config = {**DEFAULTS, **values, 'action_limit':True}
    if config.get('api_key'):
        raise ValueError('Keep provider keys in AUTOPROTEUS_API_KEY, not study plans')
    if type(config['max_steps']) is not int or not 1 <= config['max_steps'] <= 200:
        raise ValueError('Research action allowances must be integers from 1 to 200')
    return config


def resource_limits(config, seconds, tokens):
    if (config.get('action_limit') is not True or type(seconds) not in (int,float)
            or not math.isfinite(seconds) or seconds <= 0 or type(tokens) is not int or tokens <= 0):
        raise ValueError('Research requires explicit action, wall-time and generated-token limits')
    return {'actions':config['max_steps'], 'action_limit':True, 'wall_seconds':seconds,
            'generated_tokens':tokens, 'scope':'Shared by the declared trial stages; no automatic allowance extension.'}
