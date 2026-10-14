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
