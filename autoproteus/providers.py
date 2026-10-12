"""Guest tool descriptions; model connections remain in the host controller."""
class ProviderError(Exception):
    def __init__(self, message, response=None):
        super().__init__(message)
        self.response = response


def tool_definitions(terminal=False):
    def definition(name, description, properties, required):
        return {"type": "function", "function": {"name": name, "description": description,
                "parameters": {"type": "object", "properties": properties, "required": required}}}
    string = {"type": "string"}
    tools = [
        definition("list_files", "List a directory in the task workspace.", {"path": string}, []),
        definition("read_file", "Read UTF-8 text: offset is bytes, length is characters (default 1000, maximum 12000). Continue at next_offset; eof marks the end.",
                   {"path": string, "offset": {"type": "integer", "minimum": 0},
                    "length": {"type": "integer", "minimum": 1, "maximum": 12000}}, ["path"]),
        definition("write_file", "Create or replace a text file. Supply its complete content.", {"path": string, "content": string}, ["path", "content"]),
        definition("edit_file", "Replace old_text exactly once in a UTF-8 file, preserving surrounding text. Missing or ambiguous matches fail; read first.",
                   {"path": string, "old_text": string, "new_text": string}, ["path", "old_text", "new_text"]),
        definition("finish", "Report verified completion, or ask the user for required information.",
                   {"message": string, "status": {"type": "string", "enum": ["completed", "needs_input"]}}, ["message", "status"]),
    ]
    if terminal:
        tools.append(definition("run_command", "Run a native shell command from the task workspace.", {"command": string}, ["command"]))
    return tools
