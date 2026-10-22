"""Thin provider adapters. An incomplete response never becomes an action."""
from __future__ import annotations

import json
import queue
import threading
import time
import uuid
import urllib.error
import urllib.request

from .errors import Cancelled


class ProviderError(Exception):
    def __init__(self, message, response=None, category='connection'):
        super().__init__(message)
        self.response = response
        self.category = category if category in ERROR_MESSAGES else 'connection'


ERROR_MESSAGES = {
    'budget': 'The experiment exhausted its generated-token allowance. Saved work can still be independently checked.',
    'connection': 'The model service could not be reached. Check the connection and retry.',
    'timeout': 'The model response timed out. Retry or choose a smaller model.',
    'cutoff': 'The model response was cut short. Increase the response budget or retry; no partial action ran.',
    'protocol': 'The model did not follow the selected action protocol. Try JSON fallback or another model.',
    'context': 'The input exceeds the configured context estimate. Shorten the task or increase the context window in Settings.',
}

# Only these fixed explanations cross the broker for a repairable provider
# error. Raw server errors can contain secrets and remain host diagnostics.
PROTOCOL_HINTS = {
    'tool_arguments': 'Tool arguments were not valid JSON. Send a complete call with valid JSON arguments; escape newlines inside strings.',
    'tool_batch': 'A response may contain at most 32 tool calls. Send one tool call, inspect its result, then continue.',
}


def model_service_error(detail, native):
    text = detail.lower()
    if native and any(marker in text for marker in ('invalid tool call arguments', 'failed to parse tool call')):
        return ProviderError(detail, {'protocol_reason': 'tool_arguments'}, category='protocol')
    return ProviderError(detail)


def context_bytes(messages, tools):
    return len(json.dumps({'messages': messages, 'tools': tools or []}, ensure_ascii=False).encode('utf-8'))


def validate_context(messages, tools, config):
    """A model-agnostic upper bound on our estimate, not an exact tokenizer."""
    size = context_bytes(messages, tools)
    allowance = max(0, config['context_tokens'] - config['response_tokens'] - 128) * 2
    if size > allowance:
        raise ProviderError(ERROR_MESSAGES['context'], category='context')
    return {'estimated_input_tokens': (size + 1) // 2, 'allowance_tokens': allowance // 2}


def wire_messages(messages, ollama):
    """Translate the neutral journal history to a provider's tool message format."""
    output, pending = [], None

    def close_pending(result=None):
        nonlocal pending
        if pending is None:
            return
        call_id, name = pending
        if result is None:
            result = {'tool': name, 'ok': False, 'result': {
                'error': 'No saved result is available. The operation outcome is unknown; inspect before retrying.'}}
        item = {'role': 'tool', 'content': json.dumps(result, ensure_ascii=False)}
        item.update({'tool_name': name} if ollama else {'tool_call_id': call_id})
        output.append(item)
        pending = None

    for index, message in enumerate(messages):
        content = message['content']
        # Provider-specific reasoning signatures and old call IDs are not portable.
        plain = {k: message[k] for k in ('role', 'content', 'origin') if k in message}
        if message['role'] == 'assistant':
            close_pending()
            try:
                decision = json.loads(content)
            except ValueError:
                output.append(plain); continue
            if not isinstance(decision, dict):
                output.append(plain); continue
            action = decision.get('action')
            if (isinstance(action, dict) and isinstance(action.get('tool'), str)
                    and isinstance(action.get('arguments'), dict)):
                last_id = f'call_{index}'
                pending = (last_id, action['tool'])
                function = {'name': action['tool'], 'arguments': action['arguments'] if ollama else json.dumps(action['arguments'])}
                call = {'function': function} if ollama else {'id': last_id, 'type': 'function', 'function': function}
                output.append({'role': 'assistant', 'content': decision.get('message', ''), 'tool_calls': [call]})
            else:
                output.append({'role': 'assistant', 'content': decision.get('message', content)})
        elif message['role'] == 'user' and message.get('origin') != 'human' and content.startswith('ACTION RESULT\n'):
            try:
                result = json.loads(content.split('\n', 1)[1])
            except ValueError:
                result = None
            if pending and isinstance(result, dict) and result.get('tool') == pending[1]:
                close_pending(result)
            else:
                close_pending()
                # Orphan/mismatched results remain context, never a false success.
                output.append(plain)
        else:
            close_pending()
            output.append(plain)
    close_pending()
    return output


def normalize_tool_response(content, calls):
    if not calls:
        raise ValueError('A native response needs a tool call. Call finish with message and status="completed" after verification, or status="needs_input" to ask the user a required question.')
    if len(calls) > 32:
        raise ValueError('Too many tool calls in one response')
    decisions = []
    for call in calls:
        function = call['function']
        arguments = function['arguments']
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        if function['name'] == 'finish':
            decisions.append({'message': arguments['message'], 'status': arguments['status']})
        else:
            decisions.append({'message': content if not decisions else '', 'action': {'tool': function['name'], 'arguments': arguments}})
    if len(decisions) == 1:
        return json.dumps(decisions[0], ensure_ascii=False)
    # Execute ordered tools, then let the model inspect their actual results.
    # A finish call made alongside tools cannot yet verify those results.
    actions = [decision['action'] for decision in decisions if 'action' in decision]
    if not actions:
        raise ValueError('Return only one finish call')
    return json.dumps({'message': content, 'actions': actions, 'deferred_finish': any('status' in d for d in decisions)}, ensure_ascii=False)


def model_response(content, calls, native, **metadata):
    response = {'content': content, 'raw_content': content, 'tool_calls': calls, **metadata}
    if native:
        try:
            response['content'] = normalize_tool_response(content, calls)
        except (ValueError, KeyError, TypeError) as error:
            # Preserve malformed native responses in the journal for diagnosis.
            response.update(content='', normalization_error=str(error))
    return response


def request_json(url, data=None, headers=None, timeout=10):
    request = urllib.request.Request(url, data=json.dumps(data).encode() if data is not None else None,
                                     headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(2000001)
            if len(raw) > 2000000:
                raise ProviderError("The service response exceeded the maximum size")
            return json.loads(raw)
    except urllib.error.HTTPError as error:
        detail = error.read(2000).decode(errors="replace")
        raise ProviderError(f"The model service returned HTTP {error.code}: {detail}") from None
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ProviderError(f"Could not reach the model service: {error}") from None


class ModelClient:
    def __init__(self, config, key="", observer=None):
        self.config = dict(config)
        self.key = key
        self.observer = observer
        self.observation_context = None
        self.observation_failed = False

    def check_context(self, messages, tools):
        """Protected default; experimental host clients may supply another estimator."""
        return validate_context(messages, tools, self.config)

    def prepare_messages(self, messages, tools, observe=None):
        """Budget the actual provider representation without editing the journal.

        Native envelopes can exceed the seed's neutral estimate. Remove only
        oldest complete tool exchanges, retaining all system/user messages and
        the newest exchange. An irreducible request still fails before transport.
        """
        native = self.config.get('protocol', 'native') == 'native'
        ollama = self.config['provider'] == 'ollama'
        wire = wire_messages(messages, ollama) if native else [
            {key: item[key] for key in ('role', 'content')} for item in messages]
        wire = [{key: value for key, value in item.items() if key != 'origin'} for item in wire]
        schemas = tools if native else []
        pairs = []
        if native:
            for index, (call, result) in enumerate(zip(wire, wire[1:])):
                calls = call.get('tool_calls', [])
                if call['role'] != 'assistant' or len(calls) != 1 or result['role'] != 'tool':
                    continue
                matches = (result.get('tool_name') == calls[0]['function']['name'] if ollama else
                           result.get('tool_call_id') == calls[0].get('id'))
                if matches:
                    pairs.append(index)
        # Keep the newest exact observation available for the next decision.
        removable = iter(pairs[:-1])
        removed, before = 0, None
        while True:
            try:
                self.check_context(wire, schemas)
                break
            except ProviderError as error:
                index = next(removable, None) if error.category == 'context' else None
                if index is None:
                    raise
                if before is None:
                    before = context_bytes(wire, schemas)
                index -= removed * 2
                del wire[index:index + 2]
                removed += 1
        adjustment = None
        if removed:
            adjustment = {'reason': 'native_wire_context_limit', 'removed_tool_exchanges': removed,
                'messages_before': len(messages), 'messages_after': len(wire),
                'input_bytes_before': before, 'input_bytes_after': context_bytes(wire, schemas)}
            if observe:
                observe('context_trimmed', adjustment)
        return wire, adjustment

    def complete(self, messages, cancel, progress=None, tools=None):
        # Polling a worker lets Stop return promptly even during model loading.
        # A late result is discarded; it cannot run an action in a stopped session.
        result = queue.Queue(maxsize=1)
        call_id, started = uuid.uuid4().hex, time.monotonic()
        observer, observation_context = self.observer, self.observation_context
        key = self.key

        def record(kind, data):
            if observer is None:
                return
            def clean(value):
                if isinstance(value, str) and key:
                    return value.replace(key, '[REDACTED]').replace(
                        json.dumps(key, ensure_ascii=False)[1:-1], '[REDACTED]')
                if isinstance(value, list):
                    return [clean(item) for item in value]
                if isinstance(value, dict):
                    return {clean(name): clean(item) for name, item in value.items()}
                return value
            try:
                # A detached snapshot prevents a collector changing the request.
                snapshot = json.loads(json.dumps(data, ensure_ascii=False))
                snapshot = clean(snapshot)
                if kind == 'call_end' and 'error_detail' in snapshot:
                    snapshot['error_detail'] = snapshot['error_detail'][:2000]
                observer({'type': kind, 'call_id': call_id, 'time': time.time(),
                               'elapsed_seconds': time.monotonic() - started, 'data': snapshot})
            except Exception:
                # Diagnostics never change inference or release a partial action.
                self.observation_failed = True

        if observer is not None:
            try:
                context = observation_context(messages) if observation_context else {}
                record('call_start', {'context': context, 'provider': self.config['provider'],
                                     'model': self.config['model'], 'protocol': self.config.get('protocol', 'native')})
            except Exception:
                self.observation_failed = True

        def work():
            try:
                answer = (self._complete(messages, cancel, progress, tools, observe=record)
                          if observer is not None else self._complete(messages, cancel, progress, tools))
                outcome = (True, answer)
            except Exception as error:
                outcome = (False, error)
            record('transport_end', {'finished': True})
            result.put(outcome)

        if cancel.is_set():
            record('transport_end', {'finished': True, 'not_started': True})
            record('call_end', {'status': 'cancelled'})
            raise Cancelled()
        threading.Thread(target=work, daemon=True).start()
        deadline = time.monotonic() + self.config.get("request_timeout", 180)
        try:
            while True:
                if cancel.is_set():
                    raise Cancelled()
                if time.monotonic() > deadline:
                    raise ProviderError(ERROR_MESSAGES['timeout'], category='timeout')
                try:
                    ok, value = result.get(timeout=0.1)
                except queue.Empty:
                    continue
                if not ok:
                    raise value
                record('call_end', {'status': 'returned', 'content': value.get('content'),
                       'normalization_error': value.get('normalization_error'), 'usage': value.get('usage', {})})
                return value
        except Cancelled:
            record('call_end', {'status': 'cancelled'})
            raise
        except Exception as error:
            usage = error.response.get('usage', {}) if isinstance(error, ProviderError) and isinstance(error.response, dict) else {}
            record('call_end', {'status': 'error', 'category': error.category if isinstance(error, ProviderError) else 'internal',
                               'usage': usage, 'error_detail': str(error)})
            raise

    def _complete(self, messages, cancel, progress, tools=None, observe=None):
        config = self.config
        native = config.get('protocol', 'native') == 'native'
        if native and tools is None:
            raise ProviderError('Native inference requires tool definitions supplied by the seed')
        wire, adjustment = self.prepare_messages(messages, tools, observe)
        context_metadata = {'context_adjustment': adjustment} if adjustment else {}
        base = config["base_url"].rstrip("/")
        if config["provider"] == "ollama":
            payload = {"model": config["model"], "messages": wire, "stream": True,
                       "options": {"num_ctx": config["context_tokens"], "num_predict": config["response_tokens"],
                                   "temperature": config["temperature"]}, "keep_alive": "10m"}
            if native:
                payload['tools'] = tools
            else:
                payload['format'] = 'json'
            if config.get("thinking") is not None:
                payload["think"] = config["thinking"]
            request = urllib.request.Request(base + "/api/chat", data=json.dumps(payload).encode(),
                                             headers={"Content-Type": "application/json"})
            if observe:
                observe('provider_request', {'payload': payload})
            text, thinking, done, metrics, calls = "", "", False, {}, []
            frames, recorded = [], False
            received = 0
            try:
                with urllib.request.urlopen(request, timeout=config.get("request_timeout", 180)) as response:
                    while True:
                        raw = response.readline(1000001)
                        if not raw:
                            break
                        if len(raw) > 1000000:
                            raise ProviderError("The model stream exceeded the maximum frame size")
                        received += len(raw)
                        if received > 2000000:
                            raise ProviderError('The model stream exceeded the maximum response size')
                        if cancel.is_set():
                            raise Cancelled()
                        item = json.loads(raw)
                        if observe:
                            frames.append(item)
                        if item.get("error"):
                            raise model_service_error(str(item["error"]), native)
                        text += item.get("message", {}).get("content", "")
                        thinking += item.get("message", {}).get("thinking", "")
                        calls.extend(item.get('message', {}).get('tool_calls', []))
                        if len(calls) > 32:
                            raise ProviderError('The model returned too many tool calls',
                                                {'protocol_reason': 'tool_batch'}, category='protocol')
                        if progress:
                            progress(len(text))
                        if len(text) + len(thinking) > 300000:
                            raise ProviderError("The model response exceeded the maximum size.")
                        if item.get("done"):
                            done = True
                            metrics = {key: item.get(key) for key in ("prompt_eval_count", "eval_count", "done_reason", "total_duration")}
                            break
                if observe:
                    observe('provider_response', {'frames': frames, 'stream': True, 'complete': done})
                    recorded = True
                if not done or metrics.get("done_reason") == "length":
                    raise ProviderError("The model response was cut short. No action was executed. Increase the response budget or retry.",
                                        {'raw_content':text, 'thinking':thinking, 'tool_calls':calls, 'usage':metrics, 'incomplete':True}, category='cutoff')
                return model_response(text, calls, native, thinking=thinking, usage=metrics, **context_metadata)
            except urllib.error.HTTPError as error:
                raise model_service_error(f"Local model error (HTTP {error.code}): {error.read(2000).decode(errors='replace')}", native) from None
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                raise ProviderError(f"The local model connection was interrupted: {error}. No partial action was executed.",
                                    {'raw_content':text, 'thinking':thinking, 'tool_calls':calls, 'incomplete':True}) from None
            finally:
                if observe and not recorded:
                    observe('provider_response', {'frames': frames, 'stream': True, 'complete': done})
        payload = {"model": config["model"], "messages": wire, "stream": False,
                   "max_tokens": config["response_tokens"], "temperature": config["temperature"]}
        if native:
            payload['tools'] = tools
        if config.get("json_mode") and not native:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": "Bearer " + self.key} if self.key else {}
        if observe:
            observe('provider_request', {'payload': payload})
        try:
            data = request_json(base + "/chat/completions", payload, headers, config.get("request_timeout", 180))
        except ProviderError as error:
            if error.category == 'connection':
                raise model_service_error(str(error), native) from None
            raise
        if observe:
            observe('provider_response', {'payload': data, 'stream': False, 'complete': True})
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") not in ("stop", "tool_calls", None):
                raise ProviderError("The model response was cut short or rejected. No action was executed.",
                                    {'raw_content':choice.get('message',{}), 'usage':data.get('usage',{}), 'incomplete':True}, category='cutoff')
            content = choice["message"].get("content") or ""
            if not isinstance(content, str):
                raise ProviderError("The provider did not return a text response.")
            calls = choice['message'].get('tool_calls', [])
            return model_response(content, calls, native, usage=data.get('usage', {}), **context_metadata)
        except (KeyError, IndexError, TypeError):
            raise ProviderError("The provider returned an unexpected response format.") from None


class DemoClient:
    """A clearly labeled, deterministic tour; this is not a language model."""
    def complete(self, messages, cancel, progress=None):
        for _ in range(5):
            if cancel.wait(0.12):
                raise Cancelled()
        results = sum(message["role"] == "user" and message["content"].startswith("ACTION RESULT") for message in messages)
        steps = [
            {"message": "I'll create a short plan for this sample run.", "action": {"tool": "write_file", "arguments": {"path": "todo.txt", "content": "[ ] Create welcome.md\n[ ] Read the file to verify it\n"}}},
            {"message": "I'm writing a welcome note in this session's workspace.", "action": {"tool": "write_file", "arguments": {"path": "welcome.md", "content": "# Hello from AutoProteus\n\nThis file was created by the interactive demo.\n\nThe demo uses real workspace tools and session logging, but no AI model.\n"}}},
            {"message": "I'll read the file back before marking the task complete.", "action": {"tool": "read_file", "arguments": {"path": "welcome.md"}}},
            {"message": "The file is present. I'm updating the checklist.", "action": {"tool": "write_file", "arguments": {"path": "todo.txt", "content": "[x] Create welcome.md\n[x] Read the file to verify it\n"}}},
            {"message": "Your sample run is complete. Open welcome.md in Files, or connect a model to start your own task.", "status": "completed"},
        ]
        return {"content": json.dumps(steps[min(results, len(steps)-1)]), "usage": {}, "demo": True}
