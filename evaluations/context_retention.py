"""Opt-in shared context estimator. Pure data handling; safe to copy into a guest.

Provider usage anchors an unchanged prefix. Old trailing plan/runtime metadata
stays charged in the anchor; the current tail is priced again conservatively.
No message is removed, rewritten or granted authority by this helper.
"""
import hashlib
import json


TAILS = ('Current task plan (model-written todo.txt;',
         'Remaining final-task plan after activation (model-written todo.txt;',
         'Runtime notice: The tool action allowance is exhausted.')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':')).encode()).hexdigest()


def neutral_identity(messages):
    return fingerprint([{k: item[k] for k in ('role', 'content')} for item in messages])


class RetentionBudget:
    def __init__(self):
        self.anchor = None
        self.last = None

    @staticmethod
    def scope(messages, tools, config, source=None):
        settings = {k: config.get(k) for k in ('provider', 'model', 'base_url',
            'context_tokens', 'response_tokens', 'protocol', 'thinking', 'temperature')}
        return fingerprint({'settings': settings, 'source': source, 'tools': tools,
            'system': [m for m in messages if m.get('role') == 'system']})

    @staticmethod
    def prefix(messages):
        end = len(messages)
        while end and messages[end - 1].get('role') == 'user' and isinstance(messages[end - 1].get('content'), str) and messages[end - 1]['content'].startswith(TAILS):
            end -= 1
        return [fingerprint(m) for m in messages[:end]]

    def estimate(self, messages, tools, config, source=None):
        size = len(json.dumps({'messages': messages, 'tools': tools or []}, ensure_ascii=False).encode())
        fallback = (size + 1) // 2
        estimate, mode = fallback, 'conservative_fallback'
        anchor = self.anchor
        if anchor and anchor['scope'] != self.scope(messages, tools, config, source):
            self.anchor = anchor = None
        prefix = self.prefix(messages)
        if anchor and anchor['prefix'] and prefix[:len(anchor['prefix'])] == anchor['prefix']:
            # Never subtract old metadata or completion usage. Added history and
            # the current optional tail are charged at the original byte rate.
            added = messages[len(anchor['prefix']):]
            delta = (len(json.dumps(added, ensure_ascii=False).encode()) + 1) // 2 if added else 0
            anchored = anchor['input_tokens'] + delta + 256
            if anchored < fallback:
                estimate, mode = anchored, 'provider_anchor'
        self.last = {'mode': mode, 'estimated_input_tokens': estimate,
            'conservative_input_tokens': fallback, 'messages': len(messages)}
        return estimate

    def observe(self, messages, tools, config, usage, source=None):
        usage = usage if isinstance(usage, dict) else {}
        tokens = next((usage[k] for k in ('prompt_eval_count', 'prompt_tokens', 'input_tokens')
            if type(usage.get(k)) is int and usage[k] > 0), None)
        if tokens is None:
            self.anchor = None
            return False
        self.anchor = {'scope': self.scope(messages, tools, config, source),
            'prefix': self.prefix(messages), 'input_tokens': tokens}
        return True

    def observe_response(self, messages, tools, config, response, source=None):
        receipt = response.get('context_retention', {})
        if (not isinstance(receipt, dict) or receipt.get('neutral_sha256') != neutral_identity(messages)
                or receipt.get('wire_trimmed') is not False or response.get('normalization_error')
                or response.get('provider_error') or response.get('incomplete')):
            self.anchor = None
            return False
        return self.observe(messages, tools, config, response.get('usage'), source)
