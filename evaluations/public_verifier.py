"""Experimental final-output feedback from rules published before inference.

Reads inert saved files only. No hidden grader, candidate imports, subprocesses,
feature tests or model-generated verification code are used for feedback.
"""
import csv
import hashlib
import io
import json
import time


def specification(task, feature, earlier=None):
    if earlier:
        instruction = task['final_task']
        path = 'sample.txt' if earlier == 'csv_preview' else 'inventory.json'
        output = 'audit.json'
        fields = ['path', 'bytes', 'sha256']
        if earlier == 'csv_preview':
            fields += ['rows', 'truncated']
        operation = 'preserve' if earlier == 'csv_preview' else 'canonical_json'
    else:
        spec = task['first_use']
        instruction, path, output = spec['instruction'], spec['input'], spec['output']
        fields = {'sha256_file': ['path', 'bytes', 'sha256'],
                  'format_json': ['path', 'bytes'], 'csv_preview': ['path', 'rows', 'truncated']}[feature]
        operation = 'canonical_json' if feature == 'format_json' else 'preserve'
    if not instruction or instruction not in task['task']:
        raise ValueError('Public verifier needs the verbatim original final task')
    return {'schema': 1, 'instruction': instruction, 'input': path, 'output': output,
            'input_operation': operation, 'receipt_fields': fields, 'exact_fields': not bool(earlier),
            'preview_limit': 5 if 'rows' in fields else None,
            'canonical_json': {'ensure_ascii': False, 'sort_keys': True, 'indent': 2, 'final_lf': True},
            'scope': 'Public saved-output checks only; no capability-use, hidden tests or upgrade approval.'}


def announcement(spec):
    return ('\nEXPERIMENTAL PUBLIC FINAL-OUTPUT VERIFIER\n' + json.dumps(spec, ensure_ascii=False) +
            '\nAfter your completed finish, these published checks may supply one automatic correction request. '
            'It uses the original remaining allowances. Independent hidden qualification is separate.')


def first_difference(expected, actual, location='', max_nodes=128, max_depth=8):
    """Bounded diagnostic only; the public verifier decides equality separately."""
    remaining = [max_nodes]

    def visit(wanted, found, path, depth):
        path = path[:240]
        remaining[0] -= 1
        if remaining[0] < 0 or depth > max_depth:
            return {'location': path, 'kind': 'diagnostic_limit',
                    'message': 'Inspect the saved value; diagnostic traversal is bounded.'}
        if type(wanted) is not type(found):
            return {'location': path, 'kind': 'type', 'expected_type': type(wanted).__name__,
                    'actual_type': type(found).__name__}
        if isinstance(wanted, str):
            if wanted == found:
                return None
            index = next((i for i, (a, b) in enumerate(zip(wanted, found)) if a != b), min(len(wanted), len(found)))
            return {'location': path, 'kind': 'text', 'character': index,
                    'expected_length': len(wanted), 'actual_length': len(found),
                    'expected_character': wanted[index] if index < len(wanted) else None,
                    'actual_character': found[index] if index < len(found) else None}
        if isinstance(wanted, list):
            for index, (a, b) in enumerate(zip(wanted, found)):
                result = visit(a, b, path + '/' + str(index), depth + 1)
                if result:
                    return result
            if len(wanted) != len(found):
                return {'location': path, 'kind': 'length', 'expected_length': len(wanted), 'actual_length': len(found)}
        elif isinstance(wanted, dict):
            for key in wanted:
                child = path + '/' + key[:80].replace('~', '~0').replace('/', '~1')
                if key not in found:
                    return {'location': child[:240], 'kind': 'missing_key'}
                result = visit(wanted[key], found[key], child, depth + 1)
                if result:
                    return result
            for key in found:
                if key not in wanted:
                    return {'location': (path + '/' + key[:80].replace('~', '~0').replace('/', '~1'))[:240], 'kind': 'unexpected_key'}
        elif wanted != found:
            return {'location': path, 'kind': 'value', 'expected_type': type(wanted).__name__}
        return None

    return visit(expected, actual, location, 0)


def inspect(files, spec, original_text):
    """Expected values come from original public inputs, never candidate outputs."""
    baseline = original_text.encode('utf-8')
    expected_input = baseline
    if spec['input_operation'] == 'canonical_json':
        expected_input = (json.dumps(json.loads(original_text), ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')
    expected = {'path': spec['input'], 'bytes': len(expected_input),
                'sha256': hashlib.sha256(expected_input).hexdigest()}
    if 'rows' in spec['receipt_fields']:
        rows = list(csv.reader(io.StringIO(original_text, newline='')))
        expected.update(rows=rows[:spec['preview_limit']], truncated=len(rows) > spec['preview_limit'])
    mismatches, snapshots = [], {}
    for name in (spec['input'], spec['output']):
        try:
            raw = files.read(name)
            snapshots[name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
            if name == spec['input']:
                if raw != expected_input:
                    mismatches.append({'path': name, 'check': spec['input_operation'],
                                       'message': 'Saved input does not match the published preservation/formatting requirement.'})
            else:
                receipt = json.loads(raw)
                if not isinstance(receipt, dict):
                    raise ValueError('Receipt must be a JSON object')
                if spec['exact_fields'] and set(receipt) != set(spec['receipt_fields']):
                    mismatches.append({'path': name, 'check': 'fields', 'expected': spec['receipt_fields'], 'actual': [k[:80] for k in list(receipt)[:20]]})
                for key in spec['receipt_fields']:
                    actual = receipt.get(key)
                    # JSON equality distinguishes booleans from numeric 0/1.
                    if key not in receipt or json.dumps(actual, sort_keys=True) != json.dumps(expected[key], sort_keys=True):
                        detail = {'path': name, 'check': key, 'message': 'Saved field differs from the public requirement.'}
                        # Avoid returning arbitrarily large candidate strings or
                        # entire expected rows. These are diagnostics, not answers.
                        if key == 'rows':
                            detail.update(expected_records=len(expected[key]), actual_records=len(actual) if isinstance(actual, list) else None)
                        elif key in ('bytes', 'truncated'):
                            detail.update(expected=expected[key], actual=actual if type(actual) in (int, bool, type(None)) else 'invalid type')
                        detail['difference'] = first_difference(expected[key], actual, '/' + key)
                        mismatches.append(detail)
        except (OSError, ValueError, UnicodeError, RecursionError):
            mismatches.append({'path': name, 'check': 'readable', 'message': 'Required saved file is missing or invalid.'})
    return {'passed': not mismatches, 'mismatches': mismatches, 'snapshots': snapshots,
            'scope': spec['scope']}


def repair(agent, store, session, settings, config, spec, original_text, budget, deadline, wait, run, record=None):
    """At most one opt-in correction, with no fresh resource allowance."""
    from controller.isolation import Artifacts
    files = Artifacts(store, session)
    before = inspect(files, spec, original_text)
    receipt = {'experimental': True, 'specification': spec, 'initial': before,
               'initial_status': session['status'], 'initial_run': run, 'corrections': 0,
               'scope': 'Public verifier results are not independent qualification. Hidden results never enter feedback.'}
    if record:
        record(receipt)  # Preserve first-finish evidence before any correction.
    remaining = config['max_steps'] - session['steps']
    if (not before['passed'] and session['status'] == 'completed' and not run.get('timed_out') and
            remaining > 0 and time.monotonic() < deadline and not budget.summary()['exhausted']):
        message = ('AUTOMATIC PUBLIC FINAL-OUTPUT FEEDBACK\n' + json.dumps(before, ensure_ascii=False) +
                   '\nCorrect these saved outputs using the active tools and original requirements. '
                   'Do not edit the seed or request activation again. Verify the outputs and finish completed. '
                   'No additional action, token or time allowance is granted.')
        receipt.update(corrections=1, feedback=message, supplied_actions=remaining)
        if record:
            record(receipt)
        settings.values = {**config, 'action_limit': True, 'max_steps': remaining}
        agent.start(session, message, deadline=deadline)
        run = wait(agent, session, max(0, deadline - time.monotonic()))
    receipt['final'] = inspect(files, spec, original_text)
    receipt['final_status'] = session['status']
    receipt['passed_without_feedback'] = before['passed'] and receipt['initial_status'] == 'completed'
    receipt['passed_after_feedback'] = bool(receipt['corrections'] and receipt['final']['passed'] and session['status'] == 'completed')
    if record:
        record(receipt)
    return run, receipt
