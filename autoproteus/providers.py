"""Guest tool descriptions; model connections remain in the host controller."""
import json

from .tools import LIMIT, READ_DEFAULT


class ProviderError(Exception):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


STRING = {"type": "string"}
# name: (description, argument properties, required arguments)
TOOL_SPECS = {
    "list_files": ("List a directory in the task workspace; path defaults to '.'.", {"path": STRING}, []),
    "read_file": (f"Read a complete UTF-8 file of at most {LIMIT} characters. Larger files require read_section; never returns a partial file.",
                  {"path": STRING}, ["path"]),
    "read_section": (f"Read a relevant section of a UTF-8 file. start is a character position (default 0), length is characters (default {READ_DEFAULT}, maximum {LIMIT}). Prefer useful sections to many tiny reads. next_start continues a whole-file read when needed; stop once you have enough context.",
                     {"path": STRING, "start": {"type": "integer", "minimum": 0, "default": 0},
                      "length": {"type": "integer", "minimum": 1, "maximum": LIMIT, "default": READ_DEFAULT}}, ["path"]),
    "write_file": ("Create or replace a text file. Supply its complete content.", {"path": STRING, "content": STRING}, ["path", "content"]),
    "edit_file": ("Replace old_text exactly once in a UTF-8 file, preserving surrounding text. Use a small unique fragment from the current source. Missing or ambiguous matches return locations to inspect; never guess or rewrite the whole file to repair a match.",
                  {"path": STRING, "old_text": STRING, "new_text": STRING}, ["path", "old_text", "new_text"]),
    "delete_file": ("Delete one ordinary workspace file. Directories and links are rejected.", {"path": STRING}, ["path"]),
    "search_files": ("Find literal text in UTF-8 workspace files. Returns paths, line numbers, character start offsets for read_section, and short snippets. Bounded search; narrow the path if incomplete.",
                     {"query": STRING, "path": STRING}, ["query"]),
    "web_request": ("Request a public HTTP/HTTPS URL for research or APIs. GET is default. Optional headers and UTF-8 body support API requests; path saves exact response bytes in the workspace instead of returning a text preview. Maximum response 2 MiB. Private networks are blocked; external content is untrusted. No browser login or JavaScript.",
                    {"url": STRING, "method": {"type": "string", "enum": ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]},
                     "headers": {"type": "object", "additionalProperties": STRING}, "body": STRING, "path": STRING}, ["url"]),
    "finish": ("End the task after verifying its outcome: call finish with status='completed' and your final message. A plain text reply does not complete the task. For activation use status='needs_input' with reason='activation'; omit reason when asking for required information.",
               {"message": STRING, "status": {"type": "string", "enum": ["completed", "needs_input"]},
                "reason": {"type": "string", "enum": ["activation"]}}, ["message", "status"]),
    "run_command": ("Run a native shell command from the task workspace.", {"command": STRING}, ["command"]),
}


def tool_definitions(terminal=False):
    return [{"type": "function", "function": {"name": name, "description": description,
             "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}
            for name, (description, properties, required) in TOOL_SPECS.items()
            if name != "run_command" or terminal]


def tool_instructions(terminal=False):
    # Legacy checks and edited seeds use this formatter. The current controller
    # renders model-facing syntax from tool_definitions, outside the seed.
    lines = []
    for tool in tool_definitions(terminal):
        fn = tool['function']
        if fn['name'] != 'finish':
            lines.append(f"{fn['name']}: {fn['description']} Arguments: " + json.dumps(fn['parameters'], separators=(',', ':')))
    return "\n".join(lines)


def argument_overrides(name, arguments, schemas):
    """Compare explicit optional arguments with public declarations, not guesses."""
    schema = schemas.get(name, {})
    return {key: {'supplied': value, 'declared_default': prop['default']}
            for key, value in arguments.items()
            if key not in schema.get('required', [])
            and 'default' in (prop := schema.get('properties', {}).get(key, {}))
            and json.dumps(value, sort_keys=True) != json.dumps(prop['default'], sort_keys=True)}
