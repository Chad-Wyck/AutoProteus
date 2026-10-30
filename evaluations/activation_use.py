"""Protected, prospective first-use contracts; no candidate code executes here."""
import base64
import ast
import csv
import hashlib
import io
import json
import time

from controller.evaluation import candidate_source, source_identity, tool_use
from controller.isolation import Artifacts
from controller.tool_evidence import python_results
from observations import read_events

PROTOCOL = 'activation-use-v2'


def same_json(actual, wanted):
    # Python considers True == 1; a saved JSON boolean must remain a boolean.
    if type(actual) is not type(wanted): return False
    if isinstance(wanted,dict):
        return actual.keys()==wanted.keys() and all(same_json(actual[k],v) for k,v in wanted.items())
    if isinstance(wanted,list):
        return len(actual)==len(wanted) and all(same_json(a,b) for a,b in zip(actual,wanted))
    return actual==wanted


def contract(feature, nonce):
    """Fresh bytes are frozen in the host plan, withheld during development."""
    stem = 'activation/' + nonce
    output = stem + '-receipt.json'
    if feature == 'sha256_file':
        path = stem + '.txt'
        text = 'Fresh input ' + nonce + '\r\né猫\nSecond line.\n'
        instruction = ('Use sha256_file on ' + path + '. Save exactly its path, bytes and sha256 '
                       'fields as a JSON object in ' + output + '. Preserve the input bytes.')
    elif feature == 'csv_preview':
        path = stem + '.csv'
        text = 'name,value\r\n"café, 猫",1\r\n"line\r\nbreak",2\r\n' + ''.join(
            f'{nonce}-{index},{index}\r\n' for index in range(5))
        instruction = ('Use csv_preview on ' + path + ' with its default limit. Save exactly its '
                       'path, rows and truncated fields as a JSON object in ' + output +
                       '. Preserve all input bytes; the earlier development examples are not this task.')
    elif feature == 'format_json':
        path = stem + '.json'
        text = json.dumps({'z':[2,False], 'a':'café 猫', 'run':nonce}, ensure_ascii=False)
        instruction = ('Use format_json to format ' + path + ' in place. Save exactly its path and bytes '
                       'fields as a JSON object in ' + output + '.')
    else:
        from novel_features import contract as novel_contract
        return novel_contract(feature, nonce)
    return {'feature':feature, 'input':path, 'output':output, 'fixtures':{path:text},
            'instruction':instruction + ' Check the saved result and finish completed. Do not edit the seed after activation.'}


def expected(spec):
    path = spec['input']; text = spec['fixtures'][path]; raw = text.encode('utf-8')
    if spec['feature'] == 'sha256_file':
        receipt = {'path':path, 'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest()}
        final = raw
    elif spec['feature'] == 'csv_preview':
        rows = list(csv.reader(io.StringIO(text, newline='')))
        receipt = {'path':path, 'rows':rows[:5], 'truncated':len(rows)>5}
        final = raw
    elif spec['feature'] == 'format_json':
        final = (json.dumps(json.loads(text), ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode('utf-8')
        receipt = {'path':path, 'bytes':len(final)}
    else:
        from novel_features import expected as novel_expected
        return novel_expected(spec)
    return final, receipt


def check_outputs(files, spec):
    final, receipt = expected(spec)
    try: input_correct = files.read(spec['input']) == final
    except (OSError, ValueError): input_correct = False
    try: output_correct = same_json(json.loads(files.read(spec['output'])),receipt)
    except (OSError, ValueError, UnicodeError, RecursionError): output_correct = False
    return {'input_correct':input_correct, 'receipt_correct':output_correct,
            'artifacts_correct':input_correct and output_correct}


def grade(files, spec, events, *, source_unchanged, completed, on_time=True, within_budget=True):
    """Score only the post-activation boundary, including the actual fresh call."""
    if spec.get('strict_use'):
        from novel_features import grade as novel_grade
        return novel_grade(files, spec, events, source_unchanged=source_unchanged,
                           completed=completed, on_time=on_time, within_budget=within_budget)
    output = check_outputs(files, spec)
    _, receipt = expected(spec)
    usage = tool_use(events)
    used = False
    native_arguments = []
    for event in events:
        data = event.get('data', {})
        if event.get('type')!='action_result' or not data.get('ok'):
            continue
        action = data.get('action', {})
        observed = []
        if action.get('tool')==spec['feature'] and action.get('arguments',{}).get('path')==spec['input']:
            observed.append(data.get('result'))
            native_arguments.append(action['arguments'])
        elif spec['feature'] in tool_use([event])['development']:
            observed.extend(python_results(data,spec['feature'],spec['input']))
            for line in data.get('result',{}).get('output','').splitlines():
                try: value = json.loads(line)
                except ValueError:
                    try: value = ast.literal_eval(line)
                    except (ValueError, SyntaxError, RecursionError): continue
                if isinstance(value,dict):
                    if value.get('check') in ('candidate tool invocation','development tool invocation') and value.get('tool')==spec['feature'] and value.get('passed') is True:
                        observed.append(value.get('result'))
                    elif 'check' not in value: observed.append(value)
        used = used or any(isinstance(value,dict) and all(k in value and same_json(value[k],v) for k,v in receipt.items()) for value in observed)
    inspected = any(e.get('type')=='action_result' and e.get('data',{}).get('ok') and
        e['data'].get('action',{}).get('tool') in ('read_file','read_section') and
        e['data']['action'].get('arguments',{}).get('path')==spec['output'] for e in events)
    return {**output, 'usage':usage, 'capability_used':used, 'source_unchanged':source_unchanged,
        'inspection_observed':inspected, 'completed':completed,
        'default_arguments_omitted':(any('limit' not in args for args in native_arguments)
            if spec['feature']=='csv_preview' and native_arguments else None),
        'passed':bool(output['artifacts_correct'] and used and source_unchanged and completed and on_time and within_budget)}


def oracle_controls(specs):
    """Calibrate artifact/use scoring; feature implementation controls run separately."""
    checks = {}
    class Files:
        def __init__(self, values): self.values = values
        def read(self, path):
            if path not in self.values: raise ValueError('Missing artifact')
            return self.values[path]
    for key, spec in specs.items():
        final, receipt = expected(spec)
        files = Files({spec['input']:final, spec['output']:json.dumps(receipt).encode()})
        events = [{'type':'action_result','data':{'ok':True,'action':{'tool':spec['feature'],
            'arguments':{'path':spec['input']}},'result':receipt}}]
        options = {'source_unchanged':True,'completed':True}
        positive = grade(files,spec,events,**options)['passed']
        bad_receipt = Files({spec['input']:final, spec['output']:b'{}'})
        wrong_call = json.loads(json.dumps(events));wrong_call[0]['data']['action']['arguments']['path']='development/other.txt'
        negatives = {
            'wrong_receipt':grade(bad_receipt,spec,events,**options)['passed'],
            'missing_post_activation_call':grade(files,spec,[],**options)['passed'],
            'wrong_input_call':grade(files,spec,wrong_call,**options)['passed'],
            'source_changed':grade(files,spec,events,source_unchanged=False,completed=True)['passed'],
            'unfinished':grade(files,spec,events,source_unchanged=True,completed=False)['passed']}
        wrong_type = dict(receipt)
        key_name = 'sections' if spec['feature']=='ini_sections' else 'truncated' if spec['feature']=='csv_preview' else 'bytes'
        wrong_type[key_name] = 1 if key_name=='truncated' else str(wrong_type[key_name])
        typed_files = Files({spec['input']:final, spec['output']:json.dumps(wrong_type).encode()})
        negatives['wrong_json_type'] = grade(typed_files,spec,events,**options)['passed']
        if spec['feature']=='csv_preview':
            stale = {**receipt,'rows':receipt['rows'][:2]}
            negatives['stale_preview'] = grade(Files({spec['input']:final,spec['output']:json.dumps(stale).encode()}),spec,events,**options)['passed']
        elif spec['feature']=='format_json':
            negatives['format_not_written'] = grade(Files({spec['input']:spec['fixtures'][spec['input']].encode(),
                spec['output']:json.dumps(receipt).encode()}),spec,events,**options)['passed']
        checks[key] = {'positive':positive,'negative_passes':negatives,'passed':positive and not any(negatives.values())}
    if not all(row['passed'] for row in checks.values()): raise ValueError('First-use oracle calibration failed')
    return {'passed':True,'checks':checks,'scope':'Artifact/use oracle controls; independent feature controls and scripted VM integration are separate.'}


def eligible_parent(row, protocol=None):
    if protocol == PROTOCOL:
        return row.get('first_package_accepted') is True
    return row.get('review', {}).get('accepted') is True


def chain_result(first, second, protocol=None):
    second_passed = second.get('scores', {}).get('functional_growth') is True
    if protocol != PROTOCOL:
        return {'protocol':'legacy', 'complete_chain_passed':None, 'second_task_passed':second_passed}
    first_passed = first.get('first_use', {}).get('passed') is True
    return {'protocol':PROTOCOL, 'first_use_passed':first_passed, 'second_task_passed':second_passed,
            'diagnostic_only':not first_passed, 'complete_chain_passed':first_passed and second_passed,
            'parent_source':'Frozen independently verified first package; first-use mutations are not promoted.'}


def activate(agent, store, session, settings, config, spec, budget, deadline, wait, feedback=None):
    result = {'attempted':False, 'activated':False, 'passed':False, 'input':spec['input'], 'output':spec['output']}
    remaining = config['max_steps'] - session['steps']
    if time.monotonic() >= deadline or remaining <= 0 or budget.summary()['exhausted']:
        return {**result, 'reason':'shared_allowance_exhausted'}
    from novel_features import items
    reserved = [*spec['fixtures'], *(item['output'] for item in items(spec))]
    if any(path in session.get('artifacts', {}) for path in reserved):
        return {**result, 'reason':'reserved_first_use_files_created_before_activation'}
    source = source_identity(candidate_source(store, session))
    events_path = store.directory(session['id'])/'events.jsonl'
    boundary = len(read_events(events_path))
    before_steps = session['steps']
    files = Artifacts(store, session)
    for path, text in spec['fixtures'].items():
        files.put(path, base64.b64encode(text.encode('utf-8')).decode())
    files.checkpoint([*session.get('artifacts', {}), *spec['fixtures']])
    settings.values = {**config, 'action_limit':True, 'max_steps':remaining}
    result.update(attempted=True, source_sha256=source, supplied_actions=remaining)
    try:
        agent.restart_seed(session, handoff='concise', deadline=deadline)
        result['activated'] = True
        run = wait(agent, session, max(0, deadline-time.monotonic()))
        if feedback:
            run, result['public_verifier'] = feedback(run)
        events = read_events(events_path)[boundary:]
        unchanged = source_identity(candidate_source(store, session)) == source
        result.update(grade(files,spec,events,source_unchanged=unchanged,completed=session['status']=='completed',
            on_time=time.monotonic()<deadline and not run.get('timed_out'),
            within_budget=session['steps']<=config['max_steps'] and budget.summary()['charged_output_tokens']<=budget.summary()['limit']),
            run=run, actions=session['steps']-before_steps, shared_actions_used=session['steps'],
            deadline_reached=time.monotonic()>=deadline)
    except Exception as error:
        result.update(reason='activation_or_use_error', error=str(error)[:500])
    return result
