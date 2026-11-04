"""Persistent, unprivileged Python kernel. Execute ONLY inside the research VM."""
import ast
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import sys
import traceback

PREFIX=b'AP1 '
MAX=4*1024*1024
channel=reader=None
cell=None
sequence=0


def send(value):
    raw=PREFIX+json.dumps(value,separators=(',',':'),ensure_ascii=True).encode()+b'\n'
    if len(raw)>MAX:raise ValueError('Kernel frame exceeds limit')
    view=memoryview(raw)
    while view:
        n=channel.write(view)
        if not n:raise RuntimeError('Controller closed')
        view=view[n:]


def receive():
    raw=reader.readline(MAX+1)
    if not raw.startswith(PREFIX) or len(raw)>MAX:raise RuntimeError('Invalid controller frame')
    return json.loads(raw[len(PREFIX):])


def rpc(op,**data):
    global sequence
    sequence+=1;identifier=sequence
    send({'op':'rpc','cell':cell,'id':identifier,'request':{'op':op,**data}})
    reply=receive()
    if reply.get('op')!='rpc_result' or reply.get('id')!=identifier or reply.get('cell')!=cell:raise RuntimeError('RPC response mismatch')
    if 'error' in reply:raise ValueError(reply['error'])
    return reply['value']


def encode_selection(value):
    if value is None:return None
    if isinstance(value,slice):return {'slice':[value.start,value.stop,value.step]}
    if isinstance(value,int):return [value]
    return [int(x) for x in value]


def load_tensor(name,rows=None,cols=None,*,edited=True):
    import numpy as np
    meta=rpc('read_start',name=name,rows=encode_selection(rows),cols=encode_selection(cols),edited=edited)
    chunks=[];digest=hashlib.sha256()
    for offset in range(0,meta['bytes'],262144):
        value=rpc('read_chunk',handle=meta['handle'],offset=offset)
        data=base64.b64decode(value['data'],validate=True);chunks.append(data);digest.update(data)
    rpc('read_close',handle=meta['handle'])
    if digest.hexdigest()!=meta['sha256']:raise ValueError('Tensor transfer checksum mismatch')
    return np.frombuffer(b''.join(chunks),dtype='<f4').copy().reshape(meta['shape'])


def save_edit(name,value):
    import numpy as np
    value=np.ascontiguousarray(value,dtype='<f4');raw=memoryview(value).cast('B')
    meta=rpc('write_start',name=name,shape=list(value.shape),bytes=len(raw));digest=hashlib.sha256()
    for offset in range(0,len(raw),262144):
        chunk=raw[offset:offset+262144];digest.update(chunk)
        rpc('write_chunk',handle=meta['handle'],offset=offset,data=base64.b64encode(chunk).decode('ascii'))
    return rpc('write_finish',handle=meta['handle'],sha256=digest.hexdigest())


def forward(ids=None,*,view='edited',mode='generate',texts=None):
    """Host-controlled inference; no model or GPU code runs in this kernel."""
    return rpc('forward',ids=ids,view=view,mode=mode,texts=texts)


def test_candidate(ids):
    """Generate with ALL currently saved edits; original baseline is unchanged."""
    return forward(ids,view='edited',mode='generate')


def compare_with_original(ids=None,*,texts=None):
    """Evaluate the current candidate and return the immutable original control."""
    return forward(ids,view='both',mode='probe' if texts is not None else 'generate',texts=texts)


def inspect_candidate(texts):
    """Read last-token logits/activations from the current edited candidate."""
    return forward(view='edited',mode='probe',texts=texts)


def execute_cell(code,namespace):
    """REPL-style final-expression display, executed ONLY inside the VM."""
    tree=ast.parse(code,filename='<workspace-cell>',mode='exec')
    expression=bool(tree.body and isinstance(tree.body[-1],ast.Expr))
    name='__workspace_last_expression_value__'
    if expression:
        original=tree.body[-1]
        tree.body[-1]=ast.copy_location(ast.Assign(targets=[ast.Name(id=name,ctx=ast.Store())],value=original.value),original)
        ast.fix_missing_locations(tree)
    exec(compile(tree,'<workspace-cell>','exec'),namespace,namespace)
    if expression:
        value=namespace.pop(name,None)
        if value is not None:print(repr(value))


def load_observation(handle):
    import numpy as np
    meta=rpc('observation_start',handle=handle);chunks=[];digest=hashlib.sha256()
    for offset in range(0,meta['bytes'],262144):
        row=rpc('observation_chunk',handle=meta['handle'],offset=offset);data=base64.b64decode(row['data'],validate=True)
        chunks.append(data);digest.update(data)
    rpc('observation_close',handle=meta['handle'])
    if digest.hexdigest()!=meta['sha256']:raise ValueError('Observation checksum mismatch')
    with np.load(io.BytesIO(b''.join(chunks)),allow_pickle=False) as value:return {k:value[k].copy() for k in value.files}


class Output(io.TextIOBase):
    def __init__(self):self.parts=[];self.size=0;self.truncated=False
    def write(self,text):
        text=str(text);available=max(0,12000-self.size)
        if available:self.parts.append(text[:available]);self.size+=min(len(text),available)
        if len(text)>available:self.truncated=True
        return len(text)
    def text(self):return ''.join(self.parts)+('\n[output truncated]' if self.truncated else '')


def main():
    global channel,reader,cell
    if sys.platform!='linux' or not Path('/dev/vport0p1').exists():raise RuntimeError('This kernel requires the isolated research VM')
    channel=open('/dev/vport0p1','r+b',buffering=0);reader=io.BufferedReader(channel)
    os.chmod('/dev/vport0p1',0o600)
    resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    resource.setrlimit(resource.RLIMIT_NOFILE,(128,128));resource.setrlimit(resource.RLIMIT_NPROC,(64,64))
    resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_CPU,(1800,1800))
    os.setgroups([]);os.setgid(1000);os.setuid(1000);os.chdir('/work')
    os.environ.update(HOME='/work',TMPDIR='/work/tmp',OPENBLAS_NUM_THREADS='2',OMP_NUM_THREADS='2')
    import numpy as np
    np.random.seed(2026110304)
    ns={'__name__':'__workspace__','np':np,'load_tensor':load_tensor,'save_edit':save_edit,
        'test_candidate':test_candidate,'compare_with_original':compare_with_original,'inspect_candidate':inspect_candidate,
        'load_observation':load_observation,'list_tensors':lambda:rpc('list'),
        'model_info':lambda:rpc('metadata'),'edit_status':lambda:rpc('status'),
        'undo_edit':lambda name:rpc('undo',name=name),'submit':lambda:rpc('submit')}
    ns.update(save_checkpoint=lambda label:rpc('checkpoint',label=label),
        restore_checkpoint=lambda label:rpc('restore',label=label))
    send({'op':'ready','uid':os.getuid(),'numpy':np.__version__,'persistent':True})
    while True:
        command=receive()
        if set(command)!={'op','cell','code'} or command['op']!='execute':raise ValueError('Invalid execution request')
        cell=command['cell'];out=Output();error=None
        try:
            with contextlib.redirect_stdout(out),contextlib.redirect_stderr(out):execute_cell(command['code'],ns)
        except BaseException:error=traceback.format_exc()[-4000:]
        send({'op':'cell_result','cell':cell,'output':out.text(),'error':error})


if __name__=='__main__':main()
