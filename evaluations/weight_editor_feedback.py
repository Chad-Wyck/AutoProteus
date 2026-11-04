"""Inert feedback diagnostics and rendering for opt-in weight-editor studies."""
import copy
import json

from weight_editor_runtime import require


PROFILES = {
    'cold': {'temperature': .2, 'top_p': .8, 'top_k': 20, 'thinking': False, 'output_tokens': 512},
    'warm': {'temperature': .7, 'top_p': .8, 'top_k': 20, 'thinking': False, 'output_tokens': 512},
    'reasoning': {'temperature': .6, 'top_p': .95, 'top_k': 20, 'thinking': True, 'output_tokens': 2048},
}
QUESTION = (
    'Read the measured results. Return exactly one JSON object with these fields: '
    'baseline_correct_ids (sorted IDs correct in development), candidate_correct_ids '
    '(sorted IDs correct in the latest measured trial), unfinished_ids (sorted IDs '
    'whose latest trial finish_reason is length), tested_strengths (all measured '
    'trial coefficient pairs, sorted and without duplicates), next_action. '
    'next_action is stop only if the latest trial preserves every baseline-correct '
    'case AND has strictly more correct cases; otherwise revise. No weight proposal '
    'or explanation is requested. Use reported measurements, not guesses about weights.'
)


def expected(feedback):
    baseline = {r['id'] for r in feedback['development'] if r['correct']}
    measured = [t for t in feedback['trials'] if 'results' in t]
    require(bool(measured), 'Diagnostic requires a measured trial')
    latest = measured[-1]['results']
    correct = {r['id'] for r in latest if r['correct']}
    return {
        'baseline_correct_ids': sorted(baseline),
        'candidate_correct_ids': sorted(correct),
        'unfinished_ids': sorted(r['id'] for r in latest if r['finish_reason'] == 'length'),
        'tested_strengths': sorted({tuple(t['proposal']['strengths']) for t in measured}),
        'next_action': 'stop' if baseline <= correct and len(correct) > len(baseline) else 'revise',
    }


def compact(feedback):
    """Join all arms by ID; keep factual results apart from historical prose."""
    baseline = {r['id']: r for r in feedback['development']}
    controls = {r['id']: r for r in feedback.get('fixed_control', [])}
    trials = [t for t in feedback['trials'] if 'results' in t]
    latest = {r['id']: r for r in trials[-1]['results']} if trials else {}
    def outcome(row):
        if row is None:
            return None
        return {k: row[k] for k in ('correct', 'finish_reason', 'generated_tokens')}
    return {
        'reference_strengths': feedback.get('reference_strengths', {'baseline': [1., 1.], 'fixed_control': [1.1, 1.1]}),
        'cases': [{'id': name, 'baseline': outcome(baseline[name]),
                   'fixed_control': outcome(controls.get(name)), 'latest_candidate': outcome(latest.get(name))}
                  for name in sorted(baseline)],
        'trials': [{'strengths': t['proposal']['strengths'],
                    'results': [{'id': r['id'], **outcome(r)} for r in sorted(t['results'], key=lambda r: r['id'])]}
                   if 'results' in t else copy.deepcopy(t) for t in feedback['trials']],
        'development_cases': feedback.get('development_cases', []),
        'development_gold_answers': feedback.get('development_gold_answers', {}),
    }


def render(feedback, style, profile, instruction=QUESTION):
    require(style in ('rich', 'compact') and profile in PROFILES, 'Unknown feedback/profile')
    visible = feedback if style == 'rich' else compact(feedback)
    data = json.dumps(visible, ensure_ascii=True, allow_nan=False).replace('<', r'\u003c')
    suffix = '<think>\n' if PROFILES[profile]['thinking'] else '<think>\n\n</think>\n\n'
    return ('<|im_start|>system\nYou are AutoProteus.\n' + instruction + '<|im_end|>\n'
            '<|im_start|>user\n' + data + '<|im_end|>\n<|im_start|>assistant\n' + suffix)


def final_json(raw):
    """A final answer, not a JSON object found somewhere inside reasoning."""
    final = raw.rsplit('</think>', 1)[-1]
    for marker in ('<|im_end|>', '<|endoftext|>'):
        final = final.removesuffix(marker).rstrip()
    final = final.strip()
    if final.startswith('```') and final.endswith('```'):
        lines = final.splitlines()
        require(lines[0] in ('```', '```json'), 'Unknown fenced language')
        final = '\n'.join(lines[1:-1])
    value = json.loads(final)
    require(isinstance(value, dict), 'Expected final JSON object')
    return value


def grade(raw, target):
    try:
        actual = final_json(raw)
        # JSON round-trip normalizes coefficient tuples to arrays.
        normalized = json.loads(json.dumps(target))
        return {'status': 'ok', 'correct': actual == normalized, 'actual': actual, 'expected': normalized}
    except (ValueError, TypeError, RuntimeError) as error:
        return {'status': 'ok', 'correct': False, 'parse_error': str(error), 'expected': json.loads(json.dumps(target))}


def diagnostic_feedback(diagnostics, index, *, confirmation=False):
    """Four outcome-only counterfactuals; no heldout math questions or answers."""
    require(index in range(4), 'Four fixed diagnostic cases')
    ids = ['practice-c', 'practice-d'] if confirmation else ['practice-a', 'practice-b']
    baseline_ok = [index < 2, index >= 2]
    candidate_ok = [True, True] if index % 2 else ([True, False] if index == 0 else [True, False])
    pair = ([1.03, 1.17] if confirmation else [1.12, 1.28]) if index % 2 == 0 else ([.93, 1.07] if confirmation else [1.05, 1.15])
    def rows(flags, reverse=False):
        result = [{'id': name, 'correct': ok, 'status': 'ok', 'prediction': 'verified' if ok else None,
                   'finish_reason': 'eos' if ok else 'length', 'generated_tokens': 500 if ok else 32768,
                   'answer_omitted': not ok,
                   'response_tail': f'Measured output for {name}: ' + ('finished and verified.' if ok else 'unfinished at output limit.')}
                  for name, ok in zip(ids, flags)]
        return list(reversed(result)) if reverse else result
    return {
        'development': rows(baseline_ok, True), 'fixed_control': rows([not x for x in baseline_ok]),
        'development_cases': [{'id': name, 'problem': 'Synthetic result-reading exercise; do not solve math.'} for name in ids],
        'development_gold_answers': {name: 'verified' for name in ids},
        'weight_diagnostics': copy.deepcopy(diagnostics),
        'reference_strengths': {'baseline': [1., 1.], 'fixed_control': [1.1, 1.1]},
        'trials': [{'proposal': {'strengths': pair, 'rationale': 'A previous measured proposal.'}, 'results': rows(candidate_ok)}],
    }
