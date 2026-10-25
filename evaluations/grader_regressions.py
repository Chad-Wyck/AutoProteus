"""Read checksummed real model candidates as data; execution belongs in a VM."""
import gzip
import hashlib
import json
from pathlib import Path

from controller.evaluation import source_identity

FIXTURES = Path(__file__).resolve().parent / 'fixtures/grader-candidates'


def cases():
    return json.loads((FIXTURES / 'manifest.json').read_text(encoding='utf-8'))['cases']


def load_case(case):
    name = case['file']
    if Path(name).name != name or not name.endswith('.json.gz'):
        raise ValueError('Invalid grader fixture path')
    path = FIXTURES / name
    if path.stat().st_size > 2 * 1024**2:
        raise ValueError('Compressed grader fixture too large')
    packed = path.read_bytes()
    if hashlib.sha256(packed).hexdigest() != case['gzip_sha256']:
        raise ValueError('Grader fixture checksum mismatch')
    with gzip.open(path, 'rb') as stream:
        raw = stream.read(4 * 1024**2 + 1)
    if len(raw) > 4 * 1024**2:
        raise ValueError('Expanded grader fixture too large')
    source = json.loads(raw)
    if source_identity(source) != case['source_sha256']:
        raise ValueError('Grader candidate source mismatch')
    return source
