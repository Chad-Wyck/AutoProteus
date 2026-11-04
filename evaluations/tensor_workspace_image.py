"""Separate pinned NumPy VM image; no modification of the normal AP appliance."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import stat
import urllib.request
import zipfile

WHEEL='numpy-2.4.6-cp314-cp314-musllinux_1_2_x86_64.whl'
WHEEL_SHA='ae506e6902902557576a26ff33eda8695e7ecb3cb36c3b573a0765dee114ebdb'


def acquire(directory):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True);destination=directory/WHEEL
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest()!=WHEEL_SHA:raise ValueError('Cached NumPy wheel changed')
        return destination
    with urllib.request.urlopen('https://pypi.org/pypi/numpy/2.4.6/json',timeout=30) as response:metadata=json.load(response)
    row=next(x for x in metadata['urls'] if x['filename']==WHEEL)
    if row['digests']['sha256']!=WHEEL_SHA or row['size']>30*1024**2:raise ValueError('Pinned NumPy metadata mismatch')
    with urllib.request.urlopen(row['url'],timeout=60) as response:data=response.read(30*1024**2+1)
    if len(data)!=row['size'] or hashlib.sha256(data).hexdigest()!=WHEEL_SHA:raise ValueError('NumPy download failed verification')
    destination.write_bytes(data);return destination


def unpack_cpio(raw):
    entries={};offset=0
    while offset<len(raw):
        if raw[offset:offset+6]!=b'070701':raise ValueError('Unexpected base initramfs format')
        fields=[int(raw[offset+6+i*8:offset+14+i*8],16) for i in range(13)]
        end=offset+110+fields[11];name=raw[offset+110:end-1].decode();start=(end+3)&~3;finish=start+fields[6]
        if finish>len(raw):raise ValueError('Truncated initramfs')
        if name=='TRAILER!!!':return entries
        if name.startswith('/') or '..' in name.split('/') or name in entries:raise ValueError('Unsafe/duplicate initramfs entry')
        entries[name]=(fields[1],raw[start:finish]);offset=(finish+3)&~3
    raise ValueError('Missing initramfs trailer')


INIT=b'''#!/bin/sh
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 PYTHONDONTWRITEBYTECODE=1
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mkdir -p /dev/pts /work /run
mount -t devpts devpts /dev/pts
mount -t tmpfs -o size=768m,nosuid,nodev tmpfs /work
mount -t tmpfs -o size=64m,nosuid,nodev tmpfs /run
mkdir -p /work/tmp
chown -R 1000:1000 /work
while [ ! -e /dev/vport0p1 ]; do sleep 0.05; done
exec /usr/bin/python3 -I -B -u /tensor_kernel.py >/dev/null 2>/dev/console
'''


def build(project,directory,wheel):
    project,directory,wheel=map(Path,(project,directory,wheel));directory.mkdir(parents=True,exist_ok=True)
    from controller.appliance import cpio,digest
    record=json.loads((project/'.runtime/isolation/installed.json').read_text());source=project/'.runtime/isolation/initrd.gz'
    if digest(source)!=record['files']['initrd.gz'] or digest(wheel)!=WHEEL_SHA:raise ValueError('Image source checksum mismatch')
    entries=unpack_cpio(gzip.decompress(source.read_bytes()));entries['init']=(stat.S_IFREG|0o555,INIT)
    kernel=project/'evaluations/tensor_workspace_guest.py';entries['tensor_kernel.py']=(stat.S_IFREG|0o444,kernel.read_bytes())
    with zipfile.ZipFile(wheel) as archive:
        if sum(x.file_size for x in archive.infolist())>180*1024**2:raise ValueError('Wheel expansion exceeds limit')
        for info in archive.infolist():
            if info.is_dir():continue
            name=info.filename
            if name.startswith('/') or '..' in name.split('/') or stat.S_ISLNK(info.external_attr>>16):raise ValueError('Unsafe wheel entry')
            target='usr/lib/python3.14/site-packages/'+name
            if target in entries:raise ValueError('NumPy would overwrite a base-image entry')
            parent=Path(target).parent
            for directory_name in reversed([parent,*parent.parents]):
                key=directory_name.as_posix()
                if key!='.':entries.setdefault(key,(stat.S_IFDIR|0o555,b''))
            entries[target]=(stat.S_IFREG|0o444,archive.read(info))
    output=directory/'initrd.gz';output.write_bytes(gzip.compress(cpio(entries),compresslevel=3,mtime=0))
    result={'image':str(output.resolve()),'image_sha256':digest(output),'base_image_sha256':record['files']['initrd.gz'],
        'numpy':WHEEL,'numpy_sha256':WHEEL_SHA,'guest_sha256':digest(kernel),
        'kernel':str((project/'.runtime/isolation/vmlinuz').resolve()),'kernel_sha256':record['files']['vmlinuz']}
    (directory/'image.json').write_text(json.dumps(result,indent=2),encoding='utf-8');return result
