"""Build one opt-in copied navigation seed; normal source is untouched."""
import base64
import copy
from pathlib import Path


def navigation_variant(source):
    result = copy.deepcopy(source)
    changed = set()
    for item in result:
        if item['path'] not in ('autoproteus/tools.py','autoproteus/providers.py','README.md'):
            continue
        text = base64.b64decode(item['data']).decode('utf-8')
        if item['path'] == 'autoproteus/tools.py':
            anchor = '        if tool == "list_files":'
            if text.count(anchor)!=1: raise ValueError('Navigation source anchor changed')
            text = text.replace(anchor, '        if tool == "source_outline":\n'
                '            from .source_navigation import source_outline\n'
                '            return source_outline(self, args)\n'+anchor)
        elif item['path'] == 'autoproteus/providers.py':
            anchor = 'TOOL_SPECS = {'
            if text.count(anchor)!=1: raise ValueError('Navigation catalog anchor changed')
            text = text.replace(anchor, anchor+'\n    "source_outline": ("Locate Python definitions and top-level declarations. '
                'start and length are Unicode CHARACTER offsets, not line numbers; pass them unchanged to read_section.", {"path": STRING}, ["path"]),')
        else:
            text += ('\nExperimental navigation: source_outline(path) locates definitions and module declarations such as '
                     'TOOL_SPECS. Pass its exact character start/length to read_section; line numbers are separate.\n')
        item['data'] = base64.b64encode(text.encode('utf-8')).decode()
        changed.add(item['path'])
    if len(changed)!=3 or any(item['path']=='autoproteus/source_navigation.py' for item in result):
        raise ValueError('Cannot construct a clean navigation variant')
    result.append({'path':'autoproteus/source_navigation.py', 'data':base64.b64encode(
        (Path(__file__).parent/'source_navigation.py').read_bytes()).decode()})
    return result
