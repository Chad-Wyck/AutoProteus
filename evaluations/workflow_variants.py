"""Opt-in copied seeds; the normal seed and preferences are never modified."""
import base64
import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TREATMENTS = ('edit-feedback', 'syntax-feedback', 'masked-history', 'phases', 'staged-inputs',
              'submission-feedback', 'edit-context', 'verified-lesson', 'final-contract', 'short-guidance', 'source-outline', 'optional-planning')

SHORT_GUIDANCE = '''Find relevant source, make a small change, then check it.
For upgrades, follow harness/README.md. Preserve existing tests and add focused tests.
Keep disposable examples outside harness/. Run python3 harness/seed.py check before requesting activation.
After activation, complete the original task using the latest human requirements and requested defaults.
Earlier examples and overrides belong to their own step. Inspect the saved final outputs, then finish.
Use todo.txt or a small verification script when useful; choose checks that establish the requested outcome.
'''

SHORT_WORKFLOW = '''## Upgrade workflow

1. Read the relevant source. Add behavior in `Workspace.execute` and register it
   in `TOOL_SPECS`; use `self.path` for workspace paths.
2. Preserve existing tests and add focused tests using `workspace.execute`.
   Inspect actual files as well as return values. Repair failures and run
   `python3 harness/seed.py check` before requesting activation.
3. If remaining work needs the new tools, finish `needs_input` requesting
   activation. Development checks do not independently approve an extension.
4. After activation, complete the original task using the latest human
   requirements, actual paths and requested defaults. Earlier examples apply
   to their own step. Verify saved outputs, repair mismatches and explicitly
   finish `completed`. Avoid repeating unchanged passing checks.

A task plan or independent assertion script is optional. Use the inspection
method that establishes the requested result; derive expectations from the
requirements, rather than copying the produced output.

'''


def replace_once(text, anchor, replacement):
    if text.count(anchor) != 1:
        raise ValueError('Experimental source anchor changed; review the variant')
    return text.replace(anchor, replacement, 1)


def variant(source, treatment, keep=8, threshold=512):
    if treatment not in ('baseline', *TREATMENTS):
        raise ValueError('Unknown workflow treatment')
    result = copy.deepcopy(source)
    if treatment == 'source-outline':
        from navigation_variant import navigation_variant
        return navigation_variant(source)
    if treatment == 'optional-planning':
        changed = set()
        for item in result:
            if item['path'] not in ('autoproteus/protocol.py', 'README.md'):
                continue
            text = base64.b64decode(item['data']).decode('utf-8')
            if item['path'] == 'autoproteus/protocol.py':
                start = text.index('Before seed edits, record the remaining final-task requirements')
                end = text.index('For seed upgrades follow harness/README.md.', start)
                text = text[:start] + ('Use a task plan or independent assertion script when useful; derive final requirements '
                    'from the human request, not earlier examples or model-written notes.\n') + text[end:]
            else:
                start = text.index('Before editing, record the **remaining final task**')
                end = text.index('1. **Implement.**', start)
                text = text[:start] + ('A task plan in root `todo.txt` or an independent assertion script is optional.\n'
                    'Choose checks that establish the requested outcome. Derive expectations\n'
                    'from the human requirements, not earlier examples or model-written notes.\n\n') + text[end:]
                text = replace_once(text, '5. **Verify outputs.** Inspect saved files and run the prepared assertions.',
                    '5. **Verify outputs.** Inspect saved files; use independent assertions when useful.')
            item['data'] = base64.b64encode(text.encode('utf-8')).decode('ascii')
            changed.add(item['path'])
        if changed != {'autoproteus/protocol.py', 'README.md'}:
            raise ValueError('Optional planning needs the shared prompt and upgrade recipe')
        return result
    if treatment == 'short-guidance':
        changed = set()
        for item in result:
            if item['path'] not in ('autoproteus/protocol.py', 'README.md'):
                continue
            text = base64.b64decode(item['data']).decode('utf-8')
            newline = '\r\n' if '\r\n' in text else '\n'
            if item['path'] == 'autoproteus/protocol.py':
                start = text.index("GUIDANCE = '''")
                end = text.index('USE_GUIDANCE = ') if 'USE_GUIDANCE = ' in text else text.index('PROTOCOL = ')
                text = text[:start] + "GUIDANCE = '''" + SHORT_GUIDANCE.replace('\n', newline) + "'''" + newline * 2 + text[end:]
            else:
                start, end = text.index('## Upgrade workflow'), text.index('Keep fixtures, argument JSON')
                text = text[:start] + SHORT_WORKFLOW.replace('\n', newline) + text[end:]
            item['data'] = base64.b64encode(text.encode('utf-8')).decode('ascii')
            changed.add(item['path'])
        if changed != {'autoproteus/protocol.py', 'README.md'}:
            raise ValueError('Short guidance needs the shared prompt and upgrade recipe')
        return result
    if treatment in ('baseline', 'phases', 'staged-inputs', 'submission-feedback', 'edit-context', 'verified-lesson', 'final-contract'):
        return result
    # Validate even when only preparing inert source packs.
    if type(keep) is not int or keep < 1 or type(threshold) is not int or threshold < 1:
        raise ValueError('Mask settings must be positive integers')
    changed = False
    for item in result:
        if item['path'] == 'autoproteus/file_ops.py' and treatment in ('edit-feedback', 'syntax-feedback'):
            text = base64.b64decode(item['data']).decode('utf-8')
            anchor = '    return {"path": str(path.relative_to(self.root)), "bytes": len(updated.encode("utf-8")), "replacements": 1, "changed": True}'
            if anchor not in text:  # Historical frozen seeds lack the changed field.
                anchor = anchor.replace(', "changed": True', '')
            text = replace_once(text, anchor, '    from .workflow_support import edit_feedback\n'
                '    return edit_feedback(' + anchor.strip().removeprefix('return ') + ',\n'
                '                         path, updated, start, len(new), ' + repr(treatment) + ')')
            changed = True
        elif item['path'] == 'autoproteus/context.py' and treatment == 'masked-history':
            text = base64.b64decode(item['data']).decode('utf-8')
            anchor = '    required = [original] + [item for item in history if human(item)]'
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
