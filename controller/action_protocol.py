"""Model-facing syntax. The editable seed has one neutral action interface."""
import json


NATIVE = '''RESPONSE FORMAT
Use the supplied native tools. Prefer one tool call at a time.
After verification, call finish with message and status="completed".
For required user input, call finish with your question and status="needs_input".
A plain text reply is shown to the user and pauses for their reply; it does not complete the task.
'''

JSON = '''RESPONSE FORMAT
Return exactly one JSON object per response, without Markdown fences:
{"message":"What you are doing","action":{"tool":"tool_name","arguments":{}}}
or {"message":"Your final answer","status":"completed"}
or {"message":"Your question","status":"needs_input"}.
Use exactly one action or one status. Strings must use valid JSON escaping.
Tools:
'''


def response_instructions(protocol, tools):
    if protocol == 'native':
        return NATIVE
    # One declaration from the seed drives both formats; no host tool imports.
    catalog = [item for item in tools or [] if item['function']['name'] != 'finish']
    return JSON + json.dumps(catalog, ensure_ascii=False, separators=(',', ':'))


def with_response_instructions(messages, protocol, tools):
    """Leave the seed's journal intact; keep the effective opening prefix stable."""
    instructions = response_instructions(protocol, tools)
    result = [dict(item) for item in messages]
    if result and result[0]['role'] == 'system':
        result[0]['content'] += '\n' + instructions
    else:
        result.insert(0, {'role': 'system', 'content': instructions})
    return result
