"""Inert analysis of saved sequence-isolation summaries; no inference imports."""
from lora6k_state import identity
from weight_editor_runtime import require


def analyze(result):
    require(result.get('status') == 'completed' and result.get('cleanup_complete') is True, 'Incomplete qualification')
    models = []
    for model in result['models']:
        checks = model['checks']
        require(bool(checks) and all(type(row['passed']) is bool for row in checks), 'Missing numerical controls')
        failures = [row for row in checks if not row['passed']]
        signatures = {}
        for row in failures:
            key = identity({k: row[k] for k in ('prompt', 'position', 'max_abs', 'tv', 'argmax_equal')})
            signatures.setdefault(key, []).append(row['order'])
        models.append({'id': model['id'], 'checks': len(checks), 'passed': len(checks)-len(failures),
            'failed': failures, 'argmax_equal': sum(row['argmax_equal'] for row in checks),
            'tv_within_frozen_tolerance': sum(row['tv'] <= .001 for row in checks),
            'repeated_failure_orders': list(signatures.values()), 'raw_logit_vectors_available': False,
            'cause_established': False, 'scored_four_slot_qualified': not failures,
            'next_diagnostic': {'slots': [1, 1, 2, 4], 'orders': [[0, 1, 2, 3], [3, 1, 0, 2]],
                'save': ['full_logits', 'input_ids', 'forced_token_ids', 'sequence_ids', 'engine_hashes', 'context_parameters'],
                'atol': .001, 'rtol': .001, 'total_variation_limit': .001,
                'repeat_solo_first': True, 'no_tolerance_relaxation': True,
                'target': 'Same frozen repaired 0.8B F32; no weight edits', 'gpu_execution_started': False}})
    return {'status': 'offline_analysis_complete', 'models': models, 'gpu_accessed': False,
            'interpretation': 'An order-repeated summary is not proof of either harmless rounding or sequence contamination. New full-vector controls are required.'}
