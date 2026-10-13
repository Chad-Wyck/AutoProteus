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
    "read_section": (f"Read part of a UTF-8 file. start is a character position (default 0), length is characters (default {READ_DEFAULT}, maximum {LIMIT}). Continue at next_start until eof.",
                     {"path": STRING, "start": {"type": "integer", "minimum": 0, "default": 0},
                      "length": {"type": "integer", "minimum": 1, "maximum": LIMIT, "default": READ_DEFAULT}}, ["path"]),
    "write_file": ("Create or replace a text file. Supply its complete content.", {"path": STRING, "content": STRING}, ["path", "content"]),
    "edit_file": ("Replace old_text exactly once in a UTF-8 file, preserving surrounding text. Missing or ambiguous matches fail; read first.",
                  {"path": STRING, "old_text": STRING, "new_text": STRING}, ["path", "old_text", "new_text"]),
    "finish": ("Report verified completion, or ask the user for required information.",
               {"message": STRING, "status": {"type": "string", "enum": ["completed", "needs_input"]}}, ["message", "status"]),
    "run_command": ("Run a native shell command from the task workspace.", {"command": STRING}, ["command"]),
}


def tool_definitions(terminal=False):
    return [{"type": "function", "function": {"name": name, "description": description,
             "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False}}}
            for name, (description, properties, required) in TOOL_SPECS.items()
            if name != "run_command" or terminal]


def tool_instructions(terminal=False):
    # JSON replies use a status instead of calling the native finish tool.
    lines = []
    for tool in tool_definitions(terminal):
        fn = tool['function']
        if fn['name'] != 'finish':
            lines.append(f"{fn['name']}: {fn['description']} Arguments: " + json.dumps(fn['parameters'], separators=(',', ':')))
    return "\n".join(lines)
