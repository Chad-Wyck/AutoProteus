"""Trusted numeric interface for matched editors modifying an original target."""
import math
from pathlib import Path
import shutil
import sys

from lora6k_state import atomic,sha
from weight_editor_feedback import final_json
from weight_editor_runtime import require,check_files,verify_unchanged_bytes


def distinct_paths(paths):
    normalized=[str(Path(p).resolve()).casefold() for p in paths]
    require(len(set(normalized))==len(normalized),'Case-insensitive input/output path collision')


def proposal(raw,layer_count):
    value=final_json(raw)
    if value=={'stop':True}:return None
    require(set(value)=={'layers'} and isinstance(value['layers'],list) and 1<=len(value['layers'])<=2,'One or two layer edits required')
    edits=[]
    for row in value['layers']:
        require(isinstance(row,dict) and set(row)=={'layer','scale'},'Only layer and scale accepted')
        layer,scale=row['layer'],row['scale']
        require(type(layer) is int and 0<=layer<layer_count,'Layer outside target')
        require(type(scale) in (int,float) and math.isfinite(scale) and .5<=scale<=1.5 and scale!=1.,'Finite nontrivial scale in [0.5,1.5] required')
        edits.append({'layer':layer,'scale':float(scale)})
    require(len({r['layer'] for r in edits})==len(edits),'Duplicate layer')
    return sorted(edits,key=lambda r:r['layer'])


def build_target(plan,edits,folder,deadline):
    """Apply only local-editor numeric choices to a separate ORIGINAL F32 GGUF."""
    import numpy as np
    vendor=plan['cpu_vendor_sources'];check_files(vendor['path'],vendor['files']);sys.path.insert(0,vendor['path'])
    from gguf import GGUFReader
    base=plan['models']['original_target'];require(sha(base['path'])==base['sha256'],'Original target changed')
    folder=Path(folder);require(not folder.exists(),'Never overwrite candidate evidence')
    require(shutil.disk_usage(folder.parent).free>=20*2**30,'Candidate disk floor')
    deadline.remaining();folder.mkdir();output=folder/'model-f32.gguf';shutil.copyfile(base['path'],output)
    before={t.name:t for t in GGUFReader(base['path']).tensors};after={t.name:t for t in GGUFReader(output).tensors}
    selected=set();patch={};tensors=[]
    for i,edit in enumerate(edits):
        key=f"blk.{edit['layer']}.ffn_down.weight";selected.add(key);source=before[key].data
        require(source.dtype==np.float32 and source.ndim==2,'Expected F32 target FFN')
        value=source*np.float32(edit['scale']);bits=value.view(np.uint32)
        bf16=((bits+np.uint32(0x7fff)+((bits>>16)&1))>>16).astype(np.uint16)
        value=(bf16.astype(np.uint32)<<16).view(np.float32);require(np.isfinite(value).all(),'Nonfinite target edit')
        mapped=np.memmap(output,dtype=np.float32,mode='r+',offset=after[key].data_offset,shape=source.shape)
        mapped[:]=value;mapped.flush();del mapped
        patch['bf16-'+str(i)]=bf16
        tensors.append({'tensor':key,'scale':edit['scale'],'changed_entries':int(np.count_nonzero(value.view(np.uint32)!=source.view(np.uint32)))})
    byte_check=verify_unchanged_bytes(base['path'],output,[(int(before[key].data_offset),int(before[key].data.nbytes)) for key in selected],deadline)
    np.savez_compressed(folder/'numeric-patch.npz',**patch)
    with np.load(folder/'numeric-patch.npz',allow_pickle=False) as saved:
        for i,t in enumerate(tensors):
            rebuilt=(saved['bf16-'+str(i)].astype(np.uint32)<<16).view(np.float32)
            require(np.array_equal(rebuilt,after[t['tensor']].data),'Target patch roundtrip failed')
    artifact={'path':str(output),'sha256':sha(output)}
    atomic(folder/'MANIFEST.json',{'model':artifact,'base_sha256':base['sha256'],'edits':edits,'tensors':tensors,
        'patch_roundtrip_exact':True,'other_tensors_unchanged':True,'byte_comparison':byte_check,
        'authorship':'Local 4B editor chooses layer indices and scalar values; trusted host applies the declared operator',
        'published_repair_direction_supplied':False,'scope':'Bounded whole-FFN layer-scaling search; not unrestricted weight-direction discovery'})
    require(artifact['sha256']!=base['sha256'],'BF16 rounding removed the entire edit')
    return artifact
