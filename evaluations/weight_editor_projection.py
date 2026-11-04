"""Bounded numeric sparse projection actuator using original-target measurements."""
import math
from pathlib import Path
import shutil
import sys
from lora6k_state import atomic,read,sha
from weight_editor_feedback import final_json
from weight_editor_runtime import require,check_files,verify_unchanged_bytes
from weight_editor_sparse import bf16_round


def proposal(raw,layer_count):
    value=final_json(raw)
    if value=={'stop':True}:return None
    require(isinstance(value,dict) and set(value)=={'layers'} and isinstance(value['layers'],list) and 1<=len(value['layers'])<=2,'One or two projection edits required')
    result=[]
    for row in value['layers']:
        require(isinstance(row,dict) and set(row)=={'layer','strength','columns'},'Only layer, strength, columns')
        l,s,n=row['layer'],row['strength'],row['columns']
        require(type(l) is int and 0<=l<layer_count,'Invalid target layer')
        require(type(s) in (int,float) and math.isfinite(s) and s in (.25,.5,1),'Strength must be 0.25, 0.5 or 1')
        require(type(n) is int and n in (16,32,64),'Columns must be 16, 32 or 64')
        result.append({'layer':l,'strength':float(s),'columns':n})
    require(len({x['layer'] for x in result})==len(result),'Duplicate layer')
    return sorted(result,key=lambda x:x['layer'])


def project_columns(weights,direction,columns,strength):
    import numpy as np
    w=np.asarray(weights,dtype=np.float32);v=np.asarray(direction,dtype=np.float32);j=np.asarray(columns)
    require(w.ndim==2 and v.shape==(w.shape[0],) and j.ndim==1 and np.issubdtype(j.dtype,np.integer),'Projection shape/type mismatch')
    require(0<len(j)<=64 and len(set(map(int,j)))==len(j) and np.all((j>=0)&(j<w.shape[1])),'Invalid column indices')
    require(np.isfinite(w).all() and np.isfinite(v).all() and abs(float(v@v)-1)<1e-4,'Invalid unit direction')
    require(type(strength) in (float,int) and strength in (.25,.5,1),'Projection strength bound')
    result=w.copy();selected=w[:,j]
    result[:,j]=bf16_round(selected-np.float32(strength)*v[:,None]*(v@selected)[None,:])
    require(np.isfinite(result).all(),'Nonfinite projection')
    return result


def build_target(plan,edits,folder,deadline):
    import numpy as np
    vendor=plan['cpu_vendor_sources'];check_files(vendor['path'],vendor['files']);sys.path.insert(0,vendor['path'])
    from gguf import GGUFReader
    base=plan['models']['original_target'];require(sha(base['path'])==base['sha256'],'Original target changed')
    basis=Path(plan['projection_basis']['directions']);packet=Path(plan['projection_basis']['packet'])
    require(sha(basis)==plan['projection_basis']['directions_sha256'] and sha(packet)==plan['projection_basis']['packet_sha256'],'Local basis changed')
    require(plan['projection_basis']['no_published_vectors_used'] is True,'Invalid basis provenance')
    directions=np.load(basis,allow_pickle=False);lookup={x['layer']:x for x in read(packet)}
    folder=Path(folder);require(not folder.exists(),'Never overwrite artifact evidence')
    require(shutil.disk_usage(folder.parent).free>=20*2**30,'Disk floor');deadline.remaining()
    folder.mkdir();out=folder/'model-f32.gguf';shutil.copyfile(base['path'],out)
    before={x.name:x for x in GGUFReader(base['path']).tensors};after={x.name:x for x in GGUFReader(out).tensors};patch={};tensors=[]
    for i,edit in enumerate(edits):
        layer=edit['layer'];key=f'blk.{layer}.ffn_down.weight';w=before[key].data
        require(w.dtype==np.float32 and w.ndim==2,'Expected F32 target')
        columns=np.asarray(lookup[layer]['ranked_columns'][:edit['columns']],dtype=np.int64)
        changed=project_columns(w,directions[str(layer)],columns,edit['strength'])
        relative=float(np.linalg.norm((changed-w).astype(np.float64))/np.linalg.norm(w.astype(np.float64)))
        require(relative<=.1,'Per-tensor relative edit limit')
        mapped=np.memmap(out,dtype=np.float32,mode='r+',offset=after[key].data_offset,shape=w.shape);mapped[:]=changed;mapped.flush();del mapped
        patch[f'columns-{i}']=columns;patch[f'bf16-{i}']=(changed[:,columns].view(np.uint32)>>16).astype(np.uint16)
        tensors.append({'tensor':key,'columns':list(map(int,columns)),'relative_delta_norm':relative,
                        'changed_values':int(np.count_nonzero(changed!=w))})
    byte_check=verify_unchanged_bytes(base['path'],out,[(int(before[t['tensor']].data_offset),int(before[t['tensor']].data.nbytes)) for t in tensors],deadline)
    np.savez_compressed(folder/'numeric-patch.npz',**patch)
    with np.load(folder/'numeric-patch.npz',allow_pickle=False) as saved:
        for i,t in enumerate(tensors):
            rebuilt=before[t['tensor']].data.copy();j=saved[f'columns-{i}']
            rebuilt[:,j]=(saved[f'bf16-{i}'].astype(np.uint32)<<16).view(np.float32)
            require(np.array_equal(rebuilt,after[t['tensor']].data),'Exact sparse patch reconstruction failed')
    artifact={'path':str(out),'sha256':sha(out)};require(artifact['sha256']!=base['sha256'],'No surviving edit')
    atomic(folder/'MANIFEST.json',{'model':artifact,'base_sha256':base['sha256'],'edits':edits,'tensors':tensors,
        'other_tensors_unchanged':True,'byte_comparison':byte_check,'patch_roundtrip_exact':True,'published_vectors_supplied':False,
        'basis_provenance':plan['projection_basis'],
        'authorship':'Local 4B selects layer, strength and column count; trusted tool supplies locally measured original-target basis and applies sparse projection',
        'scope':'Supplied-basis bounded sparse weight editing; not unrestricted direction rediscovery'})
    return artifact
