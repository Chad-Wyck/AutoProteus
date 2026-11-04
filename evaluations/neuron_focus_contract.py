"""CPU-testable contracts for a prepared, single-channel teacher study.

Importing this module never loads a model or mutates a weight artifact.
"""
import copy,hashlib,json,re
from pathlib import Path
import numpy as np
from lora6k_state import read,sha
from weight_editor_runtime import require

PROBE_LIMIT=32
OUTPUT_LIMIT=8192
SCHEDULED_TOKENS=18*OUTPUT_LIMIT
INTERRUPTION_RESERVE=8192
TOKEN_LIMIT=SCHEDULED_TOKENS+INTERRUPTION_RESERVE
LAYER=26
STRENGTH=.5
NORM_LIMIT=.015
MATCH_TOLERANCE=.05
PREFIX_CUTS=(1024,3072)
PHASE_COUNTS={'baseline':12,'channels':8,'coordinate_control':4,'static_candidate':4,'static_control':4}


def require_execution(root):
    root=Path(root);plan=read(root/'manifest.json');binding=(root/'manifest.sha256').read_text().strip()
    for name in ('LIVE-AUTHORIZATION.json','LIVE-REVIEW.json'):
        path=root/name
        require(path.exists(),'Preparation only: explicit execution authorization and independent review are absent')
        value=read(path);require(value.get('approved') is True and value.get('plan_identity')==binding,
            'Execution approval must bind this exact frozen plan: '+name)
        require(value.get('scope')=='full_frozen_study','Preparation or partial approval cannot launch the full study: '+name)
    require(Path(plan['publication']).resolve()==root.resolve(),'Execution cannot move/copy this publication to reset its single-use ledger')
    require(plan['authority']['preparation_only'],'Unexpected protocol authority contract')


def prefix_record(case,response,cut,tokenizer):
    require(response['finish_reason']=='length' and len(response['tokens'])==8192,'Only the declared untouched unfinished traces')
    require('</think>' not in response['raw_text'],'Source trace already closed thinking')
    require(type(cut) is int and cut in PREFIX_CUTS and cut<len(response['tokens']),'Unapproved source boundary')
    original=list(case['input_ids']);ids=original+response['tokens'][:cut]
    require(len(ids)<=4096,'Full original prompt plus declared prefix exceeds4096; no silent truncation')
    text=case['rendered_prompt']+tokenizer.decode(response['tokens'][:cut],skip_special_tokens=False)
    encoded=tokenizer.encode(text,add_special_tokens=False).ids
    return {'id':case['id']+'-at-'+str(cut),'source_case_id':case['id'],'source_output_tokens':8192,
        'original_rendered_prompt':case['rendered_prompt'],'original_input_ids':original,'observed_generated_prefix_ids':response['tokens'][:cut],
        'input_ids':ids,'rendered_prompt':text,'original_prompt_tokens':len(original),'observed_prefix_tokens':cut,
        'prefix_tokens':len(ids),'decoded_prefix_roundtrips':encoded==ids,'authoritative_representation':'Exact saved token IDs; complete original prompt retained',
        'scope':'Controlled early prefix of a full8192-token unfinished trace, not its full tail or identical historical KV bit pattern'}


def validate_proposal(proposal):
    require(type(proposal) is dict and set(proposal)=={'layer','columns','scale'},'Only the outgoing-channel family')
    require(type(proposal['layer']) is int and proposal['layer']==LAYER,'Layer26 fixed prospectively')
    columns=proposal['columns'];require(type(columns) is list and len(columns)==1 and type(columns[0]) is int and 0<=columns[0]<9216,'Exactly one channel')
    require(type(proposal['scale']) in (int,float) and proposal['scale']==STRENGTH,'Half-strength fixed prospectively')
    return copy.deepcopy(proposal)


def validate_probe_request(plan,request,consumed):
    phase=request['phase'];require(phase in PHASE_COUNTS and len(request['conditions'])==PHASE_COUNTS[phase],'Frozen phase count')
    require(type(consumed) is int and 0<=consumed<=PROBE_LIMIT and consumed+len(request['conditions'])<=PROBE_LIMIT,'Probe budget exceeded')
    prefixes={p['id']:p for p in read(Path(plan['publication'])/'prefixes.json')['prefixes']}
    for c in request['conditions']:
        require(type(c.get('id')) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,160}',c['id']),'Unsafe probe artifact ID')
        require(c['prefix_id'] in prefixes,'Unknown frozen prefix')
        mode=c['mode'];require(mode in ('no_hook','capture','noop','channel'),'Unsupported hook mode')
        require((phase=='baseline' and mode in ('no_hook','capture','noop')) or (phase in ('channels','coordinate_control') and mode=='channel')
            or (phase.startswith('static_') and mode=='capture'),'Mode/phase mismatch')
        if mode=='channel':require(type(c.get('channel')) is int and 0<=c['channel']<9216,'Invalid unit')
    expected=[]
    for mode in ('no_hook','capture','noop') if phase=='baseline' else ('capture',) if phase.startswith('static_') else ():
        expected.extend((mode,i) for i in prefixes)
    if expected:require(sorted((c['mode'],c['prefix_id']) for c in request['conditions'])==sorted(expected),'Phase must cover all four prefixes exactly')
    if phase in ('channels','coordinate_control'):
        root=Path(plan['publication'])
        units=read(root/'SHORTLIST.json')['channels'] if phase=='channels' else [read(root/'SELECTION.json')['control_channel']]
        require(len(units)==(2 if phase=='channels' else 1) and len(set(units))==len(units),'Shortlist/control cardinality')
        require(sorted((c['channel'],c['prefix_id']) for c in request['conditions'])==sorted((j,i) for j in units for i in prefixes),'Unapproved channel coverage')


def parity_check(reference,observed):
    a,b=np.asarray(reference,dtype=np.float64),np.asarray(observed,dtype=np.float64)
    require(a.shape==b.shape and a.ndim==1 and a.size and np.isfinite(a).all() and np.isfinite(b).all(),'Invalid parity vectors')
    max_error=float(np.max(np.abs(a-b)));relative=float(np.linalg.norm(a-b)/max(1e-12,np.linalg.norm(a)))
    return {'passed':max_error<=1e-4 and relative<=1e-5,'max_abs_error':max_error,'relative_l2_error':relative,
        'max_abs_tolerance':1e-4,'relative_l2_tolerance':1e-5}


def channel_delta_check(base_h,base_out,changed_out,down_column):
    h=float(base_h);base=np.asarray(base_out,dtype=np.float64);changed=np.asarray(changed_out,dtype=np.float64);column=np.asarray(down_column,dtype=np.float64)
    require(base.shape==changed.shape==column.shape and base.ndim==1 and np.isfinite(h) and all(np.isfinite(x).all() for x in (base,changed,column)),'Invalid channel tensors')
    expected=(STRENGTH-1)*h*column;actual=changed-base;error=actual-expected
    tolerance=1e-4+1e-3*max(float(np.max(np.abs(base))),float(np.max(np.abs(expected))))
    return {'passed':float(np.max(np.abs(error)))<=tolerance,'max_abs_error':float(np.max(np.abs(error))),
        'max_abs_tolerance':tolerance,'expected_delta_l2':float(np.linalg.norm(expected)),'observed_delta_l2':float(np.linalg.norm(actual)),
        'scope':'Conditional final-token FFN output, not all-token static edit equivalence'}


def choose_channel(rows):
    require(len(rows)==8,'Two units times four prefixes required')
    groups={c:[r for r in rows if r['channel']==c] for c in {r['channel'] for r in rows}}
    require(len(groups)==2 and all(len(v)==4 and len({r['prefix_id'] for r in v})==4 for v in groups.values()),'Wrong shortlist coverage')
    for r in rows:
        require(all(type(r.get(k)) in (int,float) and np.isfinite(r[k]) for k in ('contrast_margin','reference_contrast_margin','contrast_margin_delta')),
            'Nonfinite or missing surrogate margin/delta')
    with np.errstate(over='ignore',invalid='ignore'):
        means={c:float(np.mean([r['contrast_margin_delta'] for r in v],dtype=np.float64)) for c,v in groups.items()}
    require(all(np.isfinite(v) for v in means.values()),'Nonfinite surrogate mean')
    eligible={c:means[c] for c,v in groups.items()
        if all(r['delta_validation']['passed'] and r['contrast_margin_delta']>=0 for r in v) and means[c]>=.001}
    if not eligible:return {'supported':False,'reason':'No consistent conditional surrogate effect; no replacement channels/doses'}
    winner=min(eligible,key=lambda c:(-eligible[c],c))
    return {'supported':True,'channel':winner,'mean_contrast_margin_delta':eligible[winner],
        'scope':'Development-only conditional effect; generated correctness remains unmeasured'}


def match_control(target_norm,candidates,excluded):
    require(np.isfinite(target_norm) and target_norm>0,'Nonzero deployed target delta required')
    available=[r for r in candidates if r['channel'] not in excluded and np.isfinite(r['deployed_delta_l2']) and r['deployed_delta_l2']>0]
    require(len(candidates)<=8,'Control pool bounded to eight norm-only candidates')
    if not available:return {'matched':False,'reason':'No control in frozen norm-only pool'}
    best=min(available,key=lambda r:(abs(r['deployed_delta_l2']/target_norm-1),r['channel']))
    error=abs(best['deployed_delta_l2']/target_norm-1)
    return {'matched':error<=MATCH_TOLERANCE,'channel':best['channel'],'relative_norm_error':error,'tolerance':MATCH_TOLERANCE,
        'selection':'Deployed weight-delta norm only; never response quality','promotable':False}


def token_partition(response,closing_id):
    tokens=response['tokens'];positions=[i for i,t in enumerate(tokens) if t==closing_id]
    before=positions[0] if positions else len(tokens)
    return {'reasoning_tokens':before,'after_thinking_tokens':len(tokens)-before-1 if positions else 0,
        'closing_tokens':1 if positions else 0,'total_tokens':len(tokens),'thinking_closed':bool(positions)}


def weight_delta_statistics(original,changed,before,after,channel):
    x,y,a,b=[np.asarray(v,dtype=np.float64) for v in (original,changed,before,after)]
    require(x.shape==y.shape==a.shape==b.shape and x.ndim==2 and all(np.isfinite(v).all() for v in (x,y,a,b)),'Invalid weight statistics arrays')
    require(type(channel) is int and 0<=channel<x.shape[1],'Invalid statistics channel')
    mask=np.zeros(x.shape[1],dtype=bool);mask[channel]=True
    require(np.array_equal(x[:,~mask],y[:,~mask]),'Canonical edit escaped one selected column')
    nx=float(np.linalg.norm(x));na=float(np.linalg.norm(a));require(nx>0 and na>0,'Zero reference norm')
    delta=b-a
    return {'channel':channel,'deployed_delta_l2':float(np.linalg.norm(delta)),'deployed_relative_l2':float(np.linalg.norm(delta)/na),
        'canonical_relative_l2':float(np.linalg.norm(y-x)/nx),'canonical_changed_entries':int(np.count_nonzero(y-x)),
        'selected_changed_values':int(np.count_nonzero(delta[:,mask])),'neighbor_changed_values':int(np.count_nonzero(delta[:,~mask])),
        'neighbor_delta_l2':float(np.linalg.norm(delta[:,~mask]))}


def behavior_comparison(original,candidate):
    b={r['id']:r for r in original};e={r['id']:r for r in candidate};require(set(b)==set(e) and b,'Matched behavior cases required')
    gains=[i for i in b if not b[i]['correct'] and e[i]['correct']];losses=[i for i in b if b[i]['correct'] and not e[i]['correct']]
    return {'gains':gains,'losses':losses,'original_correct':sum(r['correct'] for r in b.values()),'candidate_correct':sum(r['correct'] for r in e.values()),
        'useful_completion_support':bool(gains and not losses),'matched_correct_ids':[i for i in b if b[i]['correct'] and e[i]['correct']],
        'ceiling':all(r['correct'] for r in b.values()),'shorter_incorrect_output_is_not_success':True}


def final_attribution(original,candidate,control):
    targeted=behavior_comparison(original,candidate);coordinate_control=behavior_comparison(original,control)
    return {'candidate_vs_untouched':targeted,'control_vs_untouched':coordinate_control,
        'candidate_vs_control':behavior_comparison(control,candidate),
        'both_edited_artifacts_improved':bool(targeted['useful_completion_support'] and coordinate_control['useful_completion_support']),
        'coordinate_specificity_claimed':False,
        'scope':'Descriptive matched outcomes only; improvements in both artifacts do not establish targeted-channel specificity or semantic neuron identity'}
