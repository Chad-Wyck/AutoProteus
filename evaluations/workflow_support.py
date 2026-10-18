"""Small guest-side experiment helpers. No imports or execution of edited code."""
import json


def edit_feedback(result, path, text, start, changed_length, treatment):
    value = dict(result)
    if treatment == 'edit-feedback':
        left = max(0, start - 160)
        right = min(len(text), max(start + min(changed_length, 680), start + 160) + 160)
        value['edited_section'] = {'start': left, 'end': right,
            'line': text.count('\n', 0, left) + 1, 'content': text[left:right],
            'changed_start': start, 'changed_end': start + changed_length,
            'change_truncated': start + changed_length > right,
            'file_characters': len(text)}
    elif treatment == 'syntax-feedback' and path.suffix == '.py':
        try:
            # Compilation detects invalid control flow (e.g. top-level return)
            # too, and never executes the resulting code object.
            compile(text, '<edited-source>', 'exec')
            value['syntax'] = {'valid': True, 'scope': 'Python syntax only; functionality unchecked.'}
        except (SyntaxError, ValueError, RecursionError) as error:
            value['syntax'] = {'valid': False, 'message': str(error)[:240],
                'line': getattr(error, 'lineno', None), 'offset': getattr(error, 'offset', None),
                'scope': 'Advisory: the edit was saved. Functionality unchecked.'}
    return value


def mask_observations(history, keep=8, threshold=512, is_human=None):
    """Retain call/result envelopes; change only old, bulky observation bodies.

    The journal is never mutated. The normal context budget still bounds older
    actions, which can themselves be large. No generated summary or extra call.
    """
    if type(keep) is not int or keep < 1 or type(threshold) is not int or threshold < 1:
        raise ValueError('Mask settings must be positive integers')
    positions = [i for i, item in enumerate(history) if item.get('origin') != 'human' and not (is_human and is_human(item))
                 and item.get('role') == 'user' and item.get('content', '').startswith('ACTION RESULT\n')]
    old = set(positions[:-keep])
    result = []
    for index, item in enumerate(history):
        copy = dict(item)
        if index in old and len(item['content']) > threshold:
            try:
                envelope = json.loads(item['content'].split('\n', 1)[1])
                body = envelope['result']
                # Retain explicit outcomes as data, never infer success from text.
                outcome = {key: body[key] for key in ('exit_code', 'written', 'replacements', 'passed')
                           if isinstance(body, dict) and key in body and type(body[key]) in (bool, int)}
                envelope['result'] = {'observation_omitted': True, 'context_shortened': True,
                    'original_characters': len(json.dumps(body, ensure_ascii=False)),
                    'recorded_outcome': outcome,
                    'notice': 'Older result body omitted. Full journal is saved; inspect current files if needed.'}
                copy['content'] = 'ACTION RESULT\n' + json.dumps(envelope, ensure_ascii=False)
            except (ValueError, KeyError, TypeError):
                pass
        result.append(copy)
    return result
