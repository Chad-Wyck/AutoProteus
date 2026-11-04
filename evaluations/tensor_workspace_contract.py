"""Explicit configuration-derived contract for new prospective teacher studies."""
from weight_editor_runtime import require
from tensor_workspace_errors import InfrastructureStop


def qualify_target_outcome(row,response):
    if row.get('status')!='ok' or type(row.get('correct')) is not bool:
        raise InfrastructureStop('Independent grader did not return a Boolean result: '+str(row.get('status')))
    result=dict(row);result['reference_correct']=row['correct'];result['closed_thinking']='</think>' in response['raw_text']
    result['correct']=bool(row['correct'] and row['finish_reason']=='eos' and result['closed_thinking'])
    return result


def pilot_brief(plan):
    limits=plan['limits'];design=plan['design']
    require(limits['forward_calls']==4 and limits['development_generated_tokens']==32768,'Unsupported call topology')
    return f'''You are AutoProteus, editing an independent copy of the original Qwen3.5 0.8B student.
Choose numerical edits using the two supplied development problems and measured feedback. No published solution or preset edit directions are supplied. No gradients, training, optimizers, internet or host commands. Embeddings, output head, final normalization and inactive MTP tensors are protected. Do not multiply an entire tensor by one scalar. Keep shapes unchanged and all values finite.
Return exactly one complete fenced Python cell per response. The isolated NumPy kernel and /work files persist. Batch related helper operations in one cell when useful. Each cell has {limits['cell_seconds']} seconds excluding controlled inference; the VM has 2GiB RAM. Print actual results or leave a helper call as the final expression. No arbitrary host execution, host mounts, credentials or network exist.
Helpers and exact meanings:
list_tensors() returns a list of dicts with name, stored shape and editable fields. Matrices use output rows/input columns; inspect shape before indexing. model_info(), edit_status() and submit() take no arguments.
load_tensor(name, rows=None, cols=None, edited=True) returns a float32 NumPy array. edited=False reads the immutable original; edited=True reads the current candidate. Transfers are at most 64MiB.
save_edit(name,array) replaces one COMPLETE tensor with its original shape. Load, modify and save that actual array; changing a local dummy array does not edit the student. Only changed values are BF16-rounded; untouched float32 bits remain exact. undo_edit(name) restores that tensor from the original.
save_checkpoint('label') retains exact saved numeric state. restore_checkpoint('label') restores it, removing later edits. Neither evaluates or selects a state, and Python variables are not restored.
test_candidate(['dev-0','dev-1']) generates using all saved edits. At most TWO candidate-generation requests total, at most two distinct supplied development IDs per request, hence at most four candidate answers. Forward failures consume calls. Each answer has an {design['target_output_tokens']}-token output cap. Return structure is {{'candidate': {{'receipt': {{...}}, 'outcomes': [{{'id': ..., 'correct': ..., 'reference_correct': ..., 'finish_reason': ..., 'generated_tokens': ..., ...}}]}}}}. Read result['candidate']['outcomes']; printing the whole result is valid.
compare_with_original(['dev-0','dev-1']) uses the same candidate-generation request allowance and also displays cached immutable-original baseline outcomes in result['original']. Cached original results do not test current edits.
inspect_candidate([exact_prompt_text]) inspects current-candidate last-token logits/activations, generating no answer. At most TWO probe requests, exactly ONE text per request, at most 4096 input tokens. Use an actual chat-formatted prompt, not a development ID. load_observation(handle) reads returned numeric observations. Original/both-view text probes via compare_with_original(texts=...) are NOT supported in this bounded protocol.
Receipts bind exact candidate contents, settings and measured IDs; they do not imply answer correctness. The initial original baseline is shared and costs no additional teacher call. Correctness requires a reference-correct answer, EOS and closed thinking under this frozen 8K protocol; these are reported separately too. Valid capped baseline measurements permit investigation. If all baseline development cases are already correct, the study stops without replacement questions.
Limits: at most {limits['editor_calls']} responses, at most {design['editor_output_tokens']} sampled tokens per response, sharing {limits['editor_tokens']} sampled editor tokens; {limits['development_generated_tokens']} candidate-feedback tokens, two generation requests and two probes. Development has at most 30 minutes, including loading and conversion. Both response and aggregate limits apply. Structured remaining resources and exact-content coverage follow responses; unused budget does not create retries.
Use development only to choose the student. Preserve baseline-correct behavior. A development advancement requires a nonempty edit, full final-content testing, a development gain and no loss. Finish by freshly checking the chosen current candidate as needed, then submit(). Submission freezes it. End the cell cleanly: submission followed by an exception is not clean completion. Earlier errors may be recovered within remaining responses. No teacher sees another teacher's trace. Both end states freeze before independent evaluation. Do not infer improvement without measurements.
'''


def resource_feedback(study,state):
    policy=study.policy
    return {'responses_remaining':max(0,study.plan['limits']['editor_calls']-state['calls']),
        'sampled_editor_tokens_remaining':max(0,study.plan['limits']['editor_tokens']-state['editor_tokens']),
        'candidate_generation_requests_remaining':max(0,2-getattr(study,'generation_calls',0)),
        'single_text_probes_remaining':max(0,2-getattr(study,'probe_calls',0)),
        'candidate_feedback_tokens_remaining':max(0,study.plan['limits']['development_generated_tokens']-state['sampled_tokens']),
        'candidate':policy.candidate_state(),'final_content_coverage':policy.coverage(['dev-0','dev-1'],study.settings_sha256),
        'development_seconds_remaining':max(0,study.worker_deadline.end-__import__('time').monotonic())}


def development_gate(policy,state,initial,settings):
    coverage=policy.coverage(['dev-0','dev-1'],settings)
    receipts=[r for r in policy.receipt_ledger if r['receipt_index'] in coverage['receipt_indexes']]
    final={o['id']:o for r in receipts for o in r.get('outcomes',[])}
    gains=[r['id'] for r in initial if not r['correct'] and final.get(r['id'],{}).get('correct')]
    losses=[r['id'] for r in initial if r['correct'] and not final.get(r['id'],{}).get('correct')]
    clean=bool(state.get('clean_terminal') and policy.submitted)
    return {'passed':bool(clean and policy.edits and coverage['complete'] and gains and not losses),
        'clean_submission':clean,'submitted':policy.submitted,'candidate':policy.candidate_state(),
        'coverage':coverage,'gains':gains,'losses':losses,'terminal_status':state.get('status'),
        'terminal_cell_error':state.get('terminal_cell_error'),'earlier_errors':state.get('recoverable_errors',[])}
