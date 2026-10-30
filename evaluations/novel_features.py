"""Opt-in INI/newline research contracts. Candidate code is data, never imported here."""
import base64
import configparser
import copy
import json
import shlex

from controller.evaluation import growth_scores, tool_use
from controller.tool_evidence import python_invocations, python_results

FEATURES = ('ini_sections', 'normalize_newlines')
PACK = 'pilot-6k'
CONTRACTS = {
    'ini_sections': ('ini_sections(path) reads a workspace UTF-8 INI file of at most 100000 Unicode characters '
        'using configparser.ConfigParser(interpolation=None, strict=True). Return exactly '
        '{"path": relative_path, "sections": section_names_in_file_order}, excluding DEFAULT. '
        'Preserve input bytes; empty input returns no sections. Reject malformed INI, invalid UTF-8, '
        'oversized files, missing files, directories and escaping paths/symlinks by raising '
        'ValueError, OSError or configparser.Error, never an error dictionary.'),
    'normalize_newlines': ('normalize_newlines(path, newline="lf") reads workspace UTF-8 text of at most '
        '100000 Unicode characters. Normalize CRLF and bare CR to LF, then use LF by default or CRLF '
        'when newline="crlf". Save exact UTF-8 bytes in place and return exactly '
        '{"path": relative_path, "bytes": saved_byte_count, "changed": whether_bytes_changed}, '
        'with changed a boolean. Reject other newline values, invalid UTF-8, oversized input or converted '
        'output above 100000 characters, missing files, directories and escaping paths/symlinks before '
        'mutation. Raise ValueError or OSError; preserve rejected input bytes. Only path is required.')}


def oracle(feature, path, raw, arguments=None):
    text = raw.decode('utf-8')
    if len(text) > 100000:
        raise ValueError('Too many characters')
    if feature == 'ini_sections':
        parser = configparser.ConfigParser(interpolation=None, strict=True)
        parser.read_string(text)
        return raw, {'path': path, 'sections': parser.sections()}
    if feature != 'normalize_newlines':
        raise ValueError('Unknown novel feature')
    newline = (arguments or {}).get('newline', 'lf')
    if newline not in ('lf', 'crlf'):
        raise ValueError('Bad newline')
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if newline == 'crlf': text = text.replace('\n', '\r\n')
    if len(text) > 100000: raise ValueError('Too many output characters')
    final = text.encode('utf-8')
    return final, {'path': path, 'bytes': len(final), 'changed': final != raw}


def contract(feature, nonce):
    if feature not in FEATURES: raise ValueError('Unknown novel feature')
    path = 'activation/' + nonce + ('.ini' if feature == 'ini_sections' else '.txt')
    text = ('[DEFAULT]\nx=1\n[サービス]\nname=café\n[API]\nx=2\n' if feature == 'ini_sections'
            else 'café\r\n猫\rend\n')
    output = 'activation/' + nonce + '-receipt.json'
    return {'feature': feature, 'input': path, 'output': output, 'fixtures': {path: text},
        'strict_use': True, 'required_omitted_arguments': ['newline'] if feature == 'normalize_newlines' else [],
        'instruction': ('Use ' + feature + ' on ' + path + ' with defaults, omitting every optional argument. '
            'Save its exact return as JSON in ' + output + '. Inspect the saved result and input, then finish '
            'completed. Do not edit the seed after activation.')}


def items(spec):
    return [spec, *spec.get('also_use', [])]


def expected(spec):
    if spec['feature'] not in FEATURES:
        from activation_use import expected as familiar_expected
        return familiar_expected(spec)
    return oracle(spec['feature'], spec['input'], spec['fixtures'][spec['input']].encode('utf-8'))


def preserved_outputs(files, values):
    try: return all(files.read(path) == base64.b64decode(raw, validate=True) for path, raw in values.items())
    except (OSError, ValueError): return False


def saved_outputs(files, spec):
    from activation_use import check_outputs
    if not check_outputs(files, spec)['artifacts_correct']:
        raise ValueError('First-use files no longer match the independently checked task')
    return {path: base64.b64encode(files.read(path)).decode('ascii') for path in (spec['input'], spec['output'])}


def growth_result(row, earlier, feature):
    use = row['first_use']
    retained = row['retained']['passed'] and row['retained_public']['passed'] and row['stage_order_preserved']
    row.update(verified_extension=row['first_package_accepted'], final=use.get('run'),
        final_source_unchanged=use.get('source_unchanged', False),
        final_artifacts_correct=use.get('artifacts_correct', False) and use.get('preserved_outputs', False),
        final_usage=use.get('usage', {'direct': [], 'development': []}))
    row['scores'] = growth_scores(row['verified_extension'], retained, use['passed'],
        row['final_artifacts_correct'], row['final_usage'], [earlier, feature])
    row['stages'].update(correct_final_use=use['passed'], explicit_finish=use.get('completed', False))


def development_arguments(data, feature, path):
    """Literal argument evidence only; dynamic programs remain unqualified."""
    command = data.get('action', {}).get('arguments', {}).get('command', '')
    arguments = [row['arguments'] for row in python_invocations(command)
        if row['tool'] == feature and isinstance(row['arguments'], dict) and row['arguments'].get('path') == path
        and row['print_prefixes']]
    try:
        parts = shlex.split(command)
        if len(parts) == 4 and parts[:2] == ['python3', 'experience/invoke_tool.py'] and parts[2] == feature:
            value = json.loads(parts[3])
            if isinstance(value, dict) and value.get('path') == path: arguments.append(value)
        # Public seed check --tool route, whose receipt records the actual invocation.
        if (len(parts) == 7 and parts[:2] == ['python3', 'harness/seed.py'] and parts[2] in ('check', 'invoke')
                and parts[3:6] == ['--tool', feature, '--arguments']):
            value = json.loads(parts[6])
            if isinstance(value, dict) and value.get('path') == path: arguments.append(value)
    except (ValueError, TypeError): pass
    return arguments


def grade(files, spec, events, *, source_unchanged, completed, on_time=True, within_budget=True):
    from activation_use import same_json
    checks = []
    for item in items(spec):
        final, receipt = expected(item)
        def matches(value):
            # The familiar contracts permit additional return fields; their saved receipts are exact.
            return (same_json(value, receipt) if item['feature'] in FEATURES else
                isinstance(value, dict) and all(k in value and same_json(value[k], v) for k, v in receipt.items()))
        try:
            artifacts = files.read(item['input']) == final and same_json(json.loads(files.read(item['output'])), receipt)
        except (OSError, ValueError, UnicodeError, RecursionError): artifacts = False
        native = development = False
        for event in events:
            data = event.get('data', {})
            if event.get('type') != 'action_result' or not data.get('ok'): continue
            action = data.get('action', {})
            args = action.get('arguments', {})
            omitted = item.get('required_omitted_arguments', [])
            if action.get('tool') == item['feature'] and args.get('path') == item['input']:
                native |= not any(k in args for k in omitted) and matches(data.get('result'))
            elif action.get('tool') == 'run_command' and data.get('result', {}).get('exit_code') == 0:
                args_ok = any(not any(k in a for k in omitted) for a in development_arguments(data, item['feature'], item['input']))
                observed = python_results(data, item['feature'], item['input'])
                for line in data['result'].get('output', '').splitlines():
                    try: value = json.loads(line)
                    except ValueError: continue
                    if (isinstance(value, dict) and value.get('tool') == item['feature'] and value.get('passed') is True
                            and value.get('check') in ('candidate tool invocation', 'development tool invocation')):
                        observed.append(value.get('result'))
                development |= args_ok and any(matches(value) for value in observed)
        checks.append({'feature': item['feature'], 'artifacts_correct': artifacts,
            'native_default_use': native, 'verified_development_default_use': development,
            'passed': artifacts and (native or development)})
    preserved = True
    for path, encoded in spec.get('preserve', {}).items():
        try: preserved &= files.read(path) == base64.b64decode(encoded, validate=True)
        except (OSError, ValueError): preserved = False
    return {'checks': checks, 'artifacts_correct': all(c['artifacts_correct'] for c in checks),
        'capability_used': all(c['native_default_use'] or c['verified_development_default_use'] for c in checks),
        'default_arguments_omitted': all(c['passed'] for c in checks),
        'preserved_outputs': preserved, 'usage': tool_use(events), 'source_unchanged': source_unchanged,
        'completed': completed, 'passed': bool(all(c['passed'] for c in checks) and preserved and source_unchanged
            and completed and on_time and within_budget)}


def growth_task(parent, plan, first_spec, preserved):
    from activation_use import contract as use_contract
    from model_plan import growth_feature
    added = (FEATURES[1] if parent == FEATURES[0] else FEATURES[0]) if parent in FEATURES else growth_feature(parent)
    primary = strict_contract(use_contract(added, first_spec['input'].split('/')[-1].split('.')[0] + '-second'))
    reuse = strict_contract(use_contract(parent, first_spec['input'].split('/')[-1].split('.')[0] + '-reuse'))
    primary['also_use'] = [reuse]
    primary['fixtures'].update(reuse['fixtures'])
    primary['preserve'] = preserved
    final = primary['instruction'] + ' Also: ' + reuse['instruction'] + ' Keep every first-task input and receipt unchanged.'
    primary['instruction'] = final
    fixtures = {path: base64.b64decode(raw, validate=True).decode('utf-8') for path, raw in preserved.items()}
    return added, {'name': parent + '-then-' + added, 'checks': [], 'fixtures': fixtures,
        'first_use': primary, 'final_task': final, 'required_existing_tools': [parent], 'preserve': preserved,
        'task': ('Your active seed already includes the independently checked ' + parent + '. Add exactly one new tool. '
            + plan.get('contracts', CONTRACTS)[added] + plan['recipe'].replace('Finish completed only after implementing and verifying the feature.', '')
            + '\nPreserve all existing capabilities, tests and first-task files. Use disposable development examples. '
            'Finish needs_input requesting activation after verifying the extension. The controller will supply fresh '
            'new and reuse inputs only after independent checking and activation; do not create those paths or receipts. '
            'Complete this final task after activation: ' + final)}


def strict_contract(spec):
    omitted = ['newline'] if spec['feature'] == 'normalize_newlines' else ['limit'] if spec['feature'] == 'csv_preview' else []
    clause = ' For this default-use task, supply only path and omit ' + ', '.join(omitted) + '.' if omitted else ''
    return {**spec, 'strict_use': True, 'required_omitted_arguments': omitted,
        'instruction': spec['instruction'] + (clause if clause and clause not in spec['instruction'] else '')}


# These strings are injected into exported source packs only. Only the guest executes them.
REFERENCE = '''        if tool in ("ini_sections", "normalize_newlines"):
            import configparser
            path = self.path(args["path"])
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            if len(text) > 100000: raise ValueError("Too many input characters")
            if tool == "ini_sections":
                parser = configparser.ConfigParser(interpolation=None, strict=True)
                parser.read_string(text)
                return {"path": str(path.relative_to(self.root)), "sections": parser.sections()}
            newline = args.get("newline", "lf")
            if newline not in ("lf", "crlf"): raise ValueError("Bad newline")
            text = text.replace("\\r\\n", "\\n").replace("\\r", "\\n")
            if newline == "crlf": text = text.replace("\\n", "\\r\\n")
            if len(text) > 100000: raise ValueError("Too many output characters")
            final = text.encode("utf-8")
            path.write_bytes(final)
            return {"path": str(path.relative_to(self.root)), "bytes": len(final), "changed": final != raw}
'''


def reference(source, fault=None, features=FEATURES):
    from generalization import CONTRACTS as familiar, REFERENCE as familiar_code
    contracts = {**familiar, **CONTRACTS}
    if not features or not set(features).issubset(contracts): raise ValueError('Unknown reference feature')
    code = REFERENCE
    replacements = {
        'byte-limit': ('if len(text) > 100000: raise ValueError("Too many input characters")',
                       'if len(raw) > 100000: raise ValueError("Too many input characters")'),
        'path-bypass': ('path = self.path(args["path"])', 'path = self.root / args["path"]'),
        'sorted-sections': ('"sections": parser.sections()', '"sections": sorted(parser.sections())'),
        'missing-write': ('path.write_bytes(final)', 'pass # omitted write'),
        'wrong-default': ('args.get("newline", "lf")', 'args.get("newline", "crlf")'),
        'false-changed': ('"changed": final != raw', '"changed": int(final != raw)'),
        'late-validation': ('if len(text) > 100000: raise ValueError("Too many output characters")',
                            'if len(text) > 100000:\n                path.write_bytes(text.encode("utf-8"))\n                raise ValueError("Too many output characters")')}
    if fault:
        old, new = replacements[fault]
        if code.count(old) != 1: raise ValueError('Fault injection anchor changed')
        code = code.replace(old, new)
    code = code.replace('tool in ("ini_sections", "normalize_newlines")', 'tool in ' + repr(tuple(features)))
    if not set(features).intersection(FEATURES): code = ''
    for feature in features:
        if feature in FEATURES: continue
        anchor = '        if tool == "' + feature + '":'
        branch = anchor + familiar_code.split(anchor, 1)[1].split('        if tool == ', 1)[0]
        if feature == 'format_json':
            branch = branch.replace('return self.write_text(path, text)',
                'if len(text) > 100000: raise ValueError("Too large")\n'
                '            self.write_text(path, text)\n'
                '            return {"path": str(path.relative_to(self.root)), "bytes": len(text.encode("utf-8"))}')
        code += branch
    result = copy.deepcopy(source)
    specs = {name: (contracts[name], {'path': {'type': 'string'},
        **({'newline': {'type': 'string', 'enum': ['lf', 'crlf']}} if name == 'normalize_newlines' else
           {'limit': {'type': 'integer'}} if name == 'csv_preview' else {})}, ['path']) for name in features}
    for item in result:
        text = base64.b64decode(item['data'], validate=True).decode('utf-8')
        if item['path'] == 'autoproteus/tools.py':
            anchor = '        if tool == "list_files":'
            if text.count(anchor) != 1: raise ValueError('Reference injection anchor changed')
            text = text.replace(anchor, code + anchor)
        elif item['path'] == 'autoproteus/providers.py':
            text = text.replace('TOOL_SPECS = {', 'TOOL_SPECS = ' + repr(specs) + ' | {', 1)
        item['data'] = base64.b64encode(text.encode('utf-8')).decode('ascii')
    return result
