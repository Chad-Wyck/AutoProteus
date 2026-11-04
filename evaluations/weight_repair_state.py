"""Transactional offline research records and pure resource-policy controls."""
import math
import os
from pathlib import Path
import random
import re
import uuid

from lora6k_state import atomic, identity, inside, read, sha
from weight_repair_protocol import extract_answer


GUARDS = {'admission_ram_bytes': 8 * 2**30, 'admission_vram_bytes': 8 * 2**30,
    'admission_disk_bytes': 20 * 2**30, 'idle_observations': 3, 'max_idle_gpu_percent': 5,
    'running_ram_bytes': 6 * 2**30, 'commit_bytes': 4 * 2**30,
    'running_disk_bytes': 5 * 2**30, 'shared_gpu_bytes': 512 * 2**20,
    'sample_interval_seconds': 5, 'request_seconds': 2700,
    'readiness_seconds': 7200, 'pilot_seconds': 28800}


def guard_reason(sample, *, phase_seconds, request_seconds, phase_limit, admission=False):
    """External supervisor policy, tested without touching GPU/resource APIs."""
    keys = ('ram_bytes', 'vram_bytes', 'disk_bytes', 'commit_bytes', 'shared_gpu_bytes', 'gpu_percent')
    if (any(type(sample.get(k)) not in (int, float) or not math.isfinite(sample[k]) or sample[k] < 0 for k in keys)
            or any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
                   for v in (phase_seconds, request_seconds, phase_limit)) or phase_limit <= 0):
        return 'resource_counters_unavailable'
    if phase_seconds >= phase_limit: return 'cumulative_deadline'
    if request_seconds >= GUARDS['request_seconds']: return 'request_deadline'
    checks = [('ram_bytes', GUARDS['admission_ram_bytes'] if admission else GUARDS['running_ram_bytes'], 'ram_floor'),
              ('disk_bytes', GUARDS['admission_disk_bytes'] if admission else GUARDS['running_disk_bytes'], 'disk_floor'),
              ('commit_bytes', GUARDS['commit_bytes'], 'commit_floor')]
    if admission: checks.append(('vram_bytes', GUARDS['admission_vram_bytes'], 'vram_admission'))
    for key, floor, reason in checks:
        if sample[key] < floor: return reason
    if sample['shared_gpu_bytes'] > GUARDS['shared_gpu_bytes']: return 'shared_gpu_allowance'
    if admission and sample['gpu_percent'] > GUARDS['max_idle_gpu_percent']: return 'gpu_busy'
    return None


class Receipts:
    """A committed directory is the sole authority; abandoned staging is inert.

    No request launcher is included. A future executor must hold the run's
    exclusive lock, keep interrupted attempts and request explicit replay.
    """
    def __init__(self, run, binding, slots):
        self.root = Path(run) / 'records'; self.binding = binding
        self.slots = {slot['id']: slot for slot in slots}
        if (len(self.slots) != len(slots) or
                any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', name) for name in self.slots)):
            raise ValueError('Invalid or duplicate scheduled request')

    def records(self):
        result = {}
        if not self.root.exists(): return result
        for folder in sorted(self.root.iterdir()):
            if not folder.is_dir() or folder.name.startswith('.staging-'): continue
            if folder.name not in self.slots: raise ValueError('Unknown committed request')
            receipt = read(folder / 'COMMITTED.json')
            payload = folder / 'response.json'
            if (receipt.get('binding') != self.binding or receipt.get('slot') != self.slots[folder.name]
                    or sha(payload) != receipt.get('response_sha256')):
                raise ValueError('Mismatched or corrupt committed request')
            value = read(payload); self.validate(value)
            result[folder.name] = value
        return result

    @staticmethod
    def validate(value):
        if (value.get('status') not in ('completed', 'interrupted', 'resource_stop', 'grader_error')
                or type(value.get('elapsed_seconds')) not in (int, float)
                or not math.isfinite(value['elapsed_seconds']) or value['elapsed_seconds'] < 0):
            raise ValueError('Invalid request status or elapsed allowance')
        if value['status'] == 'completed':
            ids, finish = value.get('token_ids'), value.get('finish_reason')
            if (not isinstance(ids, list) or not ids or len(ids) > 32768
                    or any(type(t) is not int or t < 0 for t in ids)
                    or finish not in ('eos', 'length') or (finish == 'length' and len(ids) != 32768)
                    or not isinstance(value.get('text'), str) or type(value.get('correct')) is not bool):
                raise ValueError('Incomplete generation or grade cannot be a completed observation')
            omitted = extract_answer(value['text']) is None
            if (omitted and value['correct']) or value.get('answer_omitted', omitted) != omitted:
                raise ValueError('Saved correctness/omission contradicts the response')
        elif value.get('correct') is not None:
            raise ValueError('Infrastructure stop is not a wrong-answer measurement')

    def commit(self, slot_id, value):
        if slot_id not in self.slots: raise ValueError('Unknown request')
        self.validate(value)
        self.root.mkdir(parents=True, exist_ok=True)
        final = inside(self.root, slot_id)
        if final.exists(): raise ValueError('Request already recorded; no implicit replay')
        staging = self.root / ('.staging-' + uuid.uuid4().hex); staging.mkdir()
        atomic(staging / 'response.json', value)
        atomic(staging / 'COMMITTED.json', {'binding': self.binding, 'slot': self.slots[slot_id],
                                         'response_sha256': sha(staging / 'response.json')})
        os.rename(staging, final)


def interval(values, seed=20261102):
    """Problem-cluster bootstrap; values already average samples within problem."""
    if len(values) < 2: return None
    rng = random.Random(seed)
    draws = sorted(sum(rng.choices(values, k=len(values))) / len(values) for _ in range(2000))
    return [draws[49], draws[1949]]


def summarize(slots, records):
    arms = {}
    for arm in ('base', 'edited'):
        scheduled = [s for s in slots if s['arm'] == arm]
        completed = [(s, records[s['id']]) for s in scheduled if s['id'] in records and records[s['id']]['status'] == 'completed']
        clusters = {}
        for slot, value in completed: clusters.setdefault(slot['problem_rank'], []).append(int(value['correct']))
        values = [sum(v) / len(v) for v in clusters.values()]
        arms[arm] = {'scheduled': len(scheduled), 'completed': len(completed),
            'missing': sum(s['id'] not in records for s in scheduled),
            'infrastructure_observations': sum(s['id'] in records and records[s['id']]['status'] != 'completed' for s in scheduled),
            'accuracy_observed_samples': sum(int(v['correct']) for _, v in completed) / len(completed) if completed else None,
            'problem_cluster_interval': interval(values), 'interval_cluster_count': len(values),
            'cutoff_share_observed': sum(v['finish_reason'] == 'length' for _, v in completed) / len(completed) if completed else None,
            'generated_tokens_observed': sum(len(v['token_ids']) for _, v in completed),
            'charged_seconds_all_records': sum(records[s['id']]['elapsed_seconds'] for s in scheduled if s['id'] in records),
            'complete_coverage': len(completed) == len(scheduled),
            'answer_omissions': sum(extract_answer(v['text']) is None for _, v in completed)}
        for name in ('ttft_seconds', 'generation_seconds', 'sampled_peak_ram_bytes', 'sampled_peak_vram_bytes'):
            measured = [v[name] for _, v in completed if type(v.get(name)) in (int, float)
                        and math.isfinite(v[name]) and v[name] >= 0]
            arms[arm][name] = {'observations': len(measured), 'complete': bool(completed) and len(measured) == len(completed),
                'mean_observed': sum(measured) / len(measured) if measured else None,
                'maximum_observed': max(measured) if measured else None}
    pairs = {}
    for slot in slots:
        value = records.get(slot['id'])
        if value and value['status'] == 'completed':
            pairs.setdefault((slot['problem_rank'], slot['sample']), {})[slot['arm']] = value
    matched = [p for p in pairs.values() if set(p) == {'base', 'edited'}]
    deltas = {}
    for (rank, _), pair in pairs.items():
        if set(pair) == {'base', 'edited'}:
            deltas.setdefault(rank, []).append(int(pair['edited']['correct']) - int(pair['base']['correct']))
    return {'arms': arms, 'matched_samples': len(matched),
        'paired_problem_cluster_delta_interval': interval([sum(v) / len(v) for v in deltas.values()]),
        'paired_gains': sum(not p['base']['correct'] and p['edited']['correct'] for p in matched),
        'paired_regressions': sum(p['base']['correct'] and not p['edited']['correct'] for p in matched),
        'ap_qualification': False, 'discovery_reproduced': False,
        'scope': 'Observed samples only; missing/infrastructure slots remain visible. No pass@k scoring.'}
