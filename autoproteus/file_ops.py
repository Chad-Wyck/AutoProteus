"""Read sections and exact edits, using Workspace path and cancellation checks."""


def read_file(self, tool, args):
    """Model-facing inspection, not a processing helper; use Workspace.read_text."""
    from .tools import LIMIT, READ_DEFAULT, Cancelled
    path = self.path(args["path"])
    if tool == "read_file" and any(key in args for key in ("offset", "start", "length")):
        raise ValueError("read_file reads the whole file; use read_section with character start and length")
    start = args.get("start", 0) if tool == "read_section" else 0
    length = args.get("length", READ_DEFAULT) if tool == "read_section" else LIMIT
    if "offset" in args:
        raise ValueError("Use read_section with a character start, not a byte offset")
    if type(start) is not int or start < 0:
        raise ValueError("start must be a nonnegative character position; use next_start to continue")
    if type(length) is not int or not 1 <= length <= LIMIT:
        raise ValueError(f"length must be between 1 and {LIMIT} characters")
    try:
        # Preserve CRLF and skip by characters without allocating the prefix.
        with path.open("r", encoding="utf-8", newline="") as stream:
            remaining = start
            while remaining:
                if self.cancel.is_set():
                    raise Cancelled()
                skipped = stream.read(min(remaining, LIMIT))
                if not skipped:
                    break
                remaining -= len(skipped)
            content = stream.read(length + 1)
    except UnicodeDecodeError:
        raise ValueError("Read a valid UTF-8 text file") from None
    eof = len(content) <= length
    if tool == "read_file" and not eof:
        raise ValueError(f"This file exceeds {LIMIT} characters; use read_section with start and length")
    content = content[:length]
    return {"path": args["path"], "content": content, "start": start,
            "next_start": start + len(content), "eof": eof}


def edit_file(self, args):
    from .tools import TEXT_CHARACTER_LIMIT, Cancelled, EditConflict
    path = self.path(args["path"])
    old, new = args["old_text"], args["new_text"]
    if not isinstance(old, str) or not old or not isinstance(new, str):
        raise ValueError("Supply a nonempty old_text and a text new_text")
    if max(len(old), len(new)) > TEXT_CHARACTER_LIMIT:
        raise ValueError("Edit text must be at most 100,000 characters")
    with path.open("rb") as stream:
        raw = stream.read(TEXT_CHARACTER_LIMIT * 4 + 1)
    if len(raw) > TEXT_CHARACTER_LIMIT * 4:
        raise ValueError("Edit files of at most 100,000 UTF-8 characters")
    content = raw.decode("utf-8")
    if len(content) > TEXT_CHARACTER_LIMIT:
        raise ValueError("Edit files of at most 100,000 UTF-8 characters")
    start = content.find(old)
    if start < 0 or content.find(old, start + 1) >= 0:
        count, locations, position = 0, [], start
        while position >= 0 and count < 50:
            count += 1
            if len(locations) < 3:
                context_start = max(0, position - 80)
                locations.append({'start': position, 'line': content.count('\n', 0, position) + 1,
                                  'context_start': context_start,
                                  'content': content[context_start:position + min(len(old), 160) + 80]})
            position = content.find(old, position + 1)
        hint = ('Read one listed location with read_section and include enough surrounding text for one match.'
                if count else 'Search for a short distinctive fragment, then read the current section and copy its exact text.')
        if not count and old.replace('\r\n', '\n') in content.replace('\r\n', '\n'):
            hint = 'The line endings differ. Read the current section and preserve its exact newline characters.'
        raise EditConflict(f'old_text {"was not found" if not count else "is ambiguous"}: {count}{"+" if position >= 0 else ""} matches. No file was changed.',
                           {'matches': count, 'matches_truncated': position >= 0, 'locations': locations, 'hint': hint})
    updated = content[:start] + new + content[start + len(old):]
    if len(updated) > TEXT_CHARACTER_LIMIT:
        raise ValueError("The edited file would exceed 100,000 characters")
    if self.cancel.is_set():
        raise Cancelled()
    if old == new:
        return {"path": str(path.relative_to(self.root)), "bytes": len(raw), "replacements": 0,
                "changed": False, "message": "No change made: replacement text matches existing text."}
    path.write_bytes(updated.encode("utf-8"))
    return {"path": str(path.relative_to(self.root)), "bytes": len(updated.encode("utf-8")), "replacements": 1, "changed": True}
