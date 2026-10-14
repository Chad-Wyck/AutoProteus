"""Bounded protocol checks and public identities; no model-chosen host tools."""
import json
import secrets
import threading

from .providers import ModelClient, ProviderError, ERROR_MESSAGES, request_json
from .storage import now


def check_protocol(config, key=''):
    if config['provider'] == 'demo':
        return {'passed': True, 'protocol': 'scripted', 'checked': now()}
    value = secrets.token_hex(8)
    tools = [
        {'type': 'function', 'function': {'name': 'diagnostic_echo', 'description': 'Return a test value.',
            'parameters': {'type': 'object', 'properties': {'value': {'type': 'string'}},
                           'required': ['value'], 'additionalProperties': False}}},
        {'type': 'function', 'function': {'name': 'finish', 'description': 'Complete the diagnostic after reading the result.',
            'parameters': {'type': 'object', 'properties': {'message': {'type': 'string'},
                           'status': {'type': 'string', 'enum': ['completed']}},
                           'required': ['message', 'status'], 'additionalProperties': False}}},
    ]
    native = config['protocol'] == 'native'
    prompt = ('Call diagnostic_echo with the supplied value. After receiving its result, call finish with '
              'status completed and the returned receipt as your message.' if native else
              'Return exactly one JSON object per turn. First: {"action":{"tool":"diagnostic_echo","arguments":{"value":"VALUE"}}}. '
              'After its result: {"status":"completed","message":"RECEIPT"}. Use the actual supplied value and returned receipt.')
    messages = [{'role': 'system', 'content': prompt}, {'role': 'user', 'content': 'Test value: ' + value}]
    client = ModelClient(config, key)
    cancel = threading.Event()
    try:
        first = client.complete(messages, cancel, tools=tools if native else None)
        decision = json.loads(first['content'])
        if decision.get('action') != {'tool': 'diagnostic_echo', 'arguments': {'value': value}}:
            raise ValueError('Expected one diagnostic tool call')
        receipt = secrets.token_hex(8)
        messages += [{'role': 'assistant', 'content': json.dumps(decision)},
                     {'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps({'tool': 'diagnostic_echo', 'ok': True, 'result': {'receipt': receipt}})}]
        second = json.loads(client.complete(messages, cancel, tools=tools if native else None)['content'])
        if second.get('status') != 'completed' or second.get('message') != receipt or 'action' in second:
            raise ValueError('Expected explicit completion using the actual result')
    except ProviderError:
        raise
    except (ValueError, KeyError, TypeError):
        raise ProviderError(ERROR_MESSAGES['protocol'], category='protocol') from None
    return {'passed': True, 'protocol': config['protocol'], 'model': config['model'], 'checked': now(), 'requests': 2}


def model_identity(config):
    identity = {'provider': config['provider'], 'model': config['model']}
    if config['provider'] == 'ollama':
        try:
            base = config['base_url'].rstrip('/')
            identity['engine_version'] = request_json(base + '/api/version', timeout=3).get('version')
            tags = request_json(base + '/api/tags', timeout=3).get('models', [])
            model = next((item for item in tags if item['name'] in (config['model'], config['model'] + ':latest')), {})
            identity.update({key: model[key] for key in ('digest', 'size') if key in model})
            identity['details'] = {key: model.get('details', {}).get(key) for key in ('family', 'parameter_size', 'quantization_level')}
        except Exception:
            identity['identity_available'] = False
    return identity
