"""Opt-in, manually specified sparse parameter changes; no inference on import."""
import json
from pathlib import Path
import shutil
import struct
import sys

from lora6k_state import atomic,read,sha
from weight_editor_runtime import require,check_files,verify_unchanged_bytes


def bf16_round(value):
    import numpy as np
    value=np.asarray(value,dtype=np.float32)
    require(np.isfinite(value).all(),'Nonfinite input')
    bits=value.view(np.uint32)
    return (((bits+np.uint32(0x7fff)+((bits>>16)&1))>>16).astype(np.uint32)<<16).view(np.float32)


def rank_one_columns(weights,feature,direction,strength):
    import numpy as np
    w=np.asarray(weights,dtype=np.float32);f=np.asarray(feature,dtype=np.float32);v=np.asarray(direction,dtype=np.float32)
    require(w.ndim==2 and f.shape==(w.shape[1],) and v.shape==(w.shape[0],),'Rank-one shape mismatch')
    require(np.isfinite(w).all() and np.isfinite(f).all() and np.isfinite(v).all(),'Nonfinite rank-one data')
    require(type(strength) in (int,float) and 0<float(strength)<=1,'Bounded positive strength required')
    columns=np.flatnonzero(f)
    require(0<len(columns)<=128,'One to 128 sparse input columns required')
    edited=w.copy()
    edited[:,columns]=bf16_round(w[:,columns]+np.float32(strength)*v[:,None]*f[None,columns])
    require(np.isfinite(edited).all(),'Nonfinite changed weights')
    return edited,columns


def build_manual_feature(plan,feature,direction,strength,folder,deadline):
    """Add a diagnosis-derived sparse rank-one delta to canonical layer 29, then Q8."""
    import numpy as np
    folder=Path(folder);require(not folder.exists(),'Never overwrite candidate evidence')
    require(shutil.disk_usage(folder.parent).free>=20*2**30,'Disk floor')
    vendor=plan['cpu_vendor_sources'];check_files(vendor['path'],vendor['files']);sys.path.insert(0,vendor['path'])
    from gguf import GGUFReader,GGMLQuantizationType
    from gguf.quants import quantize
    base=plan['models']['editor_model'];require(sha(base['path'])==base['sha256'],'Immutable 4B changed')
    hf=Path(plan['tokenizers']['editor_tokenizer']['path']);name='model.language_model.layers.29.mlp.down_proj.weight'
    source=hf/read(hf/'model.safetensors.index.json')['weight_map'][name]
    expected={'model.safetensors-00001-of-00002.safetensors':'26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61',
              'model.safetensors-00002-of-00002.safetensors':'cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188'}
    require(sha(source)==expected[source.name],'Canonical weights changed')
    with source.open('rb') as stream:
        size=struct.unpack('<Q',stream.read(8))[0];header=json.loads(stream.read(size))
    tensor=header[name];require(tensor['dtype']=='BF16' and tensor['shape']==[2560,9216],'Unexpected canonical tensor')
    raw=np.memmap(source,dtype='<u2',mode='r',offset=8+size+tensor['data_offsets'][0],shape=(2560,9216))
    original=(raw.astype(np.uint32)<<16).view(np.float32)
    edited,columns=rank_one_columns(original,feature,direction,strength)
    key='blk.29.ffn_down.weight';before={t.name:t for t in GGUFReader(base['path']).tensors}
    require(before[key].tensor_type==GGMLQuantizationType.Q8_0,'Expected Q8 tensor')
    encoded_base=quantize(original,GGMLQuantizationType.Q8_0)
    require(np.array_equal(encoded_base,before[key].data),'Canonical baseline Q8 mismatch')
    encoded=quantize(edited,GGMLQuantizationType.Q8_0);a=encoded_base.reshape(-1,34);b=encoded.reshape(-1,34)
    changed=np.flatnonzero(np.any(a!=b,axis=1));require(len(changed)>0,'Q8 removed complete edit')
    block_columns=columns//32
    require(set(map(int,changed%(9216//32)))<=set(map(int,block_columns)),'Change escaped selected Q8 blocks')
    deadline.remaining();folder.mkdir();output=folder/'model-q8.gguf';shutil.copyfile(base['path'],output)
    mapped=np.memmap(output,dtype=np.uint8,mode='r+',offset=before[key].data_offset,shape=encoded.shape)
    mapped[:]=encoded;mapped.flush();del mapped
    after={t.name:t for t in GGUFReader(output).tensors}
    byte_check=verify_unchanged_bytes(base['path'],output,[(int(before[key].data_offset),int(encoded.nbytes))],deadline)
    np.savez_compressed(folder/'numeric-patch.npz',columns=columns,canonical_bf16=(edited[:,columns].view(np.uint32)>>16).astype(np.uint16),
                        q8_block_ids=changed,q8_new_blocks=b[changed],feature=np.asarray(feature),direction=np.asarray(direction))
    with np.load(folder/'numeric-patch.npz',allow_pickle=False) as patch:
        rebuilt=a.copy();rebuilt[patch['q8_block_ids']]=patch['q8_new_blocks']
        require(np.array_equal(rebuilt.reshape(encoded.shape),after[key].data),'Exact Q8 reconstruction failed')
    artifact={'path':str(output),'sha256':sha(output)}
    atomic(folder/'MANIFEST.json',{'model':artifact,'base_sha256':base['sha256'],'canonical_source_sha256':expected[source.name],
        'operator':'W_down[:,J] += strength * outer(direction, feature[J]); canonical BF16 then Q8',
        'layer':29,'strength':strength,'canonical_columns':list(map(int,columns)),'canonical_changed_values':int(np.count_nonzero(original!=edited)),
        'q8_changed_blocks':len(changed),'q8_block_neighbor_effects_possible':True,'other_tensors_unchanged':True,'byte_comparison':byte_check,'patch_roundtrip_exact':True,
        'authorship':'Codex manual contrastive activation diagnosis and rank-one design; no local-model numeric proposal',
        'scope':'Analytic fit on four practice contexts; no training optimizer; general improvement unproven'})
    return artifact
