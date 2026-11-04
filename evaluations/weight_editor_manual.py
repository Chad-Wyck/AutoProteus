"""Manually designed, diagnosis-bound parameter interventions; CPU application."""
import json
from pathlib import Path
import shutil
import struct
import sys

from lora6k_state import atomic,read,sha
from weight_editor_runtime import require,check_files,verify_unchanged_bytes


def half_ffn(plan,layer,folder,deadline):
    """Halve one measured FFN writer; verify canonical BF16 and deployed Q8 exactly."""
    import numpy as np
    require(type(layer) is int and layer in (18,29),'Only manually selected diagnosis layers')
    folder=Path(folder);require(not folder.exists(),'Never overwrite a manual candidate')
    require(shutil.disk_usage(folder.parent).free>=20*2**30,'Candidate disk floor')
    vendor=plan['cpu_vendor_sources'];check_files(vendor['path'],vendor['files']);sys.path.insert(0,vendor['path'])
    from gguf import GGUFReader,GGMLQuantizationType
    from gguf.quants import quantize
    base=plan['models']['editor_model'];require(sha(base['path'])==base['sha256'],'Immutable 4B changed')
    hf=Path(plan['tokenizers']['editor_tokenizer']['path']);name=f'model.language_model.layers.{layer}.mlp.down_proj.weight'
    source=hf/read(hf/'model.safetensors.index.json')['weight_map'][name]
    expected={'model.safetensors-00001-of-00002.safetensors':'26a93f066e1916adb13453dae5a0c707c0fbc71299ed98779571a907b8e74c61',
              'model.safetensors-00002-of-00002.safetensors':'cb544bd9bfae93dc59b0f22b292f5933573854a7f9b97835c67060d7d910e188'}
    require(sha(source)==expected[source.name],'Canonical 4B changed')
    with source.open('rb') as stream:n=struct.unpack('<Q',stream.read(8))[0];header=json.loads(stream.read(n))
    t=header[name];require(t['dtype']=='BF16' and t['shape']==[2560,9216],'Unexpected canonical tensor')
    bits=np.memmap(source,dtype='<u2',mode='r',offset=8+n+t['data_offsets'][0],shape=(2560,9216))
    original=(bits.astype(np.uint32)<<16).view(np.float32);edited=original*np.float32(.5)
    require(np.isfinite(edited).all(),'Nonfinite manual weights')
    raw=edited.view(np.uint32);rounded=((raw+np.uint32(0x7fff)+((raw>>16)&1))>>16).astype(np.uint16)
    require(np.array_equal((rounded.astype(np.uint32)<<16).view(np.float32),edited),'Half scaling not exact in BF16')
    key=f'blk.{layer}.ffn_down.weight';before={t.name:t for t in GGUFReader(base['path']).tensors}
    require(before[key].tensor_type==GGMLQuantizationType.Q8_0,'Expected Q8 tensor')
    require(np.array_equal(quantize(original,GGMLQuantizationType.Q8_0),before[key].data),'Canonical baseline Q8 differs')
    encoded=quantize(edited,GGMLQuantizationType.Q8_0)
    a=before[key].data.reshape(-1,34);b=encoded.reshape(-1,34)
    require(np.array_equal(a[:,2:],b[:,2:]),'Half scaling changed Q8 integer codes')
    old_scales=np.ascontiguousarray(a[:,:2]).view('<f2').reshape(-1)
    new_scales=np.ascontiguousarray(b[:,:2]).view('<f2').reshape(-1)
    # Quantize(canonical * .5) can differ by an FP16 rounding step from
    # .5 * Quantize(canonical). The canonical rebuild is authoritative.
    desired=old_scales.astype(np.float32)*np.float32(.5)
    scale_error=new_scales.astype(np.float32)-desired
    integer_norm=np.sum(a[:,2:].view(np.int8).astype(np.float32)**2,axis=1,dtype=np.float64)
    relative_l2=float(np.sqrt(np.sum(scale_error.astype(np.float64)**2*integer_norm)/np.sum(desired.astype(np.float64)**2*integer_norm)))
    require(relative_l2<=.001,'Canonical Q8 rounding exceeds numeric survival bound')
    deadline.remaining();folder.mkdir();output=folder/'model-q8.gguf';shutil.copyfile(base['path'],output)
    mapped=np.memmap(output,dtype=np.uint8,mode='r+',offset=before[key].data_offset,shape=before[key].data.shape)
    mapped[:]=encoded;mapped.flush();del mapped
    after={t.name:t for t in GGUFReader(output).tensors}
    byte_check=verify_unchanged_bytes(base['path'],output,[(int(before[key].data_offset),int(encoded.nbytes))],deadline)
    np.savez_compressed(folder/'q8-scale-patch.npz',new_scale_bytes=b[:,:2])
    rebuilt=a.copy();rebuilt[:,:2]=np.load(folder/'q8-scale-patch.npz',allow_pickle=False)['new_scale_bytes']
    require(np.array_equal(rebuilt.reshape(encoded.shape),after[key].data),'Exact Q8 patch reconstruction failed')
    artifact={'path':str(output),'sha256':sha(output)}
    atomic(folder/'MANIFEST.json',{'model':artifact,'authorship':'Codex manual diagnosis and design; no local-model numeric proposal',
        'operator':'Multiply one canonical FFN down-projection tensor by 0.5','layer':layer,'scale':.5,
        'canonical_source_sha256':expected[source.name],'canonical_tensor':name,'base_sha256':base['sha256'],
        'canonical_bf16_half_exact':True,'canonical_to_q8_baseline_exact':True,'q8_integer_codes_unchanged':True,
        'q8_scales_exactly_halved':bool(np.array_equal(new_scales.astype(np.float32),desired)),
        'q8_rounding_relative_l2':relative_l2,'q8_scale_rounding_difference_blocks':int(np.count_nonzero(scale_error)),
        'q8_scale_rounding_max_absolute':float(np.max(np.abs(scale_error))),
        'other_tensors_unchanged':True,'byte_comparison':byte_check,'q8_patch_roundtrip_exact':True,
        'canonical_changed_entries':int(np.count_nonzero(original!=edited)),
        'scope':'Research candidate derived from transient dose response; general improvement remains unproven'})
    return artifact
