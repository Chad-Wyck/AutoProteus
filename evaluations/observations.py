"""Opt-in host diagnostics and offline metrics; no candidate code is executed."""
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path
import threading


class CallRecorder:
    def __init__(self, path, limit=32 * 1024 * 1024, labels=None):
        self.path, self.limit = Path(path), limit
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.bytes = self.records = self.dropped = 0
        self.error = None
        self.labels = dict(labels or {})
        # A recorder never appends a new trial to an existing trace.
        self.path.open('x', encoding='utf-8').close()

    def __call__(self, record):
        try:
            raw = (json.dumps({'labels': self.labels, **record}, ensure_ascii=False, separators=(',', ':')) + '\n').encode()
            with self.lock:
                if self.error or self.bytes + len(raw) > self.limit:
                    self.dropped += 1
                    return
                with self.path.open('ab') as stream:
                    stream.write(raw)
                self.bytes += len(raw)
                self.records += 1
        except Exception as error:
            self.error = type(error).__name__

    def summary(self):
        with self.lock:
            return {'records': self.records, 'bytes': self.bytes, 'dropped': self.dropped,
                    'error': self.error, 'complete': not self.dropped and self.error is None}


def read_events(path):
    path = Path(path)
    events = []
    for number, line in enumerate(path.read_bytes().splitlines() if path.exists() else [], 1):
        try:
            events.append(json.loads(line))
        except ValueError:
            events.append({'type': 'capture_read_error', 'data': {'line': number}})
    return events


def navigation_metrics(events):
    """Coverage is conservative: writes and commands invalidate prior intervals."""
    coverage = {}
    total = overlap = reads = searches = outlines = source_edits = context_bytes = 0
    first_edit = first_green = last_green = None
    after_green = reads_after_green = edits_after_green = 0
    started = next((item['time'] for item in events if item['type'] == 'run_started'), None)
    def seconds(value):
        return round((datetime.fromisoformat(value) - datetime.fromisoformat(started)).total_seconds(), 3) if started else None
    for event in events:
        if event['type'] != 'action_result':
            continue
        data = event.get('data', {})
        if not isinstance(data, dict) or not isinstance(data.get('action'), dict):
            continue
        action, result = data.get('action', {}), data.get('result', {})
        name, args = action.get('tool'), action.get('arguments', {})
        if not isinstance(args, dict):
            continue
        path = args.get('path', '')
        if last_green is not None:
            after_green += 1
        if not data.get('ok'):
            continue
        if name in ('read_file', 'read_section', 'search_files', 'source_outline'):
            context_bytes += len(json.dumps(result, ensure_ascii=False).encode())
        if name == 'source_outline':
            outlines += 1
        if name in ('write_file', 'edit_file', 'delete_file'):
            coverage.pop(path, None)
            if path.startswith('harness/') and path.endswith('.py') and not path.startswith('harness/tests/'):
                source_edits += 1
                first_edit = first_edit if first_edit is not None else seconds(event['time'])
                if last_green is not None:
                    edits_after_green += 1
        if name == 'run_command':
            coverage.clear()  # Commands may rewrite arbitrary workspace source.
            for line in result.get('output', '').splitlines() if isinstance(result, dict) else []:
                try:
                    check = json.loads(line)
                except ValueError:
                    continue
                if (isinstance(check, dict) and check.get('check') == 'candidate tests' and
                        check.get('passed') is True and check.get('tests', 0) > 0 and result.get('exit_code') == 0):
                    last_green = seconds(event['time'])
                    first_green = first_green if first_green is not None else last_green
                    after_green = reads_after_green = edits_after_green = 0
        if name == 'search_files':
            searches += 1
        if name in ('read_file', 'read_section') and isinstance(result, dict) and isinstance(result.get('content'), str):
            reads += 1
            if last_green is not None:
                reads_after_green += 1
            start = result.get('start', 0)
            if type(start) is not int or start < 0:
                continue
            end = start + len(result['content'])
            old = coverage.setdefault(path, [])
            total += end - start
            overlap += sum(max(0, min(end, b) - max(start, a)) for a, b in old)
            merged = []
            for a, b in sorted(old + [(start, end)]):
                if merged and a <= merged[-1][1]:
                    merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
                else:
                    merged.append((a, b))
            coverage[path] = merged
    return {'read_actions': reads, 'search_actions': searches, 'outline_actions': outlines,
            'returned_context_bytes': context_bytes, 'read_characters': total,
            'overlapping_read_characters': overlap, 'new_read_characters': total - overlap,
            'first_runtime_source_edit_seconds': first_edit, 'runtime_source_edits': source_edits,
            'first_green_development_check_seconds': first_green, 'last_green_development_check_seconds': last_green,
            'actions_after_last_green_check': after_green, 'reads_after_last_green_check': reads_after_green,
            'runtime_edits_after_last_green_check': edits_after_green,
            'scope': 'Observed file tools only; commands invalidate coverage. Green checks are diagnostic, not independent approval.'}


def measurement(values, expected, complete):
    """Known sums remain usable as partial evidence, never as complete costs."""
    complete = bool(complete and len(values) == expected)
    return {'known_sum': sum(values) if values else 0 if complete else None,
            'measured_calls': len(values), 'expected_calls': expected, 'complete': complete,
            'status': 'complete' if complete else 'partial' if values else 'unavailable'}


def call_metrics(events):
    kinds = Counter(item['type'] for item in events)
    grouped = {kind: [item for item in events if item['type'] == kind] for kind in
               ('call_start', 'provider_request', 'provider_response', 'call_end', 'transport_end')}
    indexes, valid_ids = {}, True
    for kind, rows in grouped.items():
        ids = [item.get('call_id') for item in rows]
        good = [value for value in ids if isinstance(value, str) and value]
        valid_ids = valid_ids and len(good) == len(rows) == len(set(good))
        indexes[kind] = set(good)
    trace_complete = bool(not kinds['capture_read_error'] and valid_ids and
        indexes['call_start'] == indexes['call_end'] == indexes['transport_end'] and
        indexes['provider_request'] <= indexes['call_start'] and
        indexes['provider_response'] <= indexes['provider_request'])
    finished = grouped['call_end']
    if any(item['data'].get('status') == 'returned' and isinstance(item.get('call_id'), str) and item.get('call_id') in indexes['provider_request'] and
           item.get('call_id') not in indexes['provider_response'] for item in finished):
        trace_complete = False
    # Keep one observed terminal row per ID. Duplicates invalidate completeness
    # and cannot inflate the known sums. Legacy rows without IDs remain partial.
    unique, seen = [], set()
    for index, item in enumerate(finished):
        value = item.get('call_id')
        identity = value if isinstance(value, str) and value else ('unidentified', index)
        if identity not in seen:
            unique.append(item)
            seen.add(identity)
    def reported(keys):
        values, measured_ids = [], set()
        for item in unique:
            usage = item['data'].get('usage', {})
            if isinstance(usage, dict):
                value = next((usage[key] for key in keys if type(usage.get(key)) is int and usage[key] >= 0), None)
                if value is not None:
                    values.append(value)
                    identity = item.get('call_id')
                    if isinstance(identity, str):
                        measured_ids.add(identity)
        # No wire request means no inference token charge (e.g. local validation
        # rejection). A sent request lacking usage stays unknown, even on error.
        return measurement(values, kinds['provider_request'], trace_complete and
                           measured_ids == indexes['provider_request'])
    def timing(rows):
        values = [item['elapsed_seconds'] for item in rows if
            type(item.get('elapsed_seconds')) in (int, float) and math.isfinite(item['elapsed_seconds']) and item['elapsed_seconds'] >= 0]
        result = measurement(values, kinds['call_start'], trace_complete)
        if result['known_sum'] is not None:
            result['known_sum'] = round(result['known_sum'], 3)
        return result
    metrics = {'input_tokens': reported(('prompt_eval_count', 'prompt_tokens', 'input_tokens')),
               'output_tokens': reported(('eval_count', 'completion_tokens', 'output_tokens')),
               'call_seconds': timing(unique), 'transport_seconds': timing(grouped['transport_end'])}
    return {'calls': kinds['call_start'], 'wire_requests': kinds['provider_request'],
            'trace_complete': trace_complete, 'measurements': metrics,
            'trace_read_errors': kinds['capture_read_error'],
            'finished_calls': len(finished), 'transport_finished_calls': kinds['transport_end'],
            'provider_responses': kinds['provider_response'],
            'statuses': dict(Counter(item['data']['status'] for item in finished)),
            'error_categories': dict(Counter(item['data']['category'] for item in finished if 'category' in item['data'])),
            'token_usage_measured_calls': metrics['input_tokens']['measured_calls'],
            'output_token_usage_measured_calls': metrics['output_tokens']['measured_calls'],
            **{name: value['known_sum'] for name, value in metrics.items()},
            'host_history_omissions': [item['data'].get('context', {}).get('host_history_messages_omitted')
                                      for item in events if item['type'] == 'call_start']}


def latency_metrics(events):
    """Extract server timings, never infer cache hits from total input tokens.

    Ollama reports nanoseconds; llama-server reports milliseconds. Missing fields
    remain partial measurements. Nonstreaming transport cannot measure true TTFT.
    """
    calls = call_metrics(events)
    names = ('model_load_seconds', 'prompt_processing_seconds', 'generation_seconds', 'cached_input_tokens')
    values = {name: [] for name in names}
    seen = set()
    for event in events:
        key = event.get('call_id')
        if event['type'] != 'provider_response' or not isinstance(key, str) or key in seen:
            continue
        seen.add(key)
        data = event.get('data', {})
        frames = data.get('frames', [])
        payload = next((frame for frame in reversed(frames) if isinstance(frame, dict) and frame.get('done')),
                       data.get('payload', {}))
        if not isinstance(payload, dict):
            continue
        timing = payload.get('timings') or {}
        usage = payload.get('usage') or {}
        details = usage.get('prompt_tokens_details') or {} if isinstance(usage, dict) else {}
        for name, raw in (('model_load_seconds', payload.get('load_duration')),
                          ('prompt_processing_seconds', payload.get('prompt_eval_duration')),
                          ('generation_seconds', payload.get('eval_duration'))):
            if type(raw) in (int, float) and math.isfinite(raw) and raw >= 0:
                values[name].append(raw / 1e9)
        for name, key_ms in (('prompt_processing_seconds', 'prompt_ms'), ('generation_seconds', 'predicted_ms')):
            # Prefer a provider's native nanosecond field if both exist.
            native = 'prompt_eval_duration' if name == 'prompt_processing_seconds' else 'eval_duration'
            raw = timing.get(key_ms) if isinstance(timing, dict) else None
            if payload.get(native) is None and type(raw) in (int, float) and math.isfinite(raw) and raw >= 0:
                values[name].append(raw / 1000)
        cached = details.get('cached_tokens') if isinstance(details, dict) else None
        if type(cached) is int and cached >= 0:
            values['cached_input_tokens'].append(cached)
    metrics = {name: measurement(items, calls['wire_requests'], calls['trace_complete'])
               for name, items in values.items()}
    for name in names[:-1]:
        if metrics[name]['known_sum'] is not None:
            metrics[name]['known_sum'] = round(metrics[name]['known_sum'], 6)
    return {'measurements': metrics, 'time_to_first_token': None,
            'scope': 'Provider-reported phases only; unknown timings and cache hits are not zero.'}
