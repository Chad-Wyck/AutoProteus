"""Bounded conversation views; the full journal remains on disk."""
import json
from pathlib import Path

from .protocol import GUIDANCE, PROTOCOL
from .providers import tool_definitions
from .tools import clipped


def build_messages(session, config, steps=0, measure=None):
    todo_path = Path(session["workspace"]) / "todo.txt"
    todo = clipped(todo_path.read_text(encoding="utf-8", errors="replace"), 6000) if todo_path.exists() else ""
    session["todo"] = todo
    terminal = "Terminal commands run in the environment described below." if config["terminal"] else "Terminal access is disabled. Use the file tools."
    environment = ("This run has no AutoProteus VM protection. Code has this account's access; stay within the requested workspace."
                   if session.get('execution_mode') == 'native' else
                   "Commands run inside a disposable Linux VM. Host files, the controller and general network access are unavailable.")
    system = PROTOCOL.replace("{terminal}", terminal).replace('{environment}', environment).replace('{guidance}', GUIDANCE)
    # Keep the opening prefix stable so local runtimes can reuse its cache.
    # _run still enforces the action cap, including failed calls.
    runtime = []
    if steps >= config['max_steps']:
        runtime.append({'role': 'user', 'content':
                        'Runtime notice: The tool action allowance is exhausted. Finishing or asking for input uses no tool action. '
                        'Finish only if verified; further tool requests pause saved work for Resume. '
                        'Resume keeps the files and gives a fresh allowance; do not rush unverified changes.'})
    if config.get('activation_context'):
        runtime.append({'role': 'user', 'content': config['activation_context']})
    original = {"role": "user", "content": session["task"]}
    history = [dict(item) for item in session["messages"]]
    human_texts = {item['text'] for item in session.get('feed', []) if item.get('kind') == 'user'}
    def human(item):
        if item['role'] != 'user':
            return False
        if 'origin' in item:
            return item['origin'] == 'human'
        # Legacy journals have no origin. Prefer recorded human inputs;
        # recognize the old generated notices only as a migration fallback.
        return item['content'] in human_texts or not item['content'].startswith((
            'ACTION RESULT\n', 'Your response was not accepted:', 'Resume this task. Inspect current files',
            'Your finish call was deferred', 'A large prior action was omitted.'))
    for index, item in enumerate(history):
        if human(item) and item['content'] == session['task']:
            history.pop(index)
            break
    # Keep the original request and human follow-ups complete. Never silently
    # shorten user instructions to accommodate fixed prompts or tool schemas.
    required = [original] + [item for item in history if human(item)]
    # Count declarations in either mode. The controller renders the selected
    # wire format and checks its actual size, including response instructions.
    schemas = tool_definitions(config['terminal']) if config['provider'] != 'demo' else []
    allowance = max(0, config['context_tokens'] - config['response_tokens'] - 128) * 2
    def plain(items):
        # Journal provenance is local bookkeeping, never provider API fields.
        return [{'role': item['role'], 'content': item['content']} for item in items]
    def size(items):
        if measure is not None:
            return measure(plain(items), schemas)
        return len(json.dumps({'messages': plain(items), 'tools': schemas}, ensure_ascii=False).encode('utf-8'))
    fixed = [{"role": "system", "content": system}, original]
    if config['provider'] == 'demo':
        todo_state = [{'role': 'user', 'content': 'Current todo.txt:\n' + todo}] if todo else []
        return plain([*fixed, *history, *todo_state, *runtime])
    if size([fixed[0], *required]) > allowance:
        raise ValueError('The task, follow-up and tool instructions exceed the configured context estimate. Shorten the request or increase the context window in Settings.')
    # A notice must not prevent the free finish request or displace user text.
    if runtime and size([fixed[0], *required, *runtime]) > allowance:
        runtime = []
    if todo:
        todo_state = {'role': 'user', 'content': 'Current todo.txt:\n' + todo}
        if size([fixed[0], *required, todo_state, *runtime]) <= allowance:
            runtime.insert(0, todo_state)
    # Keep recent complete action/result groups. The full journal stays saved.
    budget = allowance - size([fixed[0], *required, *runtime])
    while len(history) > 2 and size(fixed + history + runtime) > allowance:
        index = next((i for i, item in enumerate(history) if not human(item)), None)
        if index is None:
            break
        history.pop(index)
        while len(history) > index and not human(history[index]) and history[index]['role'] != 'assistant':
            history.pop(index)
    if history and size(fixed + history + runtime) > allowance:
        limit = max(1, budget // max(1, len(history)) // 2)
        shortened = []
        for item in history:
            content = item['content']
            if human(item) or len(content.encode('utf-8')) <= limit:
                shortened.append(item)
            elif content.startswith('ACTION RESULT\n'):
                result = json.loads(content.split('\n', 1)[1])
                data = result['result']
                if result['tool'] == 'read_section' and 'next_start' in data:
                    preview = data['content'].encode('utf-8')[:max(1, limit // 2)].decode('utf-8', errors='ignore')
                    result['result'] = {**data, 'content': preview, 'context_shortened': True,
                                        'next_start': data['start'] + len(preview),
                                        'eof': data['eof'] if preview == data['content'] else False}
                elif result['tool'] == 'read_file' and 'content' in data:
                    result['result'] = {'path': data['path'], 'context_shortened': True, 'content_omitted': True,
                                        'characters': len(data['content']), 'hint': 'Use read_section with a smaller length.'}
                else:
                    result['result'] = {'context_shortened': True, 'preview': clipped(json.dumps(data, ensure_ascii=False), limit)}
                shortened.append({'role': 'user', 'content': 'ACTION RESULT\n' + json.dumps(result, ensure_ascii=False), 'origin': 'tool'})
            else:
                shortened.append({'role': 'user', 'content': 'A large prior action was omitted. Inspect current files before continuing.', 'origin': 'internal'})
        history = shortened
    while history and size(fixed + history + runtime) > allowance:
        index = next((i for i, item in enumerate(history) if not human(item)), None)
        if index is None:
            break
        history.pop(index)
        if len(history) > index and not human(history[index]) and history[index]['content'].startswith('ACTION RESULT\n'):
            history.pop(index)
    return plain([fixed[0], original, *history, *runtime])

