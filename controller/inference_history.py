"""Content-addressed provider evidence, independent of the editable seed."""
import hashlib
import json
from copy import deepcopy

from .artifacts import safe_path
from .storage import atomic_json

LIMIT = 64 * 1024 * 1024


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


class InferenceHistory:
    def __init__(self, store, session, config):
        self.store, self.session = store, session
        self.source = deepcopy(session.get('selected_seed'))
        self.profile = {key: config.get(key) for key in ('provider', 'model', 'protocol', 'context_tokens',
            'response_tokens', 'temperature', 'thinking', 'json_mode', 'api_format', 'reasoning_effort')}
        self.failed = False

    def blob(self, value):
        with self.store.lock:
            return self._blob(value)

    def _blob(self, value):
        root = safe_path(self.store.directory(self.session['id']), 'inference')
        root.mkdir(exist_ok=True)
        key = digest(value)
        path = safe_path(root, key + '.json')
        if not path.exists():
            size = len(json.dumps(value, ensure_ascii=False, indent=2).encode())
            if sum(p.stat().st_size for p in root.glob('*.json')) + size > LIMIT:
                raise ValueError('Inference history reached its 64 MiB storage allowance')
            atomic_json(path, value)
        elif digest(json.loads(path.read_text(encoding='utf-8'))) != key:
            raise ValueError('Inference history blob identity mismatch')
        return key

    def __call__(self, event):
        # ModelClient redacts credentials before observers see these values.
        try:
            kind, data = event['type'], event['data']
            common = {'call_id': event['call_id'], 'elapsed_seconds': event['elapsed_seconds'],
                      'seed': self.source, 'profile': self.profile}
            if kind == 'provider_request':
                payload = data['payload']
                messages = payload.get('messages', payload.get('input', []))
                state = {'tools': payload.get('tools', []),
                         'tools_present': 'tools' in payload,
                         'instructions': [m for m in messages if m.get('role') in ('system', 'developer')],
                         'profile': self.profile, 'seed': common['seed']}
                state_id = self.blob(state)
                references = [self.blob(message) for message in messages]
                options = {k: v for k, v in payload.items() if k not in ('messages', 'input', 'tools')}
                self.store.event(self.session, 'host_inference_request', {**common, 'state': state_id,
                    'messages': references, 'options': options, 'identity_format': 'SHA-256 of canonical JSON',
                    'input_format': 'responses' if 'input' in payload else 'chat-completions',
                    'scope': 'Actual provider payload; declarations are data, not host permissions.'})
            elif kind == 'provider_response':
                self.store.event(self.session, 'host_inference_response', {**common, 'response': self.blob(data)})
            elif kind in ('call_start', 'context_trimmed', 'call_end', 'transport_end'):
                value = {k: v for k, v in data.items() if k != 'content'}
                self.store.event(self.session, 'host_inference_' + kind, {**common, **value})
        except (OSError, ValueError, KeyError, TypeError) as error:
            if not self.failed:
                self.failed = True
                self.store.event(self.session, 'host_inference_history_incomplete', {'reason': str(error)[:200]})


def attach_history(client, store, session, config):
    previous = getattr(client.observer, '_original_observer', client.observer)
    recorder = InferenceHistory(store, session, config)
    def observe(event):
        try:
            recorder(event)
        finally:
            # A diagnostic failure must never suppress resource accounting or
            # another observer's evidence of a request already being sent.
            if previous:
                previous(event)
    observe._original_observer = previous
    client.observer = observe
    return recorder
