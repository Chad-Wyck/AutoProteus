"""Host-owned human input admission and operation recovery receipts."""
import hashlib
import json
import re
import uuid

from .storage import now


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def result_identity(value):
    result = value.get('result')
    if isinstance(result, dict):
        result = {k: v for k, v in result.items() if k != 'progress_hint'}
    return identity({'ok': value.get('ok'), 'result': result})


class Inputs:
    def __init__(self, store, session):
        self.store, self.session = store, session

    def enqueue(self, message, mode, request_id):
        if (not isinstance(message, str) or not message.strip() or len(message) > 12000 or
                mode not in ('steer', 'followup') or not isinstance(request_id, str) or
                not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', request_id)):
            raise ValueError('Choose a message, delivery mode and valid request ID')
        with self.store.lock:
            rows = self.session.setdefault('input_queue', [])
            context = {'session': self.session['id'], 'message': message, 'mode': mode,
                       'seed': self.session.get('selected_seed'), 'model': self.session['model'],
                       'provider': self.session['provider']}
            digest = identity(context)
            previous = next((r for r in rows if r['id'] == request_id), None)
            if previous:
                if previous['payload_sha256'] != digest:
                    raise ValueError('This request ID already belongs to different input or model/seed state')
                return dict(previous)
            if len(rows) >= 200:
                raise ValueError('This session reached its 200 queued-message limit; start a new session')
            if sum(r['status'] in ('pending', 'offered') for r in rows) >= 20:
                raise ValueError('The input queue is full; finish or cancel pending messages first')
            row = {'id': request_id, 'message': message, 'mode': mode, 'status': 'pending',
                   'created': now(), 'payload_sha256': digest, 'context': context}
            rows.append(row)
            self.store.save(self.session)
            self.store.event(self.session, 'host_input_queued', row)
            return dict(row)

    def cancel(self, request_id):
        with self.store.lock:
            row = next((r for r in self.session.get('input_queue', []) if r['id'] == request_id), None)
            if row is None or row['status'] != 'pending':
                raise ValueError('Only a pending message can be cancelled')
            row.update(status='cancelled', cancelled=now())
            self.store.save(self.session)
            self.store.event(self.session, 'host_input_cancelled', {'id': request_id})

    def offer(self, mode):
        with self.store.lock:
            rows = self.session.get('input_queue', [])
            # Previously offered entries survive a crash until their exact text
            # is acknowledged in the saved guest history. Deliver one at a time.
            choices = ('steer', 'followup') if mode == 'finish' else ('steer',)
            for kind in choices:
                row = next((r for r in rows if r['mode'] == kind and r['status'] in ('pending', 'offered')), None)
                if row:
                    row.update(status='offered', offered=now())
                    self.store.save(self.session)
                    self.store.event(self.session, 'host_input_offered', {'id': row['id'], 'mode': kind})
                    return [{'id': row['id'], 'content': row['message']}]
            return []

    def acknowledge(self, messages):
        with self.store.lock:
            for row in self.session.get('input_queue', []):
                if row['status'] == 'offered' and any(
                        m.get('role') == 'user' and m.get('origin') == 'human' and
                        m.get('input_id') == row['id'] and m.get('content') == row['message'] for m in messages):
                    row.update(status='delivered', delivered=now())
                    self.store.event(self.session, 'host_input_delivered', {'id': row['id']})


class Operations:
    """Receipts describe guest reports and committed files, never verified effects.

    No operation is automatically replayed, including a tool named read_file:
    an edited seed can change what that name does.
    """
    def __init__(self, store, session):
        self.store, self.session = store, session
        self.active_id = None

    def current(self):
        rows = self.session.get('operation_receipts', [])
        return rows[-1] if rows else None

    def event(self, kind, data, event_id):
        if kind == 'action_started' and isinstance(data, dict) and isinstance(data.get('tool'), str):
            row = {'id': uuid.uuid4().hex, 'tool': data['tool'], 'action_sha256': identity(data),
                   'started': now(), 'status': 'started', 'event_id': event_id,
                   'seed': self.session.get('selected_seed'), 'messages_before': len(self.session.get('messages', [])),
                   'checkpoint_before': identity(self.session.get('artifacts', {})),
                   'replay': 'inspect_before_retry', 'scope': 'Guest execution report; not independent verification.'}
            rows = self.session.setdefault('operation_receipts', [])
            rows.append(row)
            del rows[:-20]
            self.active_id = row['id']
            self.record(row)
        elif kind == 'action_result' and isinstance(data, dict):
            row = self.current()
            if row and row['id'] == self.active_id and row['status'] == 'started' and identity(data.get('action')) == row['action_sha256']:
                row.update(status='result_reported', result_event_id=event_id,
                    result_sha256=result_identity(data), ok=data.get('ok') is True)
                self.record(row)

    def checkpoint(self):
        row = self.current()
        if row and row['id'] == self.active_id and row['status'] == 'result_reported':
            row.update(status='checkpointed', checkpoint_after=identity(self.session.get('artifacts', {})))
            self.record(row)

    def acknowledge(self, messages):
        row = self.current()
        if not row or row['id'] != self.active_id or row['status'] != 'checkpointed':
            return
        for message in messages[row['messages_before']:]:
            if message.get('origin') != 'tool' or not message.get('content', '').startswith('ACTION RESULT\n'):
                continue
            try:
                value = json.loads(message['content'].split('\n', 1)[1])
                if value.get('tool') == row['tool'] and result_identity(value) == row['result_sha256']:
                    row.update(status='recorded', recorded=now())
                    self.record(row)
                    return
            except (ValueError, TypeError, AttributeError):
                continue

    def record(self, row):
        self.store.save(self.session)
        self.store.event(self.session, 'host_operation_receipt', dict(row))

    def notice(self):
        row = self.current()
        if not row or row['status'] == 'recorded':
            return ''
        return ('RECOVERY STATE\nOperation ' + row['id'] + ' (' + row['tool'] + ') stopped with receipt state ' +
                row['status'] + '. Only the last committed file checkpoint is restored. '
                'A reported result is not independent verification. Inspect current files and recorded results '
                'before deciding whether another action is needed; commands are never automatically replayed.')
