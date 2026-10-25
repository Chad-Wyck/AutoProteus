"""Index historical research without regrading or executing candidate code."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from controller.storage import now


def records(path):
    if not path.exists():
        return []
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError('Invalid experiment index; original bytes were preserved')
    return rows


def backfill(root=ROOT):
    folder = root / 'evaluations'
    target = folder / 'experiment-index.jsonl'
    existing = records(target)
    seen = {row.get('record_id') for row in existing}
    additions = []
    for path in sorted(folder.glob('*findings.md')):
        raw = path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        name = path.relative_to(root).as_posix()
        key = hashlib.sha256((name + '\0' + sha).encode()).hexdigest()
        if key in seen:
            continue
        text = raw.decode('utf-8-sig')
        paragraphs = [p.strip().replace('\n', ' ') for p in text.split('\n\n') if p.strip()]
        row = {'record_id': key, 'type': 'historical_report', 'indexed_at': now(),
               'report': name, 'report_sha256': sha, 'title': paragraphs[0][:200] if paragraphs else name,
               'summary': ' '.join(paragraphs[1:3])[:1500],
               'status': 'historical_not_regraded',
               'scope': 'Search index of the original report, not a fresh trial or pooled success rate.'}
        result = path.with_name(path.name.replace('findings.md', 'results.json'))
        if result.exists():
            row['results'] = result.relative_to(root).as_posix()
            row['results_sha256'] = hashlib.sha256(result.read_bytes()).hexdigest()
        additions.append(row)
    if additions:
        # A malformed existing index is rejected above before any append.
        with target.open('a', encoding='utf-8') as stream:
            for row in additions:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            stream.flush()
            import os
            os.fsync(stream.fileno())
    return additions


def search(query, path=ROOT / 'evaluations/experiment-index.jsonl'):
    words = query.casefold().split()
    return [row for row in records(path) if all(word in json.dumps(row, ensure_ascii=False).casefold() for word in words)]


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('backfill')
    find = commands.add_parser('search'); find.add_argument('query')
    args = parser.parse_args()
    values = backfill() if args.command == 'backfill' else search(args.query)
    print(json.dumps(values, ensure_ascii=False, indent=2))
