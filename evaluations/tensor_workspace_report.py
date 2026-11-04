"""Closed read-only evidence summary; never imports/executes candidate programs."""
from pathlib import Path
import re
import shutil

from lora6k_state import read,atomic,identity


def report(root):
    root=Path(root);plan=read(root/'manifest.json');result=read(root/'RESULT.json');runner=read(root/'runner.json')
    independent=read(root/'independent-results.json') if (root/'independent-results.json').exists() else result.get('independent',{})
    expected={c['id'] for c in read(root/'inputs.json')['cases'] if c['split']!='dev'}
    baseline={r['id']:r for r in independent.get('baseline',[])};arms={}
    for arm in plan['design']['arms']:
        rows=independent.get(arm,[]);state=result.get('arms',{}).get(arm,{})
        patch=read(root/arm/'FROZEN.json')['edits'] if (root/arm/'FROZEN.json').exists() else {}
        code=[]
        for path in sorted((root/arm).glob('turn-*.json')):
            row=read(path);code.append(row.get('code',''))
        suspected=[i for i,s in enumerate(code) if re.search(r'\b(backward|autograd|optimizer|optim\.Adam|gradient_descent)\b',s)]
        retained=[r for r in rows if baseline.get(r['id'],{}).get('correct') is True and r.get('correct') is True]
        lost=[r['id'] for r in rows if baseline.get(r['id'],{}).get('correct') is True and r.get('correct') is False]
        gained=[r['id'] for r in rows if baseline.get(r['id'],{}).get('correct') is False and r.get('correct') is True]
        arms[arm]={'state':state.get('status','unstarted'),'submitted':state.get('submitted',False),
            'changed_tensors':len(patch),'changed_entries':sum(e['changed_entries'] for e in patch.values()),
            'independent_correct':sum(r.get('correct') is True for r in rows),'independent_scheduled':len(expected),
            'independent_checked':len(rows),'untested_ids':sorted(expected-{r['id'] for r in rows}),
            'confirmation_correct':sum(r.get('correct') is True for r in rows if r['id'].startswith('confirmation-')),
            'heldout_correct':sum(r.get('correct') is True for r in rows if r['id'].startswith('heldout-')),
            'baseline_correct_retained':len(retained),'baseline_correct_lost':lost,'gained_ids':gained,
            'code_cells':len(code),'protocol_review_flags':suspected,
            'vm_closed':read(root/arm/'vm.json').get('owned_vm_closed') if (root/arm/'vm.json').exists() else None}
    phases=read(root/'usage.json')['phases'] if (root/'usage.json').exists() else {}
    owned=[read(p) for p in sorted((root/'runs').glob('*/CLOSED.json'))]
    pending=[str(p.parent.name) for p in (root/'runs').glob('*/supervisor.json') if not (p.parent/'CLOSED.json').exists()]
    summary={'status':result['status'],'manifest_sha256':identity(plan),'error':result.get('error'),
        'baseline_independent_correct':sum(r.get('correct') is True for r in baseline.values()),'baseline_checked':len(baseline),
        'arms':arms,'charged_generated_tokens':sum(r['charged_tokens'] for r in phases.values()),
        'generation_measurements_complete':bool(phases) and all(r['measurement_complete'] for r in phases.values()),
        'closed_native_workers':len(owned),'all_owned_native_workers_closed':not pending and all(r.get('owned_worker_closed') for r in owned),
        'missing_closure_receipts':pending,'free_disk_bytes':shutil.disk_usage(root).free,
        'elapsed_seconds':runner.get('ended_unix',runner['began_unix'])-runner['began_unix'],
        'interpretation':'One paired pilot, not repeatability or broad improvement evidence. Independent checks separate from visible development; protocol flags need review.'}
    atomic(root/'CLOSED-REPORT.json',summary)
    text=['# Isolated tensor workspace: closed pilot','',f"Status: **{summary['status']}**. Frozen plan `{summary['manifest_sha256']}`.",'',
        '| Editor | Tensors changed | Confirmation correct / 4 | Heldout correct / 4 | Untested / 8 | Submitted |',
        '| --- | ---: | ---: | ---: | ---: | --- |']
    for arm,row in arms.items():text.append(f"| {arm} | {row['changed_tensors']} | {row['confirmation_correct']} | {row['heldout_correct']} | {len(row['untested_ids'])} | {row['submitted']} |")
    text.extend(['',f"Original target: {summary['baseline_independent_correct']}/{summary['baseline_checked']} checked independent cases.",
        '',summary['interpretation'],'',f"Charged sampled tokens: {summary['charged_generated_tokens']}; complete token measurements: {summary['generation_measurements_complete']}. No efficiency winner is claimed without matched correct outcomes.",
        '',f"Owned native workers closed: {summary['all_owned_native_workers_closed']}. VM closure and code audit flags are in the private CLOSED-REPORT.json.",
        '',f"Error: {summary['error']}" if summary['error'] else 'No promotion, self-edit test, training, paid API use, commit or push was performed.'])
    (root/'FINDINGS.md').write_text('\n'.join(text)+'\n',encoding='utf8')
    return summary
