"""Research-only, CPU-testable budgets, deadlines and completion requirements."""
import ctypes
import json
import math
import os
from pathlib import Path
import time

from lora6k_state import atomic, read, sha


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_files(directory, expected):
    root = Path(directory).resolve()
    require(bool(expected), 'Empty integrity inventory')
    for name, digest in expected.items():
        path = (root / name).resolve()
        require(path.is_relative_to(root) and path != root, 'Integrity path escapes root')
        require(sha(path) == digest, 'Integrity mismatch: ' + name)


class Deadline:
    def __init__(self, seconds=None, *, end=None, clock=time.monotonic):
        self.clock = clock
        self.end = clock() + seconds if end is None else end
        require(math.isfinite(self.end), 'Invalid deadline')
        if seconds is not None:
            require(math.isfinite(seconds) and seconds > 0, 'Invalid allowance')

    def remaining(self, reserve=0):
        left = self.end - self.clock() - reserve
        if left <= 0:
            raise TimeoutError('Shared deadline exhausted')
        return left

    def child(self, seconds):
        self.remaining()
        return Deadline(end=min(self.end, self.clock() + seconds), clock=self.clock)


class TokenBudget:
    """Reserve blocks durably BEFORE sampling; charge unknown crash tails.

    A clean settlement fsyncs the journal before releasing unused reservations.
    A killed worker leaves at most one block of uncertain generated tokens. That
    reservation remains charged; a journal tail is never assumed to cost zero.
    """
    def __init__(self, folder, limit, binding, *, block=64):
        require(type(limit) is int and limit >= 0 and type(block) is int and block > 0, 'Invalid token allowance')
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        require(not (self.folder / 'usage.json').exists(), 'Never replay an existing token budget')
        self.state = {'binding': binding, 'limit': limit, 'reserved': 0, 'emitted': 0, 'state': 'open'}
        self.block = block
        self.pending = False
        self.counts = {}
        self.stream = (self.folder / 'tokens.jsonl').open('x', encoding='utf8')
        self.save()

    def save(self):
        atomic(self.folder / 'usage.json', self.state)

    def before_sample(self):
        require(self.state['state'] == 'open' and not self.pending, 'Unresolved sample or closed budget')
        if self.state['emitted'] == self.state['limit']:
            raise RuntimeError('Generated-token allowance exhausted before sampling')
        if self.state['emitted'] == self.state['reserved']:
            self.state['reserved'] = min(self.state['limit'], self.state['reserved'] + self.block)
            self.save()
        self.pending = True

    def record(self, case, token):
        require(self.pending and type(token) is int and token >= 0, 'Token without a reservation')
        index = self.counts.get(case, 0)
        self.stream.write(json.dumps({'case': case, 'index': index, 'token_id': token}) + '\n')
        self.counts[case] = index + 1
        self.state['emitted'] += 1
        self.pending = False
        if self.state['emitted'] % self.block == 0:
            self.stream.flush()

    def settle(self):
        require(not self.pending and self.state['state'] == 'open', 'Cannot settle an unresolved sample')
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.stream.close()
        self.state.update(state='settled', reserved=self.state['emitted'])
        self.save()

    def close(self):
        # Preserve reservations after any error. A close is not a settlement.
        if not self.stream.closed:
            self.stream.close()


def usage(folder, binding):
    folder = Path(folder)
    state = read(folder / 'usage.json')
    require(state['binding'] == binding and state['state'] in ('open', 'settled'), 'Usage binding/state mismatch')
    require(all(type(state.get(k)) is int for k in ('limit', 'reserved', 'emitted')), 'Invalid usage counters')
    require(0 <= state['emitted'] <= state['reserved'] <= state['limit'], 'Invalid reservation')
    raw = (folder / 'tokens.jsonl').read_bytes()
    lines = raw.splitlines(keepends=True)
    tail = bool(lines and not lines[-1].endswith(b'\n'))
    if tail:
        lines = lines[:-1]
    counts = {}
    for line in lines:
        row = json.loads(line)
        require(type(row['token_id']) is int and row['token_id'] >= 0 and row['index'] == counts.get(row['case'], 0), 'Invalid token journal')
        counts[row['case']] = counts.get(row['case'], 0) + 1
    observed = sum(counts.values())
    require(observed <= state['reserved'], 'Journal exceeds reserved quota')
    complete = state['state'] == 'settled'
    if complete:
        require(not tail and observed == state['emitted'] == state['reserved'], 'Settled journal incomplete')
    return {'observed_tokens': observed, 'charged_tokens': state['reserved'], 'measurement_complete': complete,
            'uncertain_tokens_upper_bound': 0 if complete else state['reserved'] - observed,
            'truncated_journal_tail': tail, 'per_case': counts}


def account_before_grading(study, phase, folder, binding):
    """Call before an independent grader: a grader failure cannot erase inference."""
    measured = usage(folder, binding)
    current = read(study) if Path(study).exists() else {'phases': {}}
    require(phase not in current['phases'], 'Inference phase already accounted; no implicit replay')
    current['phases'][phase] = measured
    current['charged_tokens'] = sum(row['charged_tokens'] for row in current['phases'].values())
    current['measurement_complete'] = all(row['measurement_complete'] for row in current['phases'].values())
    atomic(study, current)
    return measured


def alive(pid):
    if os.name != 'nt':
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
    from ctypes import wintypes as w
    dll = ctypes.WinDLL('kernel32', use_last_error=True)
    dll.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
    dll.OpenProcess.restype = w.HANDLE
    dll.WaitForSingleObject.argtypes = [w.HANDLE, w.DWORD]
    dll.CloseHandle.argtypes = [w.HANDLE]
    handle = dll.OpenProcess(0x100000, False, int(pid))
    if not handle:
        error = ctypes.get_last_error()
        if error == 87:
            return False
        raise ctypes.WinError(error)
    try:
        value = dll.WaitForSingleObject(handle, 0)
        require(value in (0, 258), 'Process termination could not be checked')
        return value == 258
    finally:
        dll.CloseHandle(handle)


def completed(folder, *, token=None, is_alive=alive):
    folder = Path(folder)
    closed, result = read(folder / 'CLOSED.json'), read(folder / 'RESULT.json')
    require(closed.get('owned_worker_closed') is True and closed.get('status') == 'completed'
            and closed.get('returncode') == 0 and not closed.get('guard'), 'Missing successful closure')
    require(bool(closed.get('token')) and closed['token'] == result.get('token')
            and (token is None or token == closed['token']), 'Result/closure nonce mismatch')
    require(result.get('status') == 'completed' and result.get('cleanup_complete') is True, 'Incomplete result')
    require(all(type(closed.get(k)) is int and closed[k] > 0 for k in ('launcher_pid', 'worker_pid')), 'Missing process ownership receipts')
    for pid in {closed.get('launcher_pid'), closed.get('worker_pid')} - {None}:
        require(not is_alive(pid), 'Owned process survived closure')
    return result


def completed_phases(root, expected, *, is_alive=alive):
    require(bool(expected) and len(set(expected)) == len(expected), 'Expected phase inventory must be nonempty and unique')
    return {name: completed(Path(root) / name, is_alive=is_alive) for name in expected}


class DuplicateArtifact(ValueError):
    pass


def unique_artifact(digest, existing):
    require(len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'Invalid artifact hash')
    if digest in existing:
        raise DuplicateArtifact('Candidate duplicates an existing artifact after rounding')


def verdict(base, candidate):
    require(bool(base) and len({r['id'] for r in base}) == len(base), 'Empty/duplicate baseline')
    require(len({r['id'] for r in candidate}) == len(candidate)
            and {r['id'] for r in base} == {r['id'] for r in candidate}, 'Mismatched candidate cases')
    require(all(type(r.get('correct')) is bool and r.get('status') == 'ok' for r in base + candidate), 'Ungraded outcome')
    other = {r['id']: r for r in candidate}
    correct = [r for r in base if r['correct']]
    retained = all(other[r['id']]['correct'] for r in correct)
    a = sum(r['generated_tokens'] for r in base)
    b = sum(r['generated_tokens'] for r in candidate)
    gained = retained and sum(r['correct'] for r in candidate) > len(correct)
    matched = [r for r in correct if other[r['id']]['correct']]
    matched_a = sum(r['generated_tokens'] for r in matched)
    matched_b = sum(other[r['id']]['generated_tokens'] for r in matched)
    return {'retention_opportunities': len(correct), 'retained': retained,
            'correctness_improved': gained, 'qualified_quality_gain': bool(correct) and gained,
            'matched_correct_baseline_tokens': matched_a, 'matched_correct_candidate_tokens': matched_b,
            'matched_correct_token_change': matched_b / matched_a - 1 if matched_a else None,
            'total_token_change': b / a - 1 if a else None,
            'efficiency_only_is_quality_pass': False}


class InsufficientCalibration(ValueError):
    pass


def verify_unchanged_bytes(source, candidate, allowed_regions, deadline, *, chunk_bytes=1024*1024):
    """Compare the complete file outside tensor spans using bounded streaming RAM."""
    deadline.remaining()
    source,candidate=Path(source),Path(candidate)
    require(source.resolve()!=candidate.resolve(),'Comparison requires distinct files')
    size=source.stat().st_size
    require(candidate.stat().st_size==size,'Candidate file size changed')
    require(type(chunk_bytes) is int and 0<chunk_bytes<=1024*1024,'Invalid comparison chunk size')
    regions=sorted(allowed_regions);cursor=0
    for offset,length in regions:
        require(type(offset) is int and type(length) is int and offset>=cursor and length>0 and offset+length<=size,
                'Invalid/overlapping allowed byte region')
        cursor=offset+length
    compared=0;cursor=0
    with source.open('rb') as left,candidate.open('rb') as right:
        for offset,length in regions+[(size,0)]:
            left.seek(cursor);right.seek(cursor);remaining=offset-cursor
            while remaining:
                deadline.remaining();count=min(remaining,chunk_bytes)
                a,b=left.read(count),right.read(count)
                require(len(a)==len(b)==count and a==b,'Bytes outside permitted tensor regions changed')
                compared+=count;remaining-=count
                del a,b
            cursor=offset+length
    deadline.remaining()
    return {'compared_bytes':compared,'permitted_bytes':size-compared,'maximum_buffer_bytes':2*chunk_bytes,
            'headers_padding_and_other_tensors_unchanged':True}


def calibration_split(rows):
    """Preregistered baseline stratification, performed once before any editing."""
    require(len(rows) == 8 and len({r['id'] for r in rows}) == 8, 'Expected the fixed eight-case calibration pool')
    require(all(r.get('status') == 'ok' and type(r.get('correct')) is bool for r in rows), 'Calibration incomplete')
    yes = sorted(r['id'] for r in rows if r['correct'])
    no = sorted(r['id'] for r in rows if not r['correct'])
    if len(yes) < 2 or len(no) < 2:
        raise InsufficientCalibration('Calibration lacks two correct and two incorrect cases; stop without expanding pool')
    return {'development': [yes[0], no[0]], 'confirmation': [yes[1], no[1]],
            'unused_calibration': sorted({r['id'] for r in rows} - {yes[0], no[0], yes[1], no[1]}),
            'baseline_stratified': True, 'editor_may_see': [yes[0], no[0]]}
