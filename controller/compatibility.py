"""Bounded protocol checks and public identities; no model-chosen host tools."""
import json
import hashlib
import secrets
import threading
import time
from pathlib import Path

from .providers import ModelClient, ProviderError, ERROR_MESSAGES, PROTOCOL_HINTS, request_json
from .storage import now


def check_protocol(config, key='', rounds=1, recovery=False, full_catalog=False):
    if config['provider'] == 'demo':
        return {'passed': True, 'protocol': 'scripted', 'checked': now()}
    if type(rounds) is not int or not 1 <= rounds <= 3:
        raise ValueError('Use one to three diagnostic rounds')
    tools = [
        {'type': 'function', 'function': {'name': 'diagnostic_echo', 'description': 'Return a test value.',
            'parameters': {'type': 'object', 'properties': {'value': {'type': 'string'}},
                           'required': ['value'], 'additionalProperties': False}}},
        {'type': 'function', 'function': {'name': 'diagnostic_confirm', 'description': 'Confirm the exact receipt string from the diagnostic_echo result.',
            'parameters': {'type': 'object', 'properties': {'receipt': {'type': 'string'}},
                           'required': ['receipt'], 'additionalProperties': False}}},
        {'type': 'function', 'function': {'name': 'finish', 'description': 'Complete the diagnostic after reading the result.',
            'parameters': {'type': 'object', 'properties': {'message': {'type': 'string'},
                           'status': {'type': 'string', 'enum': ['completed']}},
                           'required': ['message', 'status'], 'additionalProperties': False}}},
    ]
    if full_catalog:
        from autoproteus.providers import tool_definitions
        tools = [tool for tool in tool_definitions(config['terminal']) if tool['function']['name'] != 'finish'] + tools
    native = config['protocol'] == 'native'
    from autoproteus.protocol import parse_decisions
    from .isolation import RESPONSE_RETRIES
    response_retries = RESPONSE_RETRIES
    prompt = ('For each Test value, call diagnostic_echo with that exact value. '
              'After a successful result, call diagnostic_confirm with receipt equal to the string inside result.receipt. '
              'Supply the receipt as a string, without an object wrapper. '
              'If diagnostic_echo is rejected, retry it once with the same value. '
              'Each new Test value begins another round. When told all rounds are complete, finish completed with any short message.')
    messages = [{'role': 'system', 'content': prompt}]
    client = ModelClient(config, key)
    cancel = threading.Event()
    requests = repairs = 0
    deadline = time.monotonic() + min(600, config.get('request_timeout', 300) * 3)
    def complete():
        nonlocal requests, repairs
        for attempt in range(response_retries + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ProviderError(ERROR_MESSAGES['protocol'], category='protocol')
            client.config = {**client.config, 'request_timeout': min(config['request_timeout'], remaining)}
            requests += 1
            try:
                response = client.complete(messages, cancel, tools=tools)
            except ProviderError as error:
                if error.category not in ('cutoff', 'protocol'):
                    raise
                # Match the broker's fixed explanations; provider bodies can
                # contain credentials and must not become repair instructions.
                reason = error.response.get('protocol_reason') if isinstance(error.response, dict) else None
                response = ({'content': '', 'provider_error': 'cutoff'} if error.category == 'cutoff' else
                            {'content': '', 'normalization_error': PROTOCOL_HINTS.get(reason,
                             'Use the supplied tools with valid arguments. Prefer one tool call at a time.')})
            try:
                if response.get('provider_error') == 'cutoff':
                    raise ValueError('The response exceeded its output budget. Send a smaller action or patch. '
                                     'Generate large test data with short code rather than repeated literal text.')
                decisions, deferred = parse_decisions(response)
            except (ValueError, KeyError, TypeError) as error:
                if attempt >= response_retries:
                    raise ProviderError(ERROR_MESSAGES['protocol'], category='protocol') from None
                repairs += 1
                instruction = ('Use the supplied tools with valid arguments.' if native else
                               'Return exactly one complete JSON object following the system instructions.')
                messages.append({'role': 'user', 'origin': 'internal', 'content':
                    'Your response was not accepted: ' + str(error) + '. ' + instruction + ' No action was executed.'})
                continue
            # A valid but wrong action is a diagnostic failure, not a format
            # repair. Never execute a partial batch or provide the answer.
            if len(decisions) != 1 or deferred:
                raise ValueError('Expected one diagnostic decision')
            return decisions[0]
    try:
        for index in range(rounds):
            value = secrets.token_hex(8)
            messages.append({'role': 'user', 'content': 'Test value: ' + value})
            decision = complete()
            expected = {'tool': 'diagnostic_echo', 'arguments': {'value': value}}
            if decision.get('action') != expected:
                raise ValueError('Expected one diagnostic tool call')
            messages.append({'role': 'assistant', 'content': json.dumps(decision)})
            if recovery and index == 0:
                messages.append({'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps(
                    {'tool': 'diagnostic_echo', 'ok': False, 'error': 'Diagnostic rejection. Retry once with the same value.'})})
                decision = complete()
                if decision.get('action') != expected:
                    raise ValueError('Expected recovery from a rejected call')
                messages.append({'role': 'assistant', 'content': json.dumps(decision)})
            receipt = secrets.token_hex(8)
            messages.append({'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps(
                {'tool': 'diagnostic_echo', 'ok': True, 'result': {'receipt': receipt}})})
            confirmed = complete()
            if confirmed.get('action') != {'tool': 'diagnostic_confirm', 'arguments': {'receipt': receipt}}:
                raise ValueError('Expected confirmation of the exact receipt')
            messages.append({'role': 'assistant', 'content': json.dumps(confirmed)})
            messages.append({'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps(
                {'tool': 'diagnostic_confirm', 'ok': True, 'result': {'confirmed': True}})})
        messages.append({'role': 'user', 'content': 'All rounds are complete. Finish completed with a short message.'})
        finished = complete()
        if finished.get('status') != 'completed' or 'action' in finished:
            raise ValueError('Expected explicit completion')
    except ProviderError:
        raise
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ProviderError(ERROR_MESSAGES['protocol'], category='protocol') from None
    return {'passed': True, 'protocol': config['protocol'], 'model': config['model'], 'checked': now(),
            'requests': requests, 'rounds': rounds, 'rejected_call_recovery': recovery,
            'format_repairs': repairs, 'first_pass': repairs == 0, 'response_retries': response_retries,
            'receipt_check': 'Exact diagnostic_confirm.receipt argument; completion prose is unrestricted.',
            'scope': 'Bounded transport qualification, not a seed-editing or capability benchmark.'}


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
            show = request_json(base + '/api/show', {'model': config['model']}, timeout=3)
            if isinstance(show.get('template'), str) and show['template']:
                identity['template_sha256'] = hashlib.sha256(show['template'].encode()).hexdigest()
            if isinstance(show.get('parameters'), str):
                identity['parameters_sha256'] = hashlib.sha256(show['parameters'].encode()).hexdigest()
        except Exception:
            identity['identity_available'] = False
    return identity


PROFILE_FIELDS = ('provider', 'model', 'protocol', 'context_tokens', 'response_tokens', 'temperature',
                  'thinking', 'json_mode', 'terminal', 'request_timeout', 'api_format', 'reasoning_effort')


def qualify_profile(config, key='', previous=None):
    """Reuse a recent receipt only when every observable identity is complete."""
    if config['provider'] == 'demo':
        return check_protocol(config, key)
    from autoproteus.providers import tool_definitions
    from .isolation import RESPONSE_RETRIES
    identity = model_identity(config)
    profile = {name: config[name] for name in PROFILE_FIELDS}
    profile.update(identity=identity, endpoint_sha256=hashlib.sha256(config['base_url'].encode()).hexdigest(),
                   catalog_sha256=hashlib.sha256(json.dumps(tool_definitions(config['terminal']), sort_keys=True).encode()).hexdigest(),
                   adapter_sha256=hashlib.sha256(Path(__file__).with_name('providers.py').read_bytes()).hexdigest(),
                   response_format_sha256=hashlib.sha256(Path(__file__).with_name('action_protocol.py').read_bytes()).hexdigest(),
                   qualifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   qualification_version=3, response_retries=RESPONSE_RETRIES)
    fingerprint = hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()
    known = (config['provider'] == 'ollama' and all(identity.get(name) for name in
             ('engine_version', 'digest', 'template_sha256', 'parameters_sha256')) and
             identity.get('details', {}).get('quantization_level') and not identity.get('identity_available') is False)
    previous = previous or config.get('compatibility', {})
    # Credentials are not stored or hashed. A credential change forces a fresh
    # check at the caller; uncertain hosted metadata is never cacheable.
    if (known and previous.get('passed') is True and previous.get('rounds') == 3 and
            previous.get('rejected_call_recovery') is True and previous.get('profile_sha256') == fingerprint and
            0 <= time.time() - previous.get('checked_unix', 0) < 86400):
        return {**previous, 'cached': True, 'requests_this_check': 0}
    result = check_protocol(config, key, rounds=3, recovery=True, full_catalog=True)
    if known and model_identity(config) != identity:
        raise ProviderError('The model identity changed during qualification; reconnect and try again.', category='protocol')
    return {**result, 'profile': profile, 'profile_sha256': fingerprint, 'identity_complete': bool(known),
            'unknown_identity': [] if known else ['Complete weights, engine and template identity could not be verified; receipt is not reusable.'],
            'cached': False, 'checked_unix': time.time(), 'requests_this_check': result['requests']}
