"""Scripted guest checks for retrieval and usage anchors. No provider connection."""
import json
from pathlib import Path
import sys
sys.path.insert(0, 'harness')
from autoproteus.tools import Workspace

kind = sys.argv[1]
checks = {}
workspace = Workspace(Path.cwd())
if kind == 'retrieval':
    from autoproteus.providers import tool_definitions, tool_instructions
    checks['native_registration'] = {'history_search', 'history_read'} <= {entry['function']['name'] for entry in tool_definitions()}
    checks['json_registration'] = 'history_search' in tool_instructions() and 'history_read' in tool_instructions()
    event = {'id': 'a' * 32, 'type': 'action_result', 'seed_sha256': 'b' * 64,
             'data': {'action': {'tool': 'read_file'}, 'ok': True, 'result': {'text': 'café 猫' * 1000}}}
    Path('experience').mkdir(exist_ok=True)
    Path('experience/history.jsonl').write_text(json.dumps(event) + '\n')
    found = workspace.execute('history_search', {'query': 'café'})
    checks['exact_id_and_version'] = found['matches'][0]['id'] == 'a' * 32 and found['matches'][0]['seed_sha256'] == 'b' * 64
    recovered = workspace.execute('history_read', {'id': 'a' * 32, 'start': 20, 'length': 37})
    checks['character_window'] = recovered['content'] == json.dumps(event['data'], ensure_ascii=False)[20:57] and not recovered['eof']
    checks['bounds'] = len(json.dumps(found)) < 2000
    try:
        workspace.execute('history_read', {'id': '../outside'})
        checks['path_rejected'] = False
    except ValueError:
        checks['path_rejected'] = True
elif kind == 'usage':
    from autoproteus.usage_budget import UsageBudget
    config = {'model': 'scripted', 'provider': 'hosted', 'context_tokens': 2048, 'response_tokens': 256}
    first = [{'role': 'system', 'content': 'stable'}, {'role': 'user', 'content': 'x' * 8000}]
    budget = UsageBudget()
    fallback = budget.estimate(first, [], config)
    budget.observe(first, [], config, {'prompt_tokens': 500})
    extended = first + [{'role': 'assistant', 'content': 'saved'}]
    checks['anchor_used'] = budget.estimate(extended, [], config) < fallback
    checks['rewind_invalidates'] = budget.estimate(first[:1], [], config) == UsageBudget().estimate(first[:1], [], config)
    changed = [first[0], {'role': 'user', 'content': 'y' * 8000}]
    checks['changed_prefix_invalidates'] = budget.estimate(changed, [], config) == UsageBudget().estimate(changed, [], config)
    checks['tools_invalidate'] = budget.estimate(first, [{'name': 'different'}], config) == UsageBudget().estimate(first, [{'name': 'different'}], config)
    budget.observe(first, [], config, {})
    checks['missing_usage_invalidates'] = budget.estimate(first, [], config) == fallback
else:
    raise ValueError('Unknown calibration')
Path('experience-calibration.json').write_text(json.dumps({'passed': all(checks.values()), 'checks': checks}))
