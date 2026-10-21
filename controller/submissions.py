"""Public submission feedback. Parse candidate bytes as data; never import them."""
import ast
import base64
import hashlib
import json
from pathlib import PurePosixPath


def source_hash(source):
    entries = sorted((item['path'], hashlib.sha256(base64.b64decode(item['data'])).hexdigest()) for item in source)
    return hashlib.sha256(json.dumps(entries, separators=(',', ':')).encode()).hexdigest()


def submission_policy(starter, source):
    original = {item['path']: base64.b64decode(item['data']) for item in starter}
    candidate = {item['path']: base64.b64decode(item['data']) for item in source}
    changed = {name for name in original.keys() | candidate.keys() if original.get(name) != candidate.get(name)}
    additions = changed - original.keys()
    editable = {'autoproteus/tools.py', 'autoproteus/providers.py'}
    if 'autoproteus/extensions.py' in original:
        editable.add('autoproteus/extensions.py')
    text = {name for name in changed | original.keys() if PurePosixPath(name).suffix in {'.md', '.txt'}}
    new_tests = sorted(name for name in additions if name.startswith('tests/test_') and name.endswith('.py')
                       and b'def test_' in candidate[name])
    unexpected = sorted(name for name in changed if name not in editable | text and
                        not (name in additions and name.startswith('tests/') and name.endswith('.py')))
    protected = sorted(name for name, content in original.items()
                       if name not in editable | text and candidate.get(name) != content)
    return {'source_sha256': source_hash(source), 'changed_files': sorted(changed), 'new_test_files': new_tests,
            'runtime_changed': bool(changed & editable), 'protected_unchanged': not protected,
            'allowed_files_only': not unexpected, 'unexpected_files': unexpected, 'protected_changes': protected,
            'documentation_updated': 'README.md' in changed}


def repair_ticket(starter, source, events=()):
    policy = submission_policy(starter, source)
    issues = []
    if not policy['runtime_changed']:
        issues.append({'kind': 'implementation', 'paths': [], 'evidence': 'No permitted runtime edit was submitted.',
                       'hypothesis': 'The implementation may still be missing.'})
    if not policy['new_test_files']:
        issues.append({'kind': 'tests', 'paths': ['tests/test_<capability>.py'],
                       'evidence': 'No separate new tests/test_*.py file containing a test was submitted.',
                       'hypothesis': 'A focused test may have been omitted or added only to an existing protected file.'})
    for key, kind, explanation in [('unexpected_files', 'scope', 'These changed bundle paths are outside the declared edit scope.'),
                                    ('protected_changes', 'preservation', 'These existing protected paths were changed or deleted.')]:
        if policy[key]:
            issues.append({'kind': kind, 'paths': policy[key][:12], 'evidence': explanation,
                           'hypothesis': 'Scratch inputs or argument files may belong outside harness/.' if kind == 'scope' else
                                         'Restore the existing files and put focused tests in a new file.'})
    by_path = {item['path']: item for item in source}
    for name in policy['changed_files']:
        if name.endswith('.py') and name in by_path:
            try:
                ast.parse(base64.b64decode(by_path[name]['data']).decode('utf-8'), filename=name)
            except (SyntaxError, UnicodeError, ValueError, RecursionError) as error:
                issues.append({'kind': 'syntax', 'paths': [name], 'evidence': str(error)[:600],
                               'hypothesis': 'Inspect this location before repeating the development suite.'})
            if len(issues) >= 8:
                break
    # Guest output is diagnostic evidence, never an independent verdict. Only
    # command results observed by the host journal are eligible, not prose.
    failure = None
    for index, event in reversed(list(enumerate(events))):
        data = event.get('data', {})
        action = data.get('action', {}) if isinstance(data, dict) else {}
        command = action.get('arguments', {}).get('command', '')
        result = data.get('result', {}) if isinstance(data, dict) else {}
        if (event.get('type') == 'action_result' and action.get('tool') == 'run_command' and
                'harness/seed.py check' in command and isinstance(result, dict)):
            # The latest check supersedes older failures, including a later pass.
            if result.get('exit_code') not in (0, None):
                failure = {'event_index': index, 'command': command[:300], 'output': str(result.get('output', ''))[-1800:],
                           'hypothesis': 'The implementation or its test may contradict the contract. Compare the failing assertion '
                                         'with the real Workspace.execute interface and a small exact output example.',
                           'scope': 'Untrusted guest development-check output; source at that earlier command may differ.'}
            break
    ready = not issues and failure is None
    return {'schema': 1, 'source_sha256': policy['source_sha256'], 'ready_for_independent_checks': ready,
            'policy': policy, 'issues': issues[:8], 'development_failure': failure,
            'scope': 'Public requirements and static/development evidence only. This is not independent approval.',
            'next_step': 'Request independent verification; after activation use the tools and explicitly finish the task.' if ready else
                         'Repair these concrete issues, invoke the tool on a disposable example, inspect actual outputs, then submit again.'}


def ticket_message(ticket):
    text = json.dumps(ticket, ensure_ascii=False)
    # Bound the entire packet, including unusually long submitted path names.
    if len(text.encode('utf-8')) > 10000:
        text = json.dumps({key: ticket[key] for key in ('schema', 'source_sha256', 'scope', 'next_step')}) + '\n' + \
            'Feedback exceeded the packet limit. Inspect changed paths and the latest development-check output.'
    return 'PUBLIC SUBMISSION FEEDBACK (observations and hypotheses are separate)\n' + text
