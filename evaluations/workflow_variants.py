"""Opt-in copied seeds; the normal seed and preferences are never modified."""
import base64
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREATMENTS = ('edit-feedback', 'syntax-feedback', 'masked-history', 'phases', 'staged-inputs',
              'submission-feedback', 'edit-context', 'verified-lesson')


def replace_once(text, anchor, replacement):
    if text.count(anchor) != 1:
        raise ValueError('Experimental source anchor changed; review the variant')
    return text.replace(anchor, replacement, 1)


def variant(source, treatment, keep=8, threshold=512):
    if treatment not in ('baseline', *TREATMENTS):
        raise ValueError('Unknown workflow treatment')
    result = copy.deepcopy(source)
    if treatment in ('baseline', 'phases', 'staged-inputs', 'submission-feedback', 'edit-context', 'verified-lesson'):
        return result
    # Validate even when only preparing inert source packs.
    if type(keep) is not int or keep < 1 or type(threshold) is not int or threshold < 1:
        raise ValueError('Mask settings must be positive integers')
    changed = False
    for item in result:
        if item['path'] == 'autoproteus/file_ops.py' and treatment in ('edit-feedback', 'syntax-feedback'):
            text = base64.b64decode(item['data']).decode('utf-8')
            anchor = '    return {"path": str(path.relative_to(self.root)), "bytes": len(updated.encode("utf-8")), "replacements": 1}'
            text = replace_once(text, anchor, '    from .workflow_support import edit_feedback\n'
                '    return edit_feedback({"path": str(path.relative_to(self.root)), "bytes": len(updated.encode("utf-8")), "replacements": 1},\n'
                '                         path, updated, start, len(new), ' + repr(treatment) + ')')
            changed = True
        elif item['path'] == 'autoproteus/context.py' and treatment == 'masked-history':
            text = base64.b64decode(item['data']).decode('utf-8')
            anchor = '    followup = next((item for item in reversed(history) if human(item)), None)'
            text = replace_once(text, anchor, '    from .workflow_support import mask_observations\n'
                f'    history = mask_observations(history, keep={keep}, threshold={threshold}, is_human=human)\n' + anchor)
            changed = True
        else:
            continue
        item['data'] = base64.b64encode(text.encode('utf-8')).decode('ascii')
    if not changed or any(item['path'] == 'autoproteus/workflow_support.py' for item in result):
        raise ValueError('Cannot safely construct workflow variant')
    result.append({'path': 'autoproteus/workflow_support.py', 'data': base64.b64encode(
        (ROOT / 'evaluations/workflow_support.py').read_bytes()).decode('ascii')})
    return result


DEVELOPMENT_FOCUS = ('\nCURRENT STAGE: implement, check, submit. Preserve every original requirement. '
    'Keep the real task inputs unchanged until the controller verifies and activates the edited seed. '
    'Use separate disposable examples and inspect exact resulting bytes. Once the requested implementation and '
    'focused tests pass your development checks, finish needs_input requesting independent verification '
    'and activation. Do not continue checking an unchanged passing candidate solely to repeat checks. '
    'Your readiness message is a submission, not approval. The original task remains unfinished until final use.')
USE_FOCUS = ('\nCURRENT STAGE: use the activated tools to finish the original task and inspect its exact outputs. '
    'This source has already been independently checked for the stated contracts. '
    'Do not edit the seed or repeat development checks. If a new defect prevents the task, report it; '
    'otherwise finish completed only after verifying the required artifacts. All original requirements still apply.')
