"""Trusted bounded CPU application of locally proposed 4B FFN interventions."""
import math
from pathlib import Path
import shutil
import struct
import sys
import json

from lora6k_state import atomic, sha
from weight_editor_runtime import require, check_files


def validate(proposal, statistics):
    require(isinstance(proposal, dict) and set(proposal)=={'layer','columns','scale'}, 'Only layer, columns and scale allowed')
    layer, cols, scale = [proposal[k] for k in ('layer','columns','scale')]
    require(type(layer) is int and 0 <= layer < 32, 'Invalid layer')
    require(isinstance(cols,list) and 1 <= len(cols) <= 4 and len(set(cols))==len(cols)
            and all(type(c) is int for c in cols), 'One to four distinct integer columns required')
    available={v['column'] for row in statistics['layers'] if row['layer']==layer for v in row['largest_columns'][:4]}
    require(set(cols)<=available, 'Columns outside supplied diagnostic inventory')
    require(type(scale) in (int,float) and math.isfinite(scale) and .9 <= scale <= 1.1 and scale != 1., 'Nontrivial finite scale in [0.9,1.1] required')
    return {'layer':layer,'columns':sorted(cols),'scale':float(scale)}


def build(plan, proposal, folder, statistics, deadline):
    """Preserve the immutable BF16/Q8 bases and every untouched quantization block."""
    import numpy as np
    proposal=validate(proposal,statistics);folder=Path(folder)
    require(not folder.exists(),'Never overwrite patch evidence')
    check_files(plan['cpu_vendor_sources']['path'],plan['cpu_vendor_sources']['files'])
    sys.path.insert(0,plan['cpu_vendor_sources']['path'])
    from gguf import GGUFReader,GGMLQuantizationType
    from gguf.quants import quantize
    base=plan['models']['editor_model'];require(sha(base['path'])==base['sha256'],'Q8 base changed')
    require(shutil.disk_usage(folder.parent).free>=20*2**30,'Disk admission floor')
    hf=Path(plan['tokenizers']['editor_tokenizer']['path'])
    name=f"model.language_model.layers.{proposal['layer']}.mlp.down_proj.weight"
    index=json.loads((hf/'model.safetensors.index.json').read_text('utf8'));source=hf/index['weight_map'][name]
    require(sha(source)==statistics['pinned_shards'][source.name],'Canonical BF16 shard changed')
    with source.open('rb') as stream:
        n=struct.unpack('<Q',stream.read(8))[0];header=json.loads(stream.read(n))
    info=header[name];require(info['dtype']=='BF16' and info['shape']==[2560,9216],'Canonical tensor mismatch')
    bits=np.memmap(source,dtype='<u2',mode='r',offset=8+n+info['data_offsets'][0],shape=(2560,9216))
    x=(bits.astype(np.uint32)<<16).view(np.float32)
    tensor_name=f"blk.{proposal['layer']}.ffn_down.weight"
    before={t.name:t for t in GGUFReader(base['path']).tensors};target=before[tensor_name]
    require(target.tensor_type==GGMLQuantizationType.Q8_0,'Expected Q8_0 tensor')
    require(np.array_equal(quantize(x,GGMLQuantizationType.Q8_0),target.data),'Canonical tensor does not reconstruct exact Q8 base')
    y=x.copy();cols=proposal['columns'];values=(y[:,cols]*np.float32(proposal['scale'])).copy()
    raw=values.view(np.uint32);rounded=((raw+np.uint32(0x7fff)+((raw>>16)&1))>>16).astype(np.uint16)
    y[:,cols]=(rounded.astype(np.uint32)<<16).view(np.float32)
    require(np.isfinite(y).all(),'Nonfinite edited values')
    encoded=quantize(y,GGMLQuantizationType.Q8_0)
    original=target.data.reshape(2560,-1,34);changed=encoded.reshape(2560,-1,34)
    allowed_blocks={c//32 for c in cols};unallowed=[i for i in range(288) if i not in allowed_blocks]
    require(np.array_equal(original[:,unallowed],changed[:,unallowed]),'Unexpected quantization-block change')
    require(not np.array_equal(encoded,target.data),'Quantization erased the intervention')
    deadline.remaining();folder.mkdir();output=folder/'model-q8.gguf';shutil.copyfile(base['path'],output)
    mapped=np.memmap(output,dtype=np.uint8,mode='r+',offset=target.data_offset,shape=target.data.shape)
    mapped[:]=encoded;mapped.flush();del mapped
    after={t.name:t for t in GGUFReader(output).tensors}
    for key in before:
        deadline.remaining()
        if key!=tensor_name:require(np.array_equal(before[key].data,after[key].data),'Untouched tensor changed')
    np.savez_compressed(folder/'canonical-sparse-patch.npz',columns=np.array(cols,dtype=np.uint32),bf16_values=rounded)
    with np.load(folder/'canonical-sparse-patch.npz',allow_pickle=False) as patch:
        reconstructed=x.copy();reconstructed[:,patch['columns']]=(patch['bf16_values'].astype(np.uint32)<<16).view(np.float32)
        require(np.array_equal(quantize(reconstructed,GGMLQuantizationType.Q8_0),after[tensor_name].data),'Sparse reconstruction failed')
    artifact={'path':str(output),'sha256':sha(output)}
    atomic(folder/'MANIFEST.json',{'model':artifact,'proposal':proposal,'base_sha256':base['sha256'],
        'canonical_tensor':name,'canonical_source_sha256':statistics['pinned_shards'][source.name],
        'base_canonical_quantization_exact':True,'sparse_roundtrip_exact':True,'other_tensors_unchanged':True,
        'allowed_quantization_blocks':sorted(allowed_blocks),'canonical_changed_entries':int(np.sum(y[:,cols]!=x[:,cols])),
        'authorship':'Numeric layer/columns/scale chosen by the local unchanged 4B; host applies a predeclared bounded operator',
        'scope':'Exploratory intervention, not a verified repair or discovered neuron semantics'})
    return artifact
