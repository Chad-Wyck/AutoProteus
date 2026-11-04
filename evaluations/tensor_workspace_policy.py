"""Host-owned numeric tensor broker. Never evaluates guest Python or paths."""
import base64
import hashlib
import json
import math
from pathlib import Path
import shutil
import uuid

from lora6k_state import atomic,identity,sha
from weight_editor_runtime import require,verify_unchanged_bytes
from weight_editor_sparse import bf16_round

MAX_ARRAY=64*1024**2
CHUNK=262144
PROTECTED={'token_embd.weight','output.weight','output_norm.weight'}


def catalog(path,layer_count):
    """Return plain metadata, releasing every GGUF mapping before serving code."""
    import numpy as np
    from gguf import GGUFReader
    reader=GGUFReader(path);result={}
    for t in reader.tensors:
        if t.name.startswith('blk.') and int(t.name.split('.')[1])>=layer_count:continue
        if t.data.dtype!=np.float32:continue
        result[t.name]={'shape':list(map(int,t.data.shape)),'offset':int(t.data_offset),'bytes':int(t.data.nbytes),
            'editable':t.name not in PROTECTED}
    return result


def selection(value,dimension):
    if value is None:return range(dimension)
    if isinstance(value,dict) and set(value)=={'slice'}:
        s=value['slice'];require(isinstance(s,list) and len(s)==3 and all(x is None or type(x) is int for x in s),'Invalid slice')
        require(s[2]!=0,'Zero slice step');return range(*slice(*s).indices(dimension))
    require(isinstance(value,list) and len(value)<=16384 and all(type(x) is int for x in value),'Invalid index list')
    require(all(-dimension<=x<dimension for x in value),'Index outside tensor')
    return [x%dimension for x in value]


def uniform_scaling_only(original,candidate):
    import numpy as np
    x=np.asarray(original,dtype=np.float64).reshape(-1);y=np.asarray(candidate,dtype=np.float64).reshape(-1)
    change=float(np.linalg.norm(y-x));xx=float(x@x)
    if not change:return False
    if not xx:return False
    scale=float((x@y)/xx)
    if abs(scale-1)<=1e-7:return False
    predicted=bf16_round(np.asarray(original,dtype=np.float32)*np.float32(scale)).astype(np.float64).reshape(-1)
    return float(np.linalg.norm(y-predicted))/change<.02


class TensorPolicy:
    def __init__(self,base,records,directory,metadata,*,forward=None,max_transfer=2*1024**3,max_patch_bytes=512*1024**2):
        self.base=dict(base);self.records=records;self.directory=Path(directory).resolve();self.directory.mkdir(parents=True,exist_ok=False)
        self.metadata=dict(metadata);self.forward=forward;self.max_transfer=max_transfer;self.max_patch_bytes=max_patch_bytes
        require(sha(base['path'])==base['sha256'],'Immutable target changed')
        self.edits={};self.upload=None;self.download=None;self.observations={};self.transferred=0;self.patch_bytes=0;self.frames=0;self.submitted=False
        self.snapshot_cache={}
        self.revision=0;self.tested_revision=None;self.inspected_revision=None

    def candidate_state(self):
        return {'candidate_id':identity([{k:e[k] for k in ('name','sha256')} for e in sorted(self.edits.values(),key=lambda e:e['name'])]),
            'revision':self.revision,'changed_tensor_count':len(self.edits),
            'generated_test_revision':self.tested_revision,'inspected_revision':self.inspected_revision,
            'current_revision_generated_tested':self.tested_revision==self.revision,
            'original_baseline_includes_edits':False}

    def event(self,kind,data):
        with (self.directory/'events.jsonl').open('a',encoding='utf-8') as out:out.write(json.dumps({'kind':kind,**data},ensure_ascii=True,allow_nan=False)+'\n')

    def status(self):
        return {'submitted':self.submitted,'changed_tensors':[{k:v for k,v in e.items() if k!='path'} for e in self.edits.values()],
            'transferred_bytes':self.transferred,'patch_bytes':self.patch_bytes,'patch_byte_limit':self.max_patch_bytes,
            'candidate':self.candidate_state()}

    def _record(self,name,*,editable=False):
        require(isinstance(name,str) and name in self.records,'Unknown tensor name')
        record=self.records[name]
        require(not editable or record['editable'],'Embedding, output head and final norm edits are forbidden')
        return record

    def _charge(self,n):
        require(type(n) is int and n>=0 and self.transferred+n<=self.max_transfer,'Tensor transfer allowance exhausted')
        self.transferred+=n

    def prepare_value(self,name,raw):
        """Historical policy; opt-in experiments may override conversion only."""
        return bf16_round(raw)

    def array(self,name,*,edited=True,rows=None,cols=None):
        import numpy as np
        rec=self._record(name);shape=rec['shape'];entry=self.edits.get(name) if edited else None
        path=entry['path'] if entry else self.base['path'];offset=0 if entry else rec['offset']
        if len(shape)>2:
            require(rows is None and cols is None and rec['bytes']<=MAX_ARRAY,'Use whole reads for small higher-rank tensors')
            with open(path,'rb') as f:f.seek(offset);data=f.read(rec['bytes'])
            require(len(data)==rec['bytes'],'Truncated tensor source');return np.frombuffer(data,dtype='<f4').copy().reshape(shape)
        r=list(selection(rows,shape[0]));c=list(selection(cols,shape[1])) if len(shape)==2 else None
        require(len(r)<=16384 and (len(r)*(len(c) if c is not None else 1)*4)<=MAX_ARRAY,'Read tensor in smaller row windows')
        require(c is not None or cols is None,'Vector has no column axis')
        result=np.empty((len(r),len(c)) if c is not None else (len(r),),dtype='<f4')
        with open(path,'rb') as f:
            for i,row in enumerate(r):
                width=shape[1] if c is not None else 1
                f.seek(offset+row*width*4);raw=f.read(width*4);require(len(raw)==width*4,'Truncated tensor source')
                values=np.frombuffer(raw,dtype='<f4');result[i]=values[c] if c is not None else values[0]
        return result

    def _download(self,raw,shape=None):
        require(self.download is None,'Close the current read before opening another')
        require(len(raw)<=MAX_ARRAY,'Observation exceeds bounded transfer size');self._charge(len(raw))
        token=uuid.uuid4().hex;self.download={'handle':token,'data':raw,'next':0}
        return {'handle':token,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),**({'shape':shape} if shape is not None else {})}

    def observation(self,path):
        path=Path(path);require(path.is_file() and path.stat().st_size<=MAX_ARRAY,'Invalid controlled observation')
        token=uuid.uuid4().hex;self.observations[token]=path;return token

    def handle(self,r):
        require(isinstance(r,dict) and isinstance(r.get('op'),str),'Invalid tensor request');self.frames+=1
        require(self.frames<=20000,'Workspace request limit');op=r['op']
        fields={'list':{'op'},'metadata':{'op'},'status':{'op'},'read_start':{'op','name','rows','cols','edited'},
            'read_chunk':{'op','handle','offset'},'read_close':{'op','handle'},'write_start':{'op','name','shape','bytes'},
            'write_chunk':{'op','handle','offset','data'},'write_finish':{'op','handle','sha256'},'undo':{'op','name'},'submit':{'op'},
            'forward':{'op','ids','view','mode','texts'},'observation_start':{'op','handle'},
            'observation_chunk':{'op','handle','offset'},'observation_close':{'op','handle'}}
        require(op in fields and set(r)==fields[op],'Unknown operation or fields')
        if op=='list':return [{'name':n,'shape':x['shape'],'dtype':'float32','editable':x['editable']} for n,x in self.records.items()]
        if op=='metadata':return self.metadata
        if op=='status':return self.status()
        if op=='forward':
            require(self.forward is not None,'Forward tool is unavailable');return self.forward(r)
        if op=='submit':self.submitted=True;self.event('submitted',self.status());return self.status()
        if op=='undo':
            require(not self.submitted,'Candidate is frozen');self._record(r['name'],editable=True)
            if self.edits.pop(r['name'],None) is not None:self.revision+=1
            self.event('undo',{'name':r['name']});return self.status()
        if op=='read_start':
            require(type(r['edited']) is bool,'Invalid view');a=self.array(r['name'],edited=r['edited'],rows=r['rows'],cols=r['cols'])
            return self._download(a.tobytes(),list(a.shape))
        if op=='observation_start':
            require(r['handle'] in self.observations,'Unknown observation handle');return self._download(self.observations[r['handle']].read_bytes())
        if op in ('read_chunk','observation_chunk'):
            d=self.download;require(d is not None and r['handle']==d['handle'] and type(r['offset']) is int and r['offset']==d['next'],'Invalid read sequence')
            data=d['data'][d['next']:d['next']+CHUNK];d['next']+=len(data);return {'data':base64.b64encode(data).decode('ascii')}
        if op in ('read_close','observation_close'):
            require(self.download is not None and r['handle']==self.download['handle'],'Invalid read handle');self.download=None;return {'closed':True}
        require(not self.submitted,'Candidate is frozen')
        if op=='write_start':
            rec=self._record(r['name'],editable=True)
            require(self.upload is None and r['shape']==rec['shape'] and type(r['bytes']) is int and r['bytes']==rec['bytes']<=MAX_ARRAY,'Tensor shape/size mismatch or unfinished upload')
            require(self.patch_bytes+r['bytes']<=self.max_patch_bytes,'Patch storage allowance exhausted');self.patch_bytes+=r['bytes']
            token=uuid.uuid4().hex;path=self.directory/(token+'.f32');path.touch(exist_ok=False)
            self.upload={'handle':token,'path':path,'name':r['name'],'bytes':r['bytes'],'next':0,'digest':hashlib.sha256()}
            return {'handle':token}
        u=self.upload;require(u is not None and r['handle']==u['handle'],'Invalid upload handle')
        if op=='write_chunk':
            require(type(r['offset']) is int and r['offset']==u['next'] and isinstance(r['data'],str) and len(r['data'])<=4*((CHUNK+2)//3),'Invalid write chunk')
            data=base64.b64decode(r['data'],validate=True);require(0<len(data)<=CHUNK and u['next']+len(data)<=u['bytes'],'Write outside tensor')
            self._charge(len(data))
            with u['path'].open('ab') as f:f.write(data)
            u['digest'].update(data);u['next']+=len(data);return {'written':len(data)}
        require(op=='write_finish' and u['next']==u['bytes'] and r['sha256']==u['digest'].hexdigest(),'Incomplete/mismatched tensor upload')
        import numpy as np
        name=u['name'];path=u['path'];rec=self.records[name]
        try:
            raw=np.fromfile(path,dtype='<f4').reshape(rec['shape']);require(np.isfinite(raw).all(),'Nonfinite tensor rejected')
            value=self.prepare_value(name,raw);require(np.isfinite(value).all(),'BF16 overflow rejected');original=self.array(name,edited=False)
            changed=int(np.count_nonzero(value.view(np.uint32)!=original.view(np.uint32)))
            require(changed>0,'No effective BF16 change');require(not uniform_scaling_only(original,value),'Whole-tensor uniform scaling is forbidden by this experiment')
            value.tofile(path);entry={'name':name,'path':str(path),'shape':rec['shape'],'sha256':sha(path),'changed_entries':changed,
                'relative_delta_norm':float(np.linalg.norm((value-original).astype(np.float64))/max(np.linalg.norm(original.astype(np.float64)),1e-30))}
            self.edits[name]=entry;self.revision+=1;self.event('save_edit',{k:v for k,v in entry.items() if k!='path'});atomic(self.directory/'edits.json',self.edits)
            return {k:v for k,v in entry.items() if k!='path'}|{'candidate':self.candidate_state(),
                'next_step':'test_candidate([development_id]) generates with these saved edits. compare_with_original([development_id]) evaluates both. The original baseline never includes saved edits.'}
        finally:self.upload=None

    def snapshot(self,folder,deadline):
        if not self.edits:return dict(self.base)
        key=identity([{k:e[k] for k in ('name','sha256')} for e in sorted(self.edits.values(),key=lambda e:e['name'])])
        if key in self.snapshot_cache:return self.snapshot_cache[key]
        require(sha(self.base['path'])==self.base['sha256'],'Original target changed');folder=Path(folder);require(not folder.exists(),'Never overwrite a candidate')
        require(shutil.disk_usage(folder.parent).free>=20*1024**3,'Artifact disk floor');folder.mkdir();out=folder/'model-f32.gguf';shutil.copyfile(self.base['path'],out)
        regions=[]
        with out.open('r+b') as target:
            for name,e in self.edits.items():
                deadline.remaining();require(sha(e['path'])==e['sha256'],'Committed tensor changed');record=self.records[name]
                target.seek(record['offset'])
                with open(e['path'],'rb') as source:shutil.copyfileobj(source,target,1024*1024)
                regions.append((record['offset'],record['bytes']))
        check=verify_unchanged_bytes(self.base['path'],out,regions,deadline)
        result={'path':str(out),'sha256':sha(out)};atomic(folder/'MANIFEST.json',{'model':result,'base_sha256':self.base['sha256'],'edits':self.edits,
            'byte_comparison':check,'authorship':'Local4B-generated Python executed in isolated VM; host applies only validated numeric arrays','snapshot_identity':key})
        self.snapshot_cache[key]=result;return result
