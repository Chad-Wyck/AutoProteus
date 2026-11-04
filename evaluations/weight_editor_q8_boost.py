"""Explicit Q8-space manual FFN boost, separate from canonical BF16 repairs."""
from pathlib import Path
import shutil
import sys
from lora6k_state import atomic,sha
from weight_editor_runtime import require,check_files,verify_unchanged_bytes


def boost_bytes(encoded):
    import numpy as np
    src=np.asarray(encoded,dtype=np.uint8);require(src.ndim==2 and src.shape[1]%34==0,'Expected Q8_0 row bytes')
    a=src.reshape(-1,34);b=a.copy();old=np.ascontiguousarray(a[:,:2]).view('<f2').reshape(-1)
    require(np.isfinite(old).all(),'Nonfinite original Q8 scales')
    desired=old.astype(np.float32)*np.float32(1.1);new=desired.astype('<f2')
    require(np.isfinite(new).all(),'Nonfinite boosted Q8 scales')
    b[:,:2]=new.view(np.uint8).reshape(-1,2)
    require(np.array_equal(a[:,2:],b[:,2:]),'Q8 integer codes changed')
    return b.reshape(src.shape)


def build_boost(plan,layer,folder,deadline):
    import numpy as np
    require(type(layer) is int and layer in (18,29),'Only two independently diagnosed layers')
    folder=Path(folder);require(not folder.exists(),'Never overwrite manual candidate')
    require(shutil.disk_usage(folder.parent).free>=20*2**30,'Disk floor')
    vendor=plan['cpu_vendor_sources'];check_files(vendor['path'],vendor['files']);sys.path.insert(0,vendor['path'])
    from gguf import GGUFReader,GGMLQuantizationType
    base=plan['models']['editor_model'];require(sha(base['path'])==base['sha256'],'Original 4B changed')
    before={t.name:t for t in GGUFReader(base['path']).tensors};key=f'blk.{layer}.ffn_down.weight'
    require(before[key].tensor_type==GGMLQuantizationType.Q8_0,'Wrong tensor quantization')
    value=boost_bytes(before[key].data);a=before[key].data.reshape(-1,34);b=value.reshape(-1,34)
    old=np.ascontiguousarray(a[:,:2]).view('<f2').reshape(-1).astype(np.float64)
    new=np.ascontiguousarray(b[:,:2]).view('<f2').reshape(-1).astype(np.float64)
    norm=np.sum(a[:,2:].view(np.int8).astype(np.float64)**2,axis=1)
    rel=float(np.sqrt(np.sum((new-old)**2*norm)/np.sum(old**2*norm)))
    require(.099<=rel<=.101,'Decoded Q8 delta not approximately 10 percent')
    deadline.remaining();folder.mkdir();out=folder/'model-q8.gguf';shutil.copyfile(base['path'],out)
    mapped=np.memmap(out,dtype=np.uint8,mode='r+',offset=before[key].data_offset,shape=value.shape);mapped[:]=value;mapped.flush();del mapped
    after={t.name:t for t in GGUFReader(out).tensors}
    byte_check=verify_unchanged_bytes(base['path'],out,[(int(before[key].data_offset),int(value.nbytes))],deadline)
    np.savez_compressed(folder/'q8-scale-patch.npz',new_scale_bytes=b[:,:2])
    patch=np.load(folder/'q8-scale-patch.npz',allow_pickle=False);rebuilt=a.copy();rebuilt[:,:2]=patch['new_scale_bytes']
    require(np.array_equal(rebuilt.reshape(value.shape),after[key].data),'Exact scale patch reconstruction failed')
    artifact={'path':str(out),'sha256':sha(out)}
    atomic(folder/'MANIFEST.json',{'model':artifact,'base_sha256':base['sha256'],'layer':layer,'scale':1.1,
        'operator':'Multiply original deployed Q8_0 block scales by 1.1, round scale to FP16; integer codes unchanged',
        'precision_scope':'Q8-space manual parameter edit; not claimed identical to a canonical BF16 multiplication/requantization',
        'relative_decoded_tensor_delta':rel,'integer_codes_unchanged':True,'other_tensors_unchanged':True,'byte_comparison':byte_check,'patch_roundtrip_exact':True,
        'authorship':'Codex manual hypothesis from completion loss after scaling these diagnosed FFNs down; no local-model weight proposal',
        'scope':'Whole one-FFN tensor scales, not a sparse canonical-weight edit; no capability improvement claimed before testing'})
    return artifact
