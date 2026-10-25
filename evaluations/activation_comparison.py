"""Opt-in activation placement study; ordinary application behavior is unchanged."""
import base64
import copy
import hashlib
import json

from controller.isolation import Broker
from guidance_comparison import CONTRACT as INVENTORY_CONTRACT
from generalization import CONTRACTS

ARM_NAMES = ('baseline', 'activation-history')


class StudyBroker(Broker):
    """The owned runner selects this mode, never an edited guest request."""
    def __init__(self, store, session, client, config, cancel, activation_context='', human_message=None):
        super().__init__(store, session, client, config, cancel, activation_context, human_message)
        if config.get('_study_activation_history') is True:
            # The copied seed budgets and places the same state beside its
            # activation boundary; do not append it again after the latest result.
            self.activation_context = ''


def variant(source, arm):
    result = copy.deepcopy(source)
    if arm == 'baseline':
        return result
    if arm != 'activation-history':
        raise ValueError('Unknown activation arm')
    item = next(item for item in result if item['path'] == 'autoproteus/context.py')
    text = base64.b64decode(item['data']).decode('utf-8')
    old = "    if config.get('activation_context'):\n        runtime.append({'role': 'user', 'content': config['activation_context']})"
    new = "    activation_state = {'role': 'user', 'content': config['activation_context']} if config.get('activation_context') else None\n    if activation_state:\n        runtime.append(activation_state)"
    # Source files can retain Windows line endings.
    newline = '\r\n' if '\r\n' in text else '\n'
    text = text.replace('\r\n', '\n')
    if text.count(old) == 1:
        text = text.replace(old, new)
    elif text.count("    activation = {'role': 'user', 'content': config.get('activation_context', '')}") == 1:
        # Current seeds already put state before observations. Compare that
        # task-adjacent placement with the exact activation boundary instead.
        text = text.replace('    history = [dict(item) for item in session[\'messages\']]',
                            "    activation_state = {'role': 'user', 'content': config.get('activation_context', '')}\n"
                            "    history = [dict(item) for item in session['messages']]")
        text = text.replace("    activation = {'role': 'user', 'content': config.get('activation_context', '')}",
                            '    activation = activation_state')
    else:
        raise ValueError('Activation placement anchor changed')
    old = "        return [{'role': item['role'], 'content': item['content']} for item in items]"
    new = '''        selected = list(items)
        if activation_state and any(item is activation_state for item in selected):
            selected = [item for item in selected if item is not activation_state]
            boundary = max((index for index, item in enumerate(selected)
                            if item.get('origin') == 'internal' and
                            item['content'].startswith('Your edited seed is now active.')), default=-1)
            # Restore current facts near the start if trimming removed the
            # boundary. No extra journal entries or human messages are created.
            selected.insert(boundary + 1 if boundary >= 0 else min(2, len(selected)), activation_state)
        return [{'role': item['role'], 'content': item['content']} for item in selected]'''
    if text.count(old) != 1:
        raise ValueError('Message formatting anchor changed')
    text = text.replace(old, new)
    item['data'] = base64.b64encode(text.replace('\n', newline).encode()).decode()
    return result


RECIPE = ('\nRead harness/README.md and relevant source. Change runtime code only in '
    'harness/autoproteus/tools.py and harness/autoproteus/providers.py. Preserve the loop and every existing '
    'test exactly; add a separate focused tests/test_*.py file. Exercise edited tools on disposable examples '
    'outside harness/ and inspect actual outputs. Run python3 harness/seed.py check. When ready, finish '
    'needs_input requesting independent verification and activation. After activation, complete the final '
    'task stated below using the supplied tools, inspect the saved outputs against these requirements, '
    'and finish completed. Do not edit the activated seed while completing final use. '
    'Internet is disabled for this offline comparison.')


def tasks(index):
    first_inputs = {'records/input.txt': ('café\r\n猫\x00' * index),
                    'development/example.txt': 'disposable example, not the final input'}
    raw = first_inputs['records/input.txt'].encode()
    first = {'name': 'hash-first-' + str(index), 'fixtures': first_inputs,
        'task': 'Add and register exactly one missing public tool: ' + CONTRACTS['sha256_file'] + RECIPE +
            '\nFinal task: use sha256_file on records/input.txt, save its returned object as hash.json, '
            'inspect hash.json, then finish completed. Preserve all original input bytes.',
        'required_tools': ['sha256_file'],
        'final_checks': [{'path': 'hash.json', 'json': {'path': 'records/input.txt', 'bytes': len(raw),
                         'sha256': hashlib.sha256(raw).hexdigest()}}]}
    second_inputs = {'batch/a.txt': 'first\r\n' * index, 'batch/数据.txt': 'café 猫\n' * (index + 1),
                     'batch/archive/old.txt': 'nested file must not enter a default inventory',
                     'development/nested/example.txt': 'recursive development example'}
    listed = sorted([{'path': path, 'bytes': len(text.encode())} for path, text in second_inputs.items()
                     if path.startswith('batch/') and path.count('/') == 1], key=lambda item: item['path'])
    audited = [{**item, 'sha256': hashlib.sha256(second_inputs[item['path']].encode()).hexdigest()} for item in listed]
    second = {'name': 'inventory-second-' + str(index), 'fixtures': second_inputs,
        'task': 'The previous hashing task is complete. Extend your current grown seed with exactly one '
            'missing public tool: ' + INVENTORY_CONTRACT + RECIPE +
            '\nPreserve sha256_file and all existing tests and capabilities. During development, exercise '
            'inventory_files on development/ with recursive=True using disposable outputs. '
            'Final task: inventory batch/ with the documented defaults and save that returned object as '
            'inventory.json. Use sha256_file to hash each file in that inventory. Save audit.json as '
            '{"path":"batch","files":[{"path":file_path,"bytes":exact_bytes,"sha256":lowercase_digest},...]}, '
            'sorted by path and containing exactly the inventoried files. Preserve all original inputs and '
            'the previous hash.json. Inspect inventory.json and audit.json, then finish completed.',
        'required_tools': ['inventory_files', 'sha256_file'],
        'final_checks': [{'path': 'inventory.json', 'json': {'path': 'batch', 'files': listed}},
                         {'path': 'audit.json', 'json': {'path': 'batch', 'files': audited}}]}
    for task in (first, second):
        task['input_sha256'] = {path: hashlib.sha256(text.encode()).hexdigest() for path, text in task['fixtures'].items()}
    return {'first': first, 'second': second}


def add_hash_reference(source, fault=None):
    result = copy.deepcopy(source)
    branch = '''        if tool == "sha256_file":
            import hashlib
            path = self.path(args["path"])
            with path.open("rb") as stream: raw = stream.read(1048577)
            if len(raw) > 1048576: raise ValueError("Too large")
            return {"path": path.relative_to(self.root).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
'''
    if fault == 'exact-boundary':
        branch = branch.replace('len(raw) > 1048576', 'len(raw) >= 1048576')
    elif fault == 'false-digest':
        branch = branch.replace('hashlib.sha256(raw).hexdigest()', '"0" * 64')
    elif fault not in (None, 'required-schema', 'absent'):
        raise ValueError('Unknown hash control')
    if fault == 'absent':
        return result
    spec = {'sha256_file': ('Hash a workspace file.', {'path': {'type': 'string'}}, [] if fault == 'required-schema' else ['path'])}
    for item in result:
        text = base64.b64decode(item['data']).decode() if item['path'] in ('autoproteus/tools.py', 'autoproteus/providers.py') else ''
        if item['path'] == 'autoproteus/tools.py':
            anchor = '        if tool == "list_files":'
            if text.count(anchor) != 1:
                raise ValueError('Hash reference anchor changed')
            item['data'] = base64.b64encode(text.replace(anchor, branch + anchor, 1).encode()).decode()
        elif item['path'] == 'autoproteus/providers.py':
            item['data'] = base64.b64encode(text.replace('TOOL_SPECS = {', 'TOOL_SPECS = ' + repr(spec) + ' | {', 1).encode()).decode()
    return result
