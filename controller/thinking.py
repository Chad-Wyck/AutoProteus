"""Bounded, host-owned reasoning previews; never part of the model's prompt."""
import json
import threading
import time
import uuid

from .storage import now


class Thinking:
    def __init__(self, store, session, cancel, key='', enabled=None):
        self.store, self.session, self.cancel, self.key = store, session, cancel, key
        self.lock = threading.Lock()
        self.started = time.monotonic()
        self.saved = self.started
        self.closed = False
        self.latest = ''
        self.item = {'id':'thinking-' + uuid.uuid4().hex, 'time':now(), 'state':'running',
                     'after':session['feed'][-1]['id'] if session['feed'] else None,
                     'text':'', 'enabled':enabled, 'seconds':0, 'shortened':False}
        with store.lock:
            rows = session.setdefault('thinking_spans', [])
            rows.append(self.item)
            del rows[:-200]
            store.save(session)

    def __call__(self, characters):
        pass  # Preserve the provider's existing numeric progress callback.

    def thinking(self, text):
        if not isinstance(text, str):
            return
        with self.lock:
            if self.closed or self.cancel.is_set():
                return
            if self.key:
                text = text.replace(self.key, '[REDACTED]').replace(
                    json.dumps(self.key, ensure_ascii=False)[1:-1], '[REDACTED]')
            self.latest = text[:64000]
            self.item['shortened'] = len(text) > 64000
            if time.monotonic()-self.saved >= .5:
                self._save()

    def _save(self):
        with self.store.lock:
            self.item.update(text=self.latest, seconds=round(time.monotonic()-self.started, 1))
            remaining = 256000
            for row in reversed(self.session['thinking_spans']):
                text = row['text']
                if len(text) > remaining:
                    row.update(text=text[:remaining], shortened=True)
                remaining -= len(row['text'])
            self.store.save(self.session)
            self.saved = time.monotonic()

    def finish(self, state):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.item['state'] = state
            self._save()
