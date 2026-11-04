"""Read closed numerical and executable results; never execute candidate cells."""
from pathlib import Path
import sys

from lora6k_state import read, atomic, sha, identity
from weight_editor_runtime import require, usage, check_files


def audit_inference(root):
    root=Path(root);plan=read(root/'manifest.json')
    require(identity(plan)==(root/'manifest.sha256').read_text().strip(),'Plan changed')
    check_files(root/'code',plan['code']);check_files(root,plan['data'])
    rows=[]
    for folder in sorted((root/'runs').iterdir()):
        if not folder.is_dir():continue
        closed=read(folder/'CLOSED.json');require(closed['owned_worker_closed'],'Owned worker still active')
        row={'call':folder.name,'status':closed['status'],'guard':closed.get('guard'),'closed':True}
        if (folder/'usage.json').exists():
            ledger=read(folder/'usage.json');row['usage']=usage(folder,ledger['binding'])
            result=read(folder/'RESULT.json')
            req=root/'requests'/(folder.name+'.json')
            require(result['request_sha256']==sha(req) and result['token']==closed['token']==ledger['binding']['nonce'],'Inference binding mismatch')
            for case in read(req)['cases']:
                path=folder/(case['id']+'.json')
                if path.exists():
                    response=read(path)
                    require(response['generated_tokens']==row['usage']['per_case'][case['id']],'Response token count mismatch')
        else:
            require(not closed.get('launcher_pid'),'Missing usage for a launched worker')
            row['usage']={'charged_tokens':0,'measurement_complete':True,'kind':'Admission stopped before model launch'}
        rows.append(row)
    vms=[{'path':str(p),'closed':read(p)['owned_vm_closed']} for p in root.glob('**/vm.json')]
    require(all(v['closed'] for v in vms),'Owned VM still active')
    return {'calls':rows,'vm_receipts':vms,'new_charged_tokens':sum(r.get('usage',{}).get('charged_tokens',0) for r in rows),
        'usage_complete':all(r.get('usage',{}).get('measurement_complete',False) for r in rows),'owned_process_receipts_closed':True}


def report(project,patch_root,code_root):
    project,patch_root,code_root=map(Path,(project,patch_root,code_root))
    patch,code=read(patch_root/'RESULT.json'),read(code_root/'RESULT.json')
    require(patch['status']=='completed' and code['status']=='completed','Only completed publications get a closed report')
    audits={'patch':audit_inference(patch_root),'code':audit_inference(code_root)}
    target=read(patch_root/'independent-results.json')
    if read(patch_root/'manifest.json').get('remaining_work'):
        ref=read(patch_root/'manifest.json')['remaining_work'];prior=Path(ref['prior_root'])
        require(sha(prior/'independent-results.json')==ref['prior_results_sha256'],'Original partial results changed')
        audits['completed_first_patch']=audit_inference(prior)
        saved=read(prior/'independent-results.json')['five_weights']
        require(len(saved)==8 and 'five_weights' not in target,'Duplicate or missing completed first patch')
        target['five_weights']=saved
        old=read(prior/'RESULT.json')['results']['five_weights'];patch['results']['five_weights']=old
    base={r['id']:r for r in target['baseline']}
    cost_pairs={};failures={}
    for arm,rows in target.items():
        if arm=='baseline':continue
        paired=[r for r in rows if r['correct'] and base[r['id']]['correct']]
        cost_pairs[arm]={'matched_correct':len(paired),'ids':[r['id'] for r in paired],
            'candidate_tokens':sum(r['generated_tokens'] for r in paired),'baseline_tokens':sum(base[r['id']]['generated_tokens'] for r in paired),
            'timing_caveat':'Shared GPU permitted; timing is not a controlled idle comparison'}
        failures[arm]=[{'id':r['id'],'finish_reason':r['finish_reason'],'reference_correct':r['reference_correct'],
            'closed_thinking':r['closed_thinking'],'response_sha256':sha(r['response_file'])} for r in rows if not r['correct']]
    code_rows=read(code_root/'code-results.json');diagnostic={}
    for arm,rows in code_rows.items():
        diagnostic[arm]={split:{'correct':sum(r['correct'] for r in rows if r['split']==split),
            'numeric_and_test_correct':sum(bool(r.get('numeric_state_correct') and r.get('correct_candidate_test_coverage')) for r in rows if r['split']==split),
            'checked':sum(r['split']==split for r in rows)} for split in ('dev','confirmation')}
    # Full generated code remains private and inert. Summarize failures from VM effects.
    code_failures={arm:[{'id':r['id'],**{k:r.get(k) for k in ('numeric_state_correct','correct_candidate_test_coverage','test_calls','submitted','cell_error','error')}}
        for r in rows if not r['correct']] for arm,rows in code_rows.items()}
    closed={'status':'complete','target_results':patch['results'],'diagnostic_results':diagnostic,
        'target_failures':failures,'code_failures':code_failures,'matched_correct_costs':cost_pairs,'audits':audits,
        'no_new_manual_patch':'No additional manual 4B patch was selected. A generated-code fixture result alone does not identify a new causal weight intervention; the earlier confidence-margin proxy remains insufficient.',
        'limits':['Intermediate patches were selected by the operator from practice success, not submitted/retained by the model.',
            'The eight target checks are familiar fixed cases, not a fresh generalization set.',
            'The code diagnostic is single-cell fixture execution with explicit instructions and protocol stubs, not an autonomous math-repair workflow.',
            'Synthetic normalization fixtures are 8x8 matrices while the real 0.8B normalization tensor is a vector. Indexing errors on the fixture are not demonstrated real-target failures.',
            'The diagnostic helper list did not explicitly specify the zero-argument submit() signature. Two edited-model cells completed numeric work/testing but passed a string to submit.',
            'One result per case/model; no repeatability claim or foundation-model training.']}
    atomic(patch_root/'CLOSED-AUDIT.json',closed)
    text=['# Intermediate patches and executable editing diagnosis', '',
        'Saved promising patches were reconstructed exactly and checked separately from the models’ final submissions. No historical score was replaced.', '',
        '| 0.8B target | Complete correct / 8 | Reference matches / 8 |', '| --- | ---: | ---: |']
    labels={'baseline':'Original (reused verified control)','five_weights':'Unchanged 4B’s early five-weight patch',
        'threshold_with_rounding':'Manually edited 4B’s early threshold + rounding','rounding_only':'Rounding-only attribution control'}
    for arm,row in patch['results'].items():text.append(f"| {labels[arm]} | {row['correct']}/{row['checked']} | {row['reference_correct']}/{row['checked']} |")
    text+=['','These are operator-selected intermediate states, not model-retained final upgrades. Their fixed qualification cases were used previously; positive results would still need fresh cases.', '',
        '## Experimental workspace', '',
        'The default seed is unchanged. The opt-in numerical broker now preserves untouched F32 bits, rounds only deliberately changed values, supports named candidate checkpoints/restores, and binds test receipts to exact candidate content. It rejects development IDs passed as literal activation-probe text.', '',
        'The actual historical normalization example intended 56 changes but saved 900. The precise conversion changes exactly 56; a rounding-only control changes 875. The reconstructed historical candidates retain their original rounding.', '',
        '## Executable diagnostic', '',
        '| 4B Q8 editor | Numeric state + candidate testing / 8 | Complete requested cell / 8 |', '| --- | ---: | ---: |']
    for arm,splits in diagnostic.items():text.append(f"| {arm} | {sum(v['numeric_and_test_correct'] for v in splits.values())}/8 | {sum(v['correct'] for v in splits.values())}/8 |")
    text+=['','Both editors received the same new tools and instructions. Complete generated cells ran only in disposable VMs. The grader inspected resulting tensor values, preservation of other edits, candidate-test routing and explicit submission. It did not score a multiple-choice answer or accept a success claim.', '',
        'These are controlled, explicit single-cell fixture tasks. Their forward receipts are protocol stubs, not real 0.8B math answers. They do not establish autonomous discovery, retention or end-to-end improvement.', '',
        'The unchanged editor passed both selective restores, both checkpoint restores and both candidate-testing tasks. It selected a matrix row instead of a flattened element in one weight task and cut off in the other. The edited editor corrected the first weight task but indexed past the matrix in the second. Two otherwise functional restore cells failed by calling submit(message). All these original scores and raw cells remain unchanged.', '',
        'Two diagnostic limitations matter: the synthetic normalization fixtures were matrices even though the real 0.8B normalization tensor is a vector; and the helper list did not explicitly document submit() as a zero-argument function. These constrain any claim about real weight-editing skill or a regression caused by the manual patch. No extra manual intervention was selected from them.', '',
        'The current experimental guidance now documents zero-argument helpers and stored array shapes/flattened indexing. That follow-up is offline-checked only; neither frozen arm was repaired or rerun. Correctness, completion and calling costs remain separate.', '',
        '## Intervention decision and validation', '', closed['no_new_manual_patch'], '',
        'Twenty-one tensor/grader CPU controls and 69 weight-editor CPU controls passed. Real-VM calibration passed four known-correct cells, split/reordered candidate tests and the comparison route, and rejected four no-ops, a false rollback and a development-ID activation probe. Actual original-only routing was rejected separately by a CPU boundary control; its VM import-based negative was not counted as a routing control. All owned inference/VM closure receipts were audited.', '',
        f"New sampled tokens: target comparison **{sum(v['new_charged_tokens'] for k,v in audits.items() if k!='code'):,}**; executable diagnostic **{audits['code']['new_charged_tokens']:,}**. Journal completeness: {all(v['usage_complete'] for v in audits.values())}. Reused control tokens are not counted as new inference.", '',
        'Token efficiency is compared only on matched independently correct cases in the private closed audit. Shared-GPU timings are not treated as an idle-machine speed comparison. No training, download, paid API call, deployment or commit/push occurred.', '',
        f"Private evidence: `{patch_root.relative_to(project).as_posix()}/CLOSED-AUDIT.json` and `{code_root.relative_to(project).as_posix()}/code-results.json`."]
    path=project/'evaluations/weight-space-intermediate-and-code-findings-2026-11-04.md';path.write_text('\n'.join(text)+'\n',encoding='utf8')
    return {'report':str(path),'audit':str(patch_root/'CLOSED-AUDIT.json'),'new_tokens':sum(r['new_charged_tokens'] for r in audits.values())}


if __name__=='__main__':print(report(*sys.argv[1:]))
