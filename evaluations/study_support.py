"""Host-side experiment bookkeeping. Never imports or executes candidate source."""
from contextlib import contextmanager
import copy
import hashlib
import json
from pathlib import Path
import re
import time

from controller.storage import atomic_json, now


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


def file_identity(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class Timings:
    def __init__(self):
        self.seconds = {}

    @contextmanager
    def measure(self, phase):
        started = time.monotonic()
        try:
            yield
        finally:
            self.seconds[phase] = round(self.seconds.get(phase, 0) + time.monotonic() - started, 6)


class ResultCache:
    """Reuse observations with exact identities, keeping their original provenance.

    Callers must explicitly decide eligibility. This does not turn a cached result
    into a fresh execution, an independent repetition, or a model capability score.
    """
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def run(self, inputs, execute, eligible=lambda result: True):
        key = identity(inputs)
        path = self.directory / (key + '.json')
        try:
            saved = json.loads(path.read_text(encoding='utf-8'))
            if (saved['inputs'] == inputs and saved['result_sha256'] == identity(saved['result']) and
                    eligible(saved['result'])):
                return copy.deepcopy(saved['result']), {'hit': True, 'key': key,
                    'origin': saved['origin'], 'original_seconds': saved['seconds']}
        except (OSError, ValueError, KeyError, TypeError):
            pass
        started = time.monotonic()
        result = execute()
        receipt = {'hit': False, 'key': key, 'origin': now(),
                   'original_seconds': round(time.monotonic() - started, 6)}
        if eligible(result):
            atomic_json(path, {'inputs': inputs, 'result': result, 'result_sha256': identity(result),
                              'origin': receipt['origin'], 'seconds': receipt['original_seconds']})
        return result, receipt


class StudyQueue:
    """Durable serial cells; a launched attempt is never silently retried."""
    def __init__(self, directory, plan_sha256):
        self.directory = Path(directory)
        self.path = self.directory / 'queue.json'
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding='utf-8'))
            if self.data.get('plan_sha256') != plan_sha256:
                raise ValueError('Queue belongs to a different frozen plan')
            # A process may have exited without writing its terminal record.
            for attempts in self.data['cells'].values():
                for attempt in attempts:
                    if attempt['state'] == 'running':
                        attempt.update(state='interrupted', finished=now(),
                                       detail='Runner exited before recording completion; not automatically retried.')
            self.save()
        else:
            self.data = {'plan_sha256': plan_sha256, 'created': now(), 'cells': {}}
            self.save()

    def save(self):
        atomic_json(self.path, self.data)

    def latest(self, cell):
        attempts = self.data['cells'].get(cell, [])
        return copy.deepcopy(attempts[-1]) if attempts else None

    def run(self, cell, execute, retry=False):
        if not re.fullmatch(r'[a-z0-9_-]{1,160}', cell):
            raise ValueError('Invalid study cell ID')
        attempts = self.data['cells'].setdefault(cell, [])
        if attempts and attempts[-1]['state'] != 'not_run' and (attempts[-1]['state'] == 'completed' or not retry):
            return copy.deepcopy(attempts[-1])
        number = max((item['attempt'] for item in attempts), default=0) + 1
        folder = self.directory / 'trials' / cell / ('attempt-%03d' % number)
        folder.mkdir(parents=True, exist_ok=False)
        row = {'cell': cell, 'attempt': number, 'state': 'running',
               'folder': str(folder), 'started': now()}
        attempts.append(row)
        self.save()  # Persist launch before any inference or candidate execution.
        try:
            row['result'] = execute(folder)
            row.update(state='completed', finished=now())
        except BaseException as error:
            row.update(state='interrupted' if isinstance(error, (KeyboardInterrupt, SystemExit)) else 'error',
                       finished=now(), detail=type(error).__name__ + ': ' + str(error))
            raise
        finally:
            self.save()
        return copy.deepcopy(row)

    def skip(self, cell, reason):
        if cell not in self.data['cells']:
            self.data['cells'][cell] = [{'cell': cell, 'attempt': 0, 'state': 'not_run', 'reason': reason}]
            self.save()

    def summary(self):
        rows = [row for attempts in self.data['cells'].values() for row in attempts]
        return {'launched_attempts': sum(row['attempt'] > 0 for row in rows),
                'completed_attempts': sum(row['state'] == 'completed' for row in rows),
                'interrupted_or_error_attempts': sum(row['state'] in ('interrupted', 'error') for row in rows),
                'unresolved_cells': [cell for cell, rows in self.data['cells'].items()
                                     if rows[-1]['state'] in ('interrupted', 'error')],
                'not_run': sum(row['state'] == 'not_run' for row in rows)}
