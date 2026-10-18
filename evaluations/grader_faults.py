"""Reviewed, single-defect controls. These bytes execute only in guests."""
import base64
import copy


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Grader control anchor changed')
    return text.replace(old, new, 1)


def controls(source, reference):
    """Yield (id, feature, expected rejecting cases, inert source bundle)."""
    faults = [
        ('missing_default', 'csv_preview', ('default_limit',), 'limit = args.get("limit", 5)', 'limit = args["limit"]'),
        ('boolean_integer', 'csv_preview', ('invalid_limit_True',), 'type(limit) is not int', 'not isinstance(limit, int)'),
        ('exact_hash_limit', 'sha256_file', ('exact',), 'len(raw) > 1048576', 'len(raw) >= 1048576'),
        ('byte_character_limit', 'csv_preview', ('unicode_exact_5',),
            'rows = list(csv.reader(io.StringIO(self.read_text(path), newline="")))',
            'text = self.read_text(path)\n            if len(text.encode("utf-8")) > 100000: raise ValueError("Too large")\n'
            '            rows = list(csv.reader(io.StringIO(text, newline="")))'),
        ('false_write_success', 'format_json', ('object', 'unicode_output_exact'),
            'return self.write_text(path, text)', 'return {"path": str(path.relative_to(self.root)), "bytes": len(text.encode("utf-8"))}'),
        ('damage_rejected_input', 'format_json', ('preserve_invalid', 'preserve_expanded'),
            'text = json.dumps(json.loads(self.read_text(path)), ensure_ascii=False, sort_keys=True, indent=2)',
            'original = self.read_text(path)\n            path.write_bytes(b"damaged")\n'
            '            text = json.dumps(json.loads(original), ensure_ascii=False, sort_keys=True, indent=2)'),
        ('exact_output_limit', 'format_json', ('unicode_output_exact',),
            'return self.write_text(path, text)',
            'if len(text) >= 100000: raise ValueError("Too large")\n            return self.write_text(path, text)'),
    ]
    for name, feature, cases, old, new in faults:
        mutated = copy.deepcopy(source)
        faulty = replace_once(reference, old, new)
        for item in mutated:
            if item['path'] == 'autoproteus/tools.py':
                text = base64.b64decode(item['data']).decode('utf-8')
                item['data'] = base64.b64encode(replace_once(text, reference, faulty).encode()).decode()
        yield name, feature, cases, mutated
    mutated = copy.deepcopy(source)
    for item in mutated:
        if item['path'] == 'autoproteus/providers.py':
            text = base64.b64decode(item['data']).decode()
            # Only the reviewed calibration definition is changed.
            anchor = "'csv_preview': ('Calibration file tool.', {'path': {'type': 'string'}, 'limit': {'type': 'integer'}}, ['path'])"
            text = replace_once(text, anchor, anchor[:-2] + ", 'limit'])")
            item['data'] = base64.b64encode(text.encode()).decode()
    yield 'required_default_schema', 'csv_preview', ('optional_limit_schema',), mutated
