"""Serial GPU model trials using AutoProteus's protected VM controller.

Run with the project's portable Python after preparing weights. No candidate module
is imported on the host. Private journals and snapshots stay under .data/.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from controller.config import DEFAULTS
from controller.evaluation import candidate_source, freeze_source, run_regressions, run_task, source_changes, source_identity
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.providers import ModelClient, request_json
from controller.runtime import LocalRuntime
from controller.storage import Store, atomic_json, now

DATA=ROOT/'.data/local-model-tests'
PROBE=(ROOT/'evaluations/local-feature-probe.py').read_text(encoding='utf-8')
TASKS=json.loads((ROOT/'evaluations/local-upgrade-tasks.json').read_text(encoding='utf-8'))
ORDINARY=json.loads((ROOT/'evaluations/tasks.json').read_text(encoding='utf-8'))

class ScriptedClient:
    def __init__(self,actions):self.actions,self.index=actions,0
    def complete(self,messages,cancel):
        result=self.actions[min(self.index,len(self.actions)-1)]
        self.index+=1
        return {'content':json.dumps(result,ensure_ascii=False),'usage':{}}

def read_artifact(store,session,name):
    try:return json.loads(Artifacts(store,session).read(name))
    except Exception as error:return {'error':str(error)[:1000]}

def enrich(store,result):
    session=store.get(result['session'])
    result['notices']=[f.get('text','') for f in session['feed'] if f.get('kind')=='notice'][-4:]
    events=[json.loads(line) for line in (store.directory(session['id'])/'events.jsonl').read_text(encoding='utf-8').splitlines()]
    responses=[e['data'] for e in events if e['type']=='model_response']
    result['generated_tokens']=sum((r.get('usage') or {}).get('eval_count',0) or 0 for r in responses)
    result['prompt_tokens']=sum((r.get('usage') or {}).get('prompt_eval_count',0) or 0 for r in responses)
    result['thinking_characters']=sum(len(r.get('thinking','')) for r in responses)
    result['actions']=[e['data']['action']['tool'] for e in events if e['type']=='action_result' and isinstance(e.get('data'),dict) and isinstance(e['data'].get('action'),dict)]
    return result

def verify_feature(store,source,feature):
    settings=SimpleNamespace(values={**DEFAULTS,'configured':True,'provider':'demo','model':'independent feature verifier','protocol':'json','terminal':True,'max_steps':5},key=lambda:'')
    actions=[{'message':'Run independent guest checks','action':{'tool':'run_command','arguments':{'command':'python3 benchmark_probe.py '+feature}}},{'message':'Checks recorded','status':'completed'}]
    agent=IsolatedAgent(ROOT,store,settings,lambda _:ScriptedClient(actions))
    try:
        result=run_task(agent,store,settings.values,{'name':'verify-'+feature,'task':'Execute the fixed independent checks.','fixtures':{'benchmark_probe.py':PROBE},'checks':[{'path':'benchmark-probe.json'}]},source,120)
        probe=read_artifact(store,store.get(result['session']),'benchmark-probe.json')
        checks=probe.get('checks',{})
        functional_names=['counts_sample.txt','counts_empty.txt','counts_no-newline.txt','counts_large.txt'] if feature=='file_summary' else ['append_sample.txt','append_empty.txt','append_new/deep.txt','append_sample.txt_empty','append_large.txt_empty','limit_exact']
        functional=all(checks.get(name) is True for name in functional_names) and checks.get('registered') is True and checks.get('schema') is True
        # Unknown-tool exceptions cannot earn edge-case credit for an absent feature.
        passed=functional and bool(checks) and all(v is True for v in checks.values()) and probe.get('suite',{}).get('exit_code')==0 and result['passed']
        return {'passed':passed,'functional':functional,'checks_passed':sum(v is True for v in checks.values()) if functional else 0,'checks_total':len(checks),'run':result,'probe':probe}
    finally:agent.close()

def verify_public(store,source,feature):
    settings=SimpleNamespace(values={**DEFAULTS,'configured':True,'provider':'demo','model':'independent public-tool verifier','protocol':'json','terminal':False,'max_steps':4},key=lambda:'')
    content='café\r\n猫 and dog\n'
    arguments={'path':'sample.txt'} if feature=='file_summary' else {'path':'sample.txt','content':'élan\r\n'}
    actions=[{'message':'Invoke the requested public tool','action':{'tool':feature,'arguments':arguments}},{'message':'Read resulting bytes','action':{'tool':'read_file','arguments':{'path':'sample.txt'}}},{'message':'Public check finished','status':'completed'}]
    agent=IsolatedAgent(ROOT,store,settings,lambda _:ScriptedClient(actions))
    try:
        expected=content if feature=='file_summary' else content+'élan\r\n'
        result=run_task(agent,store,settings.values,{'name':'public-'+feature,'task':'Invoke the new public tool through the unchanged seed loop.','fixtures':{'sample.txt':content},'checks':[{'path':'sample.txt','equals':expected}]},source,90)
        events=[json.loads(line) for line in (store.directory(result['session'])/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        action_results=[e['data'] for e in events if e['type']=='action_result']
        feature_result=next((a for a in action_results if a.get('action',{}).get('tool')==feature),{})
        expected_result={'path':'sample.txt','bytes':len(content.encode()),'characters':len(content),'lines':len(content.splitlines()),'words':len(content.split())} if feature=='file_summary' else {'path':'sample.txt','bytes':len(expected.encode())}
        payload=feature_result.get('result',{})
        passed=result['passed'] and feature_result.get('ok') is True and isinstance(payload,dict) and all(payload.get(k)==v for k,v in expected_result.items())
        return {'passed':passed,'run':result,'feature_result':feature_result}
    finally:agent.close()

def assess(store,starter,result,feature,directory):
    session=store.get(result['session'])
    try:source=candidate_source(store,session)
    except Exception as error:return {'accepted':False,'reason':'No complete exported candidate: '+str(error)}
    atomic_json(directory/'candidate-source.json',source)
    changes=source_changes(starter,source)
    atomic_json(directory/'changes.json',changes)
    original={item['path']:base64.b64decode(item['data']) for item in starter}
    candidate={item['path']:base64.b64decode(item['data']) for item in source}
    changed={item['path'] for item in changes}
    additions=changed-original.keys()
    runtime_changed=bool(changed & {'autoproteus/tools.py','autoproteus/providers.py'})
    new_tests=[name for name in additions if name.startswith('tests/test_') and name.endswith('.py') and b'def test_' in candidate[name]]
    protected_unchanged=all(candidate.get(name)==content for name,content in original.items() if name not in {'autoproteus/tools.py','autoproteus/providers.py','README.md'})
    allowed=all(name in {'autoproteus/tools.py','autoproteus/providers.py','README.md'} or
                (name in additions and name.startswith('tests/') and name.endswith('.py')) for name in changed)
    review={'source_sha256':source_identity(source),'changed_files':sorted(changed),'new_test_files':new_tests,'protected_unchanged':protected_unchanged,'allowed_files_only':allowed,'documentation_updated':'README.md' in changed,'runtime_changed':runtime_changed,'completed':result['status']=='completed' and not result['timed_out'],'feature_report':any(c.get('path')=='feature.md' and c.get('passed') for c in result['checks'])}
    frozen=freeze_source(store,source,'Candidate '+feature)
    # Runtime edits get checked even when the author prematurely stops or claims failure.
    if runtime_changed:
        review['regressions']=run_regressions(ROOT,store,frozen)
        if protected_unchanged:
            review['feature']=verify_feature(store,frozen,feature)
            review['public']=verify_public(store,frozen,feature)
        else:review['feature']={'passed':False,'reason':'Requested unchanged execution loop or existing tests were modified'}
    else:
        review['feature']={'passed':False,'reason':'No runtime source edit'}
    review['accepted']=all([review['completed'],review['feature_report'],review['runtime_changed'],review['documentation_updated'],bool(new_tests),protected_unchanged,allowed,review.get('regressions',{}).get('passed'),review.get('feature',{}).get('passed'),review.get('public',{}).get('passed')])
    atomic_json(directory/'review.json',review)
    return review

def self_check(data_dir=None):
    global DATA
    if data_dir:
        DATA=(ROOT/data_dir).resolve()
        if not DATA.is_relative_to((ROOT/'.data').resolve()):
            raise ValueError('Benchmark data must stay inside the project .data directory')
    data=DATA/'grader-self-check'
    store=Store(data/'sessions')
    source=seed_files(ROOT)
    starter=freeze_source(store,source,'Starter for grader calibration')
    results={'negative':{}}
    for feature in ('file_summary','append_text'):
        results['negative'][feature]=verify_feature(store,starter,feature)
        assert not results['negative'][feature]['passed'] and not results['negative'][feature]['functional']
    reference='''        if tool == "file_summary":
            path = self.path(args["path"])
            with path.open("r", encoding="utf-8", newline="") as stream:
                text = stream.read(WRITE_LIMIT + 1)
            if len(text) > WRITE_LIMIT: raise ValueError("Too large")
            return {"path":str(path.relative_to(self.root)), "bytes":len(text.encode("utf-8")), "characters":len(text), "lines":len(text.splitlines()), "words":len(text.split())}
        if tool == "append_text":
            path = self.path(args["path"])
            content = args["content"]
            if not isinstance(content, str): raise ValueError("Content must be text")
            text = ""
            if path.exists():
                with path.open("r", encoding="utf-8", newline="") as stream: text = stream.read(WRITE_LIMIT + 1)
            if len(text) + len(content) > WRITE_LIMIT: raise ValueError("Too large")
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("ab") as stream: stream.write(content.encode("utf-8"))
            return {"path":str(path.relative_to(self.root)), "bytes":len((text + content).encode("utf-8"))}
'''
    for item in source:
        if item['path']=='autoproteus/tools.py':
            text=base64.b64decode(item['data']).decode('utf-8')
            text=text.replace('        if tool == "list_files":',reference+'        if tool == "list_files":')
            item['data']=base64.b64encode(text.encode()).decode()
        if item['path']=='autoproteus/providers.py':
            text=base64.b64decode(item['data']).decode('utf-8').replace('TOOL_SPECS = {','TOOL_SPECS = {\n    "file_summary": ("Count text.", {"path": STRING}, ["path"]),\n    "append_text": ("Append text.", {"path": STRING, "content": STRING}, ["path", "content"]),')
            item['data']=base64.b64encode(text.encode()).decode()
    reference_seed=freeze_source(store,source,'Human-written grader calibration ONLY')
    results['positive']={}
    for feature in ('file_summary','append_text'):
        results['positive'][feature]=verify_feature(store,reference_seed,feature)
        assert results['positive'][feature]['passed'],results['positive'][feature]
        results['positive'][feature]['public']=verify_public(store,reference_seed,feature)
        assert results['positive'][feature]['public']['passed']
    atomic_json(data/'results.json',results)
    print('GRADER CALIBRATED: absent tools rejected; reference tools and fresh-worker invocations passed',flush=True)

def gpu():
    try:
        raw=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used,temperature.gpu,utilization.gpu','--format=csv,noheader,nounits'],text=True,creationflags=subprocess.CREATE_NO_WINDOW)
        return raw.strip()
    except Exception as error:return str(error)[:200]

def run(args):
    global DATA
    if args.data_dir:
        DATA=(ROOT/args.data_dir).resolve()
        if not DATA.is_relative_to((ROOT/'.data').resolve()):
            raise ValueError('Benchmark data must stay inside the project .data directory')
        DATA.mkdir(parents=True,exist_ok=True)
    downloads=json.loads((DATA/'downloads.json').read_text(encoding='utf-8'))
    if args.pin_user or args.protocol or args.lf_source:
        name=('user-pinned' if args.pin_user else 'original')+('-lf' if args.lf_source else '')+('-'+args.protocol if args.protocol else '')
        DATA=DATA/'variants'/name
        DATA.mkdir(parents=True,exist_ok=True)
    selected=[m for m in downloads['models'] if m['status']=='verified']
    models=selected+[{'slug':'qwen3-4b-instruct','model':'qwen3:4b-instruct'}]
    if args.models:models=[m for m in models if m['slug'] in args.models]
    if not models:raise ValueError('No selected verified models')
    source=seed_files(ROOT)
    canonical_source_sha256=source_identity(source)
    if args.pin_user:
        for item in source:
            if item['path']=='autoproteus/agent.py':
                text=base64.b64decode(item['data']).decode('utf-8')
                old='        return [{"role": "system", "content": system}] + messages'
                new='''        if not any(item["role"] == "user" and item["content"] == session["task"] for item in messages):
            messages.insert(0, {"role": "user", "content": session["task"]})
'''+old
                if old not in text:raise ValueError('Could not prepare minimal user-turn compatibility diagnostic')
                item['data']=base64.b64encode(text.replace(old,new).encode()).decode()
    if args.lf_source:
        for item in source:
            if item['path'].endswith(('.py','.md')):
                item['data']=base64.b64encode(base64.b64decode(item['data']).replace(b'\r\n',b'\n')).decode()
    report_path=DATA/'results.json'
    report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else {'started':now(),'source_sha256':source_identity(source),'source_files':[{ 'path':i['path'],'sha256':hashlib.sha256(base64.b64decode(i['data'])).hexdigest()} for i in source],'downloads':downloads,'ordinary':[],'upgrades':[],'models':{},'method':{'execution':'vm','ordinary_timeout':180,'upgrade_timeout':args.timeout,'response_tokens':args.response_tokens,'context_tokens':args.context_tokens,'temperature':0.6,'sampling_seed':None,'repeats':1,'thinking':'enabled for supported models; none for non-reasoning models','max_steps':48,'inference':'host GPU; candidate commands and tests only in isolated VMs'}}
    if report['source_sha256']!=source_identity(source):raise ValueError('Starter changed since benchmark began')
    if (report['method']['context_tokens'],report['method']['response_tokens'])!=(args.context_tokens,args.response_tokens):
        raise ValueError('Use a separate data directory when changing context or response limits')
    report['canonical_source_sha256']=canonical_source_sha256
    report['variant']='user-turn-pinned' if args.pin_user else 'v0.5-unmodified'
    report['source_lf_normalized']=args.lf_source
    atomic_json(DATA/'starter-source.json',source)
    report['status']='running'
    report['pid']=__import__('os').getpid()
    host_files=list((ROOT/'controller').glob('*.py'))+list((ROOT/'web').glob('*'))+[ROOT/'guest/worker.py',ROOT/'app.py']
    report.setdefault('host_file_hashes',{p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in host_files if p.is_file()})
    atomic_json(report_path,report)
    settings=SimpleNamespace(values={**DEFAULTS,'base_url':'http://127.0.0.1:11435','configured':True},key=lambda:'')
    engine=LocalRuntime(ROOT,settings)
    store=Store(DATA/'sessions')
    agent=None
    monitoring=threading.Event()
    def monitor():
        with (DATA/'gpu-samples.jsonl').open('a',encoding='utf-8') as log:
            while not monitoring.is_set():
                log.write(json.dumps({'utc':now(),'gpu':gpu(),'active':report.get('active')})+'\n')
                log.flush()
                monitoring.wait(5)
    sampling=threading.Thread(target=monitor,daemon=True)
    sampling.start()
    try:
        base=engine.ensure_service(allow_download=False)
        settings.values['base_url']=base
        frozen=freeze_source(store,source,'Frozen v0.5 starter')
        if 'starter_regressions' not in report:
            report['starter_regressions']=run_regressions(ROOT,store,frozen)
            atomic_json(report_path,report)
        if not report['starter_regressions']['passed']:raise ValueError('Starter regressions failed')
        for model in models:
            slug=model['slug']
            if ((args.upgrades_only or len([r for r in report['ordinary'] if r['model']==slug])==len(ORDINARY)) and
                len([r for r in report['upgrades'] if r['model']==slug])==len(TASKS)):
                continue
            show=request_json(base+'/api/show',{'model':model['model']},timeout=40)
            capabilities=show.get('capabilities',[])
            protocol=args.protocol or ('native' if 'tools' in capabilities else 'json')
            thinking=True if 'thinking' in capabilities else None
            config={**DEFAULTS,'configured':True,'provider':'ollama','base_url':base,'model':model['model'],'context_tokens':args.context_tokens,'response_tokens':args.response_tokens,'temperature':0.6,'max_steps':48,'request_timeout':300,'command_timeout':60,'terminal':True,'protocol':protocol,'thinking':thinking}
            settings.values=config
            report['models'][slug]={'model':model['model'],'capabilities':capabilities,'details':show.get('details'),'config':{k:v for k,v in config.items() if k!='base_url'},'gpu_before':gpu()}
            tags=request_json(base+'/api/tags')['models']
            report['models'][slug]['tag']=next(t for t in tags if t['name'].lower()==model['model'].lower())
            print('MODEL',slug,protocol,'thinking',thinking,flush=True)
            try:
                warm=request_json(base+'/api/chat',{'model':model['model'],'messages':[{'role':'user','content':'Reply with exactly READY.'}],'stream':False,'think':False if 'thinking' in capabilities else None,'options':{'num_ctx':args.context_tokens,'num_predict':32,'temperature':0.6},'keep_alive':'30m'},timeout=300)
                report['models'][slug]['warmup']={k:warm.get(k) for k in ('done','done_reason','load_duration','eval_count','eval_duration','prompt_eval_count','prompt_eval_duration')}
                report['models'][slug]['placement']=request_json(base+'/api/ps')
                report['models'][slug]['gpu_loaded']=gpu()
            except Exception as error:
                report['models'][slug]['load_error']=str(error)[:1500]
                print('LOAD ERROR',slug,str(error)[:400],flush=True)
                atomic_json(report_path,report)
                continue
            atomic_json(report_path,report)
            agent=IsolatedAgent(ROOT,store,settings)
            for task in ([] if args.upgrades_only else ORDINARY):
                if any(r['model']==slug and r['task']==task['name'] for r in report['ordinary']):continue
                # Ordinary tasks use the same reasoning setting, with commands disabled.
                settings.values={**config,'terminal':False,'max_steps':32}
                report['active']={'kind':'ordinary','model':slug,'task':task['name'],'started':now()}
                print('ORDINARY',slug,task['name'],flush=True)
                result=enrich(store,run_task(agent,store,settings.values,task,frozen,180))
                result['model']=slug
                report['ordinary'].append(result)
                report.pop('active',None)
                atomic_json(report_path,report)
                print('RESULT',result['passed'],result['seconds'],result['status'],flush=True)
            for task in TASKS:
                if any(r['model']==slug and r['task']==task['name'] for r in report['upgrades']):continue
                settings.values=config
                print('UPGRADE',slug,task['name'],flush=True)
                directory=DATA/'trials'/(slug+'-'+task['name'])
                directory.mkdir(parents=True,exist_ok=True)
                report['active']={'kind':'upgrade','model':slug,'task':task['name'],'started':now()}
                atomic_json(report_path,report)
                result=enrich(store,run_task(agent,store,config,{**task,'checks':[{'path':'feature.md'}]},frozen,args.timeout))
                result['model']=slug
                result['review']=assess(store,source,result,task['name'],directory)
                report['upgrades'].append(result)
                report.pop('active',None)
                atomic_json(report_path,report)
                print('VERDICT',slug,task['name'],result['review']['accepted'],result['seconds'],result['status'],flush=True)
            agent.close();agent=None
            request_json(base+'/api/generate',{'model':model['model'],'keep_alive':0},timeout=40)
            report['models'][slug]['gpu_after']=gpu()
            atomic_json(report_path,report)
        report['status']='completed'
        report['finished']=now()
        report['source_unchanged']=source_identity(seed_files(ROOT))==canonical_source_sha256
        report['host_files_unchanged']=all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in report['host_file_hashes'].items())
        print('BENCHMARK COMPLETE',flush=True)
    except BaseException as error:
        report.update(status='interrupted',error=type(error).__name__+': '+str(error)[:1500])
        raise
    finally:
        if agent:agent.close()
        monitoring.set();sampling.join(timeout=10)
        engine.close()
        report['gpu_final']=gpu()
        atomic_json(report_path,report)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',help='Separate saved batch directory under .data; never overwrite earlier results')
    parser.add_argument('--self-check',action='store_true')
    parser.add_argument('--models',nargs='*')
    parser.add_argument('--timeout',type=int,default=900)
    parser.add_argument('--context-tokens',type=int,default=16384)
    parser.add_argument('--response-tokens',type=int,default=4096)
    parser.add_argument('--pin-user',action='store_true',help='Test a separate copied seed retaining the original user turn; does not edit starter')
    parser.add_argument('--upgrades-only',action='store_true')
    parser.add_argument('--protocol',choices=['native','json'],help='Separate protocol diagnostic; preserves original primary results')
    parser.add_argument('--lf-source',action='store_true',help='Normalize only the copied seed source to LF, leaving ordinary workspace bytes unchanged')
    args=parser.parse_args()
    if args.self_check:self_check(args.data_dir)
    else:run(args)
