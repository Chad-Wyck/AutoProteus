"""Reassess saved accepted candidates with current graders; no model inference."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'evaluations')]
import generalization as study
from controller.evaluation import freeze_source, source_identity
from controller.storage import Store, atomic_json, now


def main(args):
    source_dir, output = [(ROOT / p).resolve() for p in (args.input, args.output)]
    if not all(p.is_relative_to((ROOT / '.data').resolve()) for p in (source_dir, output)):
        raise ValueError('Use private project .data directories')
    output.mkdir(parents=True, exist_ok=False)
    plan = json.loads((source_dir / 'plan.json').read_text())
    summary = json.loads((source_dir / 'summary.json').read_text())
    record = {'started': now(), 'kind': 'Regrading saved evidence, not fresh model attempts',
              'source_sha256': plan['source_sha256'], 'graders': {
                  name: hashlib.sha256((ROOT / 'evaluations' / name).read_bytes()).hexdigest()
                  for name in ('generalization-probe.py', 'generalization.py', 'local-model-benchmark.py')}, 'candidates': []}
    store = Store(output / 'sessions')
    for profile in summary['profiles']:
        for row in profile['upgrades']:
            if not row.get('review', {}).get('accepted'): continue
            candidate_path = source_dir / profile['directory'] / row['task'] / 'review/candidate-source.json'
            candidate = json.loads(candidate_path.read_text())
            if source_identity(candidate) != row['review']['source_sha256']:
                raise ValueError('Saved candidate hash mismatch')
            frozen = freeze_source(store, candidate, 'Saved model candidate, no new inference')
            result = {'session': frozen['id'], 'status': row['run']['status'], 'timed_out': row['run']['timed_out']}
            review = study.assess(store, plan['source'], result, row['task'], output / profile['directory'] / row['task'])
            unavailable = any(component.get('run') and (component['run'].get('timed_out') or
                (not component['run'].get('passed') and component['run'].get('model_requests', 0) == 0))
                for component in (review.get('feature', {}), review.get('public', {})))
            item = {'profile': profile['directory'], 'task': row['task'], 'candidate_sha256': source_identity(candidate),
                    'original_accepted': True, 'regraded_accepted': None if unavailable else review['accepted'],
                    'verification_unavailable': unavailable,
                    'verified_upgrade': review['verified_upgrade'], 'checks': review.get('feature', {}).get('probe', {}).get('checks'),
                    'regressions': review.get('regressions', {}).get('passed'), 'public': review.get('public', {}).get('passed')}
            record['candidates'].append(item)
            atomic_json(output / 'results.json', record)
            print('REGRADED', item['profile'], item['task'], item['regraded_accepted'], flush=True)
    record['finished'] = now(); atomic_json(output / 'results.json', record)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True); p.add_argument('--output', required=True)
    main(p.parse_args())
