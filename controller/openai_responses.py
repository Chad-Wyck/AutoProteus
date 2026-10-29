"""Host-only Responses transport translation; the editable seed stays neutral."""
import copy
import hashlib
import json
from urllib.parse import urlparse


def selected(config):
    mode = config.get('api_format', 'auto')
    return config.get('provider') == 'hosted' and (mode == 'responses' or
        mode == 'auto' and urlparse(config['base_url']).hostname == 'api.openai.com')


def call_key(prefix, call):
    function = call['function']
    return hashlib.sha256(json.dumps([prefix, function['name'],
        json.loads(function['arguments'])], sort_keys=True, ensure_ascii=False).encode()).hexdigest()


class ResponsesHistory:
    """Replay opaque provider state only for an exact matching host history.

    Nothing here is read from guest metadata. Trimmed/changed histories and a
    new client fall back to ordinary neutral calls, with no stale reasoning.
    """
    def __init__(self):
        self.saved = {}

    def input(self, wire):
        items, ids = [], {}
        for index, message in enumerate(wire):
            if message['role'] == 'tool':
                items.append({'type': 'function_call_output',
                    'call_id': ids.get(message['tool_call_id'], message['tool_call_id']),
                    'output': message['content']})
                continue
            calls = message.get('tool_calls', [])
            saved = self.saved.get(call_key(wire[:index], calls[0])) if len(calls) == 1 else None
            if saved:
                items.extend(copy.deepcopy(saved))
                actual = next(item['call_id'] for item in saved if item['type'] == 'function_call')
                ids[calls[0]['id']] = actual
                continue
            if message.get('content') or not calls:
                item = {'role': message['role'], 'content': message.get('content', '')}
                if message['role'] == 'assistant':
                    item['phase'] = 'commentary' if calls else 'final_answer'
                items.append(item)
            for call in calls:
                items.append({'type': 'function_call', 'call_id': call['id'],
                    'name': call['function']['name'], 'arguments': call['function']['arguments']})
        return items

    def remember(self, wire, output):
        # The synthetic last tool result closes the pending call. Never replay
        # an unexecuted finish alongside an action or an unsupported output item.
        if len(wire) < 2 or wire[-1]['role'] != 'tool':
            return
        calls = wire[-2].get('tool_calls', [])
        actual = [item for item in output if item['type'] == 'function_call']
        if len(calls) != 1 or len(actual) != 1:
            return
        function = calls[0]['function']
        if (function['name'] != actual[0]['name'] or
                json.loads(function['arguments']) != json.loads(actual[0]['arguments'])):
            return
        self.saved[call_key(wire[:-2], calls[0])] = copy.deepcopy(output)
        while len(self.saved) > 128:
            del self.saved[next(iter(self.saved))]


def payload(config, wire, tools, history):
    result = {'model': config['model'], 'input': history.input(wire), 'store': False,
        'stream': False, 'max_output_tokens': config['response_tokens']}
    effort = config.get('reasoning_effort')
    if effort is not None:
        result['reasoning'] = {'effort': effort}
    # Sol reasoning does not accept temperature or reproducible request seeds.
    if config.get('protocol', 'native') == 'native':
        result['tools'] = [{'type': 'function', 'name': item['function']['name'],
            'description': item['function'].get('description', ''),
            'parameters': copy.deepcopy(item['function']['parameters']), 'strict': False} for item in tools]
        result['parallel_tool_calls'] = False
    elif config.get('json_mode'):
        result['text'] = {'format': {'type': 'json_object'}}
    return result


def unpack(data):
    """Reject incomplete or unknown execution forms before any action exists."""
    from .providers import ProviderError
    usage = data.get('usage', {})
    if data.get('status') != 'completed' or data.get('error'):
        raise ProviderError('The Responses request did not complete; no action was executed.',
            {'usage': usage, 'incomplete': True}, category='cutoff')
    content, summaries, calls = [], [], []
    output = data.get('output')
    if not isinstance(output, list):
        raise ProviderError('Responses returned no output list.', {'usage': usage}, category='protocol')
    try:
        for item in output:
            kind = item['type']
            if kind == 'function_call':
                if item.get('status') not in (None, 'completed'):
                    raise ValueError('Incomplete function call')
                if not all(isinstance(item.get(key), str) and item[key] for key in ('call_id', 'name', 'arguments')):
                    raise ValueError('Malformed function call')
                calls.append({'id': item['call_id'], 'type': 'function',
                    'function': {'name': item['name'], 'arguments': item['arguments']}})
            elif kind == 'message':
                if item.get('status') not in (None, 'completed'):
                    raise ValueError('Incomplete message')
                if item.get('role') != 'assistant':
                    raise ValueError('Unexpected output role')
                for part in item['content']:
                    if part['type'] == 'output_text':
                        content.append(part['text'])
                    elif part['type'] == 'refusal':
                        content.append(part.get('refusal', 'Request refused.'))
                    else:
                        raise ValueError('Unsupported output content')
            elif kind == 'reasoning':
                summaries.extend(part['text'] for part in item.get('summary', []) if part.get('type') == 'summary_text')
            else:
                # Host tools, remote execution and program items are not guest
                # capabilities and cannot be silently treated as successful.
                raise ValueError('Unsupported Responses output item')
        if len(calls) > 32:
            raise ValueError('Too many function calls')
    except (KeyError, TypeError, ValueError):
        raise ProviderError('Unsupported or malformed Responses output; no action was executed.',
            {'usage': usage}, category='protocol') from None
    return ''.join(content), calls, '\n'.join(summaries), usage
