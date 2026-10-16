"""Experimental usage anchor, shared as source by the guest and trusted study client."""
import hashlib
import json
import math


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


class UsageBudget:
    def __init__(self):
        self.anchor = None
        self.decisions = []

    @staticmethod
    def scope(messages, tools, config):
        settings = {key: config.get(key) for key in ('provider', 'model', 'base_url', 'context_tokens',
                    'response_tokens', 'protocol', 'thinking', 'temperature')}
        return hashlib.sha256(encoded({'settings': settings, 'tools': tools,
            'system': [item for item in messages if item['role'] == 'system']})).hexdigest()

    def estimate(self, messages, tools, config):
        # Match the existing fallback exactly, including its JSON spacing.
        size = len(json.dumps({'messages': messages, 'tools': tools or []}, ensure_ascii=False).encode())
        fallback = (size + 1) // 2
        estimate, mode = fallback, 'conservative_fallback'
        prefix = [hashlib.sha256(encoded(item)).hexdigest() for item in messages]
        scope = self.scope(messages, tools, config)
        anchor = self.anchor
        if anchor and anchor['scope'] == scope and prefix[:len(anchor['prefix'])] == anchor['prefix']:
            # Price newly appended material conservatively; do not double-count
            # completion usage, since its serialized assistant message is here.
            added = messages[len(anchor['prefix']):]
            delta = (len(json.dumps(added, ensure_ascii=False).encode()) + 1) // 2 if added else 0
            observed = anchor['input_tokens'] + delta + 256
            if observed < fallback:
                estimate, mode = observed, 'provider_anchor'
        self.decisions.append({'mode': mode, 'estimated_input_tokens': estimate,
                               'fallback_input_tokens': fallback, 'messages': len(messages)})
        self.decisions = self.decisions[-1000:]
        return estimate

    def observe(self, messages, tools, config, usage):
        usage = usage if isinstance(usage, dict) else {}
        value = usage.get('prompt_eval_count', usage.get('prompt_tokens', usage.get('input_tokens')))
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            self.anchor = None
            return False
        self.anchor = {'scope': self.scope(messages, tools, config), 'input_tokens': math.ceil(value),
                       'prefix': [hashlib.sha256(encoded(item)).hexdigest() for item in messages]}
        return True
