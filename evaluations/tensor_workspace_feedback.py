"""Host-owned model identity receipts; no claims of correctness from provenance."""
from weight_editor_runtime import require


def evaluated_receipt(policy,view,model,mode,ids,cached_ids=()):
    require(view in ('original','edited') and mode in ('generate','probe'),'Invalid evaluated view')
    candidate=view=='edited';cached=set(cached_ids)
    ledger=None
    if hasattr(policy,'mark_evaluated'):
        ledger=policy.mark_evaluated(mode,ids,model['sha256'],view=view)
    state=policy.candidate_state()
    return {'ledger_receipt':ledger,'tested_model':'CURRENT CANDIDATE' if candidate else 'IMMUTABLE ORIGINAL BASELINE',
        'weights_sha256':model['sha256'],'candidate_id':state['candidate_id'] if candidate else None,
        'evaluated_revision':state['revision'] if candidate else 0,'saved_edits_applied':candidate and bool(policy.edits),
        'changed_tensor_count':len(policy.edits) if candidate else 0,'mode':mode,
        'cached_result_ids':[i for i in ids if i in cached],'new_inference_ids':[i for i in ids if i not in cached],
        'notice':('These results evaluate ALL currently saved edits.' if policy.edits else 'No edits are saved; candidate weights equal the original.')
            if candidate else 'ORIGINAL ONLY: saved edits are NOT applied. These results do not test your changes.'}


def observation_summary(row,handle):
    """Keep opaque array handles visible even in a four-text probe batch."""
    return {'id':row['id'],'npz_handle':handle,'top_tokens':row['top_tokens'][:5],
        'activation_count':len(row['activations']),'activation_examples':dict(list(row['activations'].items())[:4]),
        'full_arrays':'load_observation(npz_handle) returns all captured arrays, including logits.'}
