"""Opt-in receipt-cue source construction; never executes guest source on host."""
import base64
import copy


SCOPE = {'execution_route': 'development_helper', 'scope': 'invocation_only',
    'notice': 'This is a development-helper result, not a direct call to a supplied workspace tool. '
              "A successful invocation does not establish independent approval or completion of the user's task."}


def replace_once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Receipt experiment source changed; review before preparing')
    return text.replace(before, after, 1)


def variant(source):
    """Return a copied seed with scoped receipts; leave the default seed alone."""
    result = copy.deepcopy(source)
    matches = [item for item in result if item['path'] == 'seed.py']
    if len(matches) != 1:
        raise ValueError('One seed entry point is required')
    item = matches[0]
    text = base64.b64decode(item['data'], validate=True).decode('utf-8')
    text = replace_once(text, '    from autoproteus.tools import Workspace\n    try:',
        '    from autoproteus.tools import Workspace\n    scope = ' + repr(SCOPE) + '\n    try:')
    for before, after in (
        ("'result': value}, ensure_ascii=True)", "'result': value, **scope}, ensure_ascii=True)"),
        ("'error': type(error).__name__ + ': ' + str(error)}, ensure_ascii=True)",
         "'error': type(error).__name__ + ': ' + str(error), **scope}, ensure_ascii=True)")):
        text = replace_once(text, before, after)
    item['data'] = base64.b64encode(text.encode('utf-8')).decode('ascii')
    return result


def invoker(text):
    """Return the matching guest-only fixture, to freeze with --invoke-tool-file."""
    return replace_once(text, "'result': result}, ensure_ascii=True)",
        "'result': result, **" + repr(SCOPE) + "}, ensure_ascii=True)")
