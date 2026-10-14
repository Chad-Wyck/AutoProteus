"""Thin provider adapters. An incomplete response never becomes an action."""
from __future__ import annotations

import json
import queue
import threading
import time
import urllib.error
import urllib.request

from .errors import Cancelled


class ProviderError(Exception):
    def __init__(self, message, response=None, category='connection'):
        super().__init__(message)
        self.response = response
        self.category = category if category in ERROR_MESSAGES else 'connection'


ERROR_MESSAGES = {
    'connection': 'The model service could not be reached. Check the connection and retry.',
    'timeout': 'The model response timed out. Retry or choose a smaller model.',
    'cutoff': 'The model response was cut short. Increase the response budget or retry; no partial action ran.',
    'protocol': 'The model did not follow the selected action protocol. Try JSON fallback or another model.',
    'context': 'The input exceeds the configured context estimate. Shorten the task or increase the context window in Settings.',
}


def validate_context(messages, tools, config):
    """A model-agnostic upper bound on our estimate, not an exact tokenizer."""
    size = len(json.dumps({'messages': messages, 'tools': tools or []}, ensure_ascii=False).encode('utf-8'))
    allowance = max(0, config['context_tokens'] - config['response_tokens'] - 128) * 2
    if size > allowance:
        raise ProviderError(ERROR_MESSAGES['context'], category='context')
    return {'estimated_input_tokens': (size + 1) // 2, 'allowance_tokens': allowance // 2}


def wire_messages(messages, ollama):
    """Translate the neutral journal history to a provider's tool message format."""
    output, last_id = [], None
    for index, message in enumerate(messages):
        content = message['content']
        if message['role'] == 'assistant':
            try:
                decision = json.loads(content)
            except ValueError:
                output.append(message); continue
            if 'action' in decision:
                action = decision['action']; last_id = f'call_{index}'
                function = {'name': action['tool'], 'arguments': action['arguments'] if ollama else json.dumps(action['arguments'])}
                call = {'function': function} if ollama else {'id': last_id, 'type': 'function', 'function': function}
                output.append({'role': 'assistant', 'content': decision.get('message', ''), 'tool_calls': [call]})
            else:
                output.append({'role': 'assistant', 'content': decision.get('message', '')})
        elif message['role'] == 'user' and content.startswith('ACTION RESULT\n'):
            result = json.loads(content.split('\n', 1)[1])
            if last_id is None:
                # A pruned orphan result is useful context, but not a valid API tool response.
                output.append(message)
            else:
                item = {'role': 'tool', 'content': json.dumps(result, ensure_ascii=False)}
                item.update({'tool_name': result['tool']} if ollama else {'tool_call_id': last_id})
                output.append(item); last_id = None
        else:
            output.append(message)
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
    def __init__(self, config, key=""):
        self.config = dict(config)
        self.key = key

    def complete(self, messages, cancel, progress=None, tools=None):
        # Polling a worker lets Stop return promptly even during model loading.
        # A late result is discarded; it cannot run an action in a stopped session.
        result = queue.Queue(maxsize=1)

        def work():
            try:
                result.put((True, self._complete(messages, cancel, progress, tools)))
            except Exception as error:
                result.put((False, error))

        threading.Thread(target=work, daemon=True).start()
        deadline = time.monotonic() + self.config.get("request_timeout", 180)
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
            return value

    def _complete(self, messages, cancel, progress, tools=None):
        config = self.config
        native = config.get('protocol', 'native') == 'native'
        if native and tools is None:
            raise ProviderError('Native inference requires tool definitions supplied by the seed')
        wire = wire_messages(messages, config['provider'] == 'ollama') if native else messages
        validate_context(wire, tools if native else [], config)
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
            text, thinking, done, metrics, calls = "", "", False, {}, []
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
                        if item.get("error"):
                            raise ProviderError(str(item["error"]))
                        text += item.get("message", {}).get("content", "")
                        thinking += item.get("message", {}).get("thinking", "")
                        calls.extend(item.get('message', {}).get('tool_calls', []))
                        if len(calls) > 32:
                            raise ProviderError('The model returned too many tool calls')
                        if progress:
                            progress(len(text))
                        if len(text) + len(thinking) > 300000:
                            raise ProviderError("The model response exceeded the maximum size.")
                        if item.get("done"):
                            done = True
                            metrics = {key: item.get(key) for key in ("prompt_eval_count", "eval_count", "done_reason", "total_duration")}
                            break
                if not done or metrics.get("done_reason") == "length":
                    raise ProviderError("The model response was cut short. No action was executed. Increase the response budget or retry.",
                                        {'raw_content':text, 'thinking':thinking, 'tool_calls':calls, 'usage':metrics, 'incomplete':True}, category='cutoff')
                return model_response(text, calls, native, thinking=thinking, usage=metrics)
            except urllib.error.HTTPError as error:
                raise ProviderError(f"Local model error (HTTP {error.code}): {error.read(2000).decode(errors='replace')}") from None
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                raise ProviderError(f"The local model connection was interrupted: {error}. No partial action was executed.",
                                    {'raw_content':text, 'thinking':thinking, 'tool_calls':calls, 'incomplete':True}) from None
        payload = {"model": config["model"], "messages": wire, "stream": False,
                   "max_tokens": config["response_tokens"], "temperature": config["temperature"]}
        if native:
            payload['tools'] = tools
        if config.get("json_mode") and not native:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": "Bearer " + self.key} if self.key else {}
        data = request_json(base + "/chat/completions", payload, headers, config.get("request_timeout", 180))
        try:
            choice = data["choices"][0]
            if choice.get("finish_reason") not in ("stop", "tool_calls", None):
                raise ProviderError("The model response was cut short or rejected. No action was executed.",
                                    {'raw_content':choice.get('message',{}), 'usage':data.get('usage',{}), 'incomplete':True}, category='cutoff')
            content = choice["message"].get("content") or ""
            if not isinstance(content, str):
                raise ProviderError("The provider did not return a text response.")
            calls = choice['message'].get('tool_calls', [])
            return model_response(content, calls, native, usage=data.get('usage', {}))
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
