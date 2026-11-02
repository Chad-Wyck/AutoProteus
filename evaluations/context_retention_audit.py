"""Read-only context accounting from closed local studies; no inference or recovery.

    python evaluations/context_retention_audit.py --study .data/CLOSED_STUDY --output .data/NEW_AUDIT.json

Only serialized records are read. Candidate source is never imported, tokenized
or executed, and no session loader is called. Output contains counts, not prompts.
"""
import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def events(path):
    with Path(path).open(encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def size(messages, tools):
    # Match both current seed and protected provider's conservative estimator.
    return len(json.dumps({'messages': messages, 'tools': tools or []}, ensure_ascii=False).encode())


def audit_calls(records, config, selected=None):
    selected = selected or {}
    calls = {}
    for event in records:
        identity = event.get('call_id')
        if not isinstance(identity, str) or not identity:
            continue
        row = calls.setdefault(identity, {'call_id': identity, 'wire_trim_events': 0,
                                         'removed_wire_exchanges': 0})
        data = event.get('data', {})
        if event['type'] == 'call_start':
            context = data.get('context', {})
            row.update(host_history_messages=context.get('host_history_messages'),
                host_signature_mismatches=context.get('host_history_messages_omitted'),
                neutral_message_count=context.get('neutral_message_count'))
        elif event['type'] == 'context_trimmed':
            row['wire_trim_events'] += 1
            row['removed_wire_exchanges'] += data.get('removed_tool_exchanges', 0)
        elif event['type'] == 'provider_request':
            payload = data.get('payload', {})
            messages = payload.get('messages')
            if not isinstance(messages, list):
                row['unsupported_wire_format'] = True  # Responses envelopes require a different estimator.
                continue
            tools = payload.get('tools', [])
            response = payload.get('max_tokens', payload.get('options', {}).get('num_predict', config['response_tokens']))
            row.update(wire_messages=len(messages), wire_bytes=size(messages, tools),
                response_tokens=response,
                input_allowance_tokens=max(0, config['context_tokens'] - response - 128))
            row['conservative_wire_tokens'] = (row['wire_bytes'] + 1) // 2
            if identity in selected:
                observation = selected[identity]
                row['seed_selected_messages'] = len(observation['messages'])
                row['seed_selected_bytes'] = size(observation['messages'], tools)
                row['handoff'] = observation.get('handoff')
        elif event['type'] == 'provider_response':
            payload = data.get('payload', {})
            frames = data.get('frames', [])
            final = next((f for f in reversed(frames) if isinstance(f, dict) and f.get('done')), {})
            usage = payload.get('usage') or {}
            count = final.get('prompt_eval_count', usage.get('prompt_tokens', usage.get('input_tokens')))
            if type(count) is int and count >= 0:
                row['reported_prompt_tokens'] = count
    rows = list(calls.values())
    measured = [r['reported_prompt_tokens'] for r in rows if 'reported_prompt_tokens' in r]
    return {'calls': rows, 'summary': {
        'calls_observed': len(rows),
        'wire_requests_observed': sum('wire_messages' in r or r.get('unsupported_wire_format', False) for r in rows),
        'prompt_usage_measured_calls': len(measured),
        'largest_reported_prompt_tokens': max(measured, default=None),
        'signature_mismatch_calls': sum((r.get('host_signature_mismatches') or 0) > 0 for r in rows),
        'wire_trim_events': sum(r['wire_trim_events'] for r in rows),
        'calls_with_selected_seed_view': sum('seed_selected_messages' in r for r in rows)}}


def selected_views(folder):
    views = {}
    for path in (folder / 'sessions').glob('*/events.jsonl'):
        latest, handoff = None, None
        for event in events(path):
            data = event.get('data', {})
            if event['type'] == 'model_request':
                latest, handoff = data.get('messages'), None
            elif event['type'] == 'context_handoff':
                handoff = data
            elif event['type'] == 'host_inference_call_start' and latest is not None:
                views[data['call_id']] = {'messages': latest, 'handoff': handoff}
    return views


def audit(study):
    study = Path(study).resolve()
    plan = read(study / 'plan.json')
    queue = read(study / 'queue.json')
    if any(a['state'] == 'running' for rows in queue['cells'].values() for a in rows):
        raise ValueError('Read-only closed-study audit requires no running cells')
    profiles = {p['id']: p['config'] for p in plan['profiles']}
    cells = []
    for key, attempts in queue['cells'].items():
        for attempt in attempts:
            if not attempt.get('folder'):
                continue
            folder = Path(attempt['folder'])
            trace = folder / 'provider-calls.jsonl'
            if not trace.exists():
                continue
            profile = max((name for name in profiles if key.startswith(name + '_')), key=len)
            result = audit_calls(events(trace), profiles[profile], selected_views(folder))
            cells.append({'cell': key, 'attempt': attempt['attempt'], 'state': attempt['state'],
                'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(),
                'session_journal_sha256': {p.parent.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in (folder / 'sessions').glob('*/events.jsonl')}, **result})
    return {'study': str(study), 'plan_sha256': hashlib.sha256((study / 'plan.json').read_bytes()).hexdigest(),
        'audit_implementation_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'cells': cells,
        'scope': 'Counts across repeated calls, not unique lost messages/facts or causal effects. '
                 'Signature mismatches include rewriting, shortening and activation handoff. '
                 'Wire byte estimates and provider-rendered token usage measure different representations. '
                 'No counterfactual tokenizer fit or successful-task improvement is established.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--study', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = audit(args.study)
    with Path(args.output).open('x', encoding='utf-8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
    print(json.dumps({'cells': len(result['cells']), 'output': args.output}))
