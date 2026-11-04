"""Explicit user-approved League sharing for research, never enabled on import."""
import re
import time
import math
import ntpath

from weight_editor_runtime import require


APPROVED = frozenset(('league of legends.exe','leagueclientuxrender.exe'))
IDLE_OVERLAYS = frozenset(('gamebar.exe','xboxgamebarwidgets.exe','gamebarftserver.exe','gamebarpresencewriter.exe'))
IDLE_CAPTURE_APPS = frozenset(('snippingtool.exe',))


def classify_shared_owners(rows,names,compute,base_check):
    """Only the named game may share compute; preserve all other owner checks."""
    ordinary=[];shared=[]
    for row in rows:
        require(len(row)==3 and isinstance(row[0],str) and row[0].strip().isdigit(),'Invalid GPU owner row')
        pid=int(row[0].strip());name=names.get(pid,'')
        overlay_name=name or ntpath.basename(row[1].strip())
        if name.lower() in APPROVED:
            shared.append({'pid':pid,'name':name,'reported_memory':row[2],
                'classification':'User-approved shared League graphics/compute; timing not comparable to idle control'})
        elif overlay_name.lower() in (IDLE_OVERLAYS|IDLE_CAPTURE_APPS) and row[2].strip() in ('N/A','[N/A]','[Not Supported]'):
            shared.append({'pid':pid,'name':overlay_name,'live_name_observed':bool(name),'reported_memory':row[2],
                'classification':'Idle Windows overlay/capture app; active capture-app compute still rejected'})
        else:ordinary.append(row)
    from lora6k_supervisor import DESKTOP_GPU_PROCESSES
    other_compute=[];desktop_compute=[]
    for item in compute:
        match=re.match(r'^pid_(\d+)_',item.get('Name',''))
        if match and names.get(int(match[1]),'').lower() in APPROVED:continue
        if match and names.get(int(match[1]),'').lower() in (DESKTOP_GPU_PROCESSES|IDLE_OVERLAYS):
            value=item.get('UtilizationPercentage')
            if type(value) in (int,float) and math.isfinite(value) and 0<=value<=100:
                desktop_compute.append(item);continue
        other_compute.append(item)
    # Windows voice/video/UI effects can make brief CUDA calls. Only known
    # desktop apps receive this small, aggregate allowance; Python/unknown
    # compute remains an error even at one percent.
    if sum(item['UtilizationPercentage'] for item in desktop_compute)>5:other_compute.extend(desktop_compute)
    return base_check(ordinary,names,other_compute)+shared


def admission(observe,deadline,*,sleep=time.sleep,clock=time.monotonic):
    """Three memory/ownership samples; user permits a non-idle GPU here.

    The caller's observe still records measured utilization and enforces the
    owner policy. No fake utilization is supplied and no resource floor falls.
    """
    began=clock()
    for index in range(3):
        deadline.remaining();sample=observe(min(10,deadline.remaining()));deadline.remaining()
        require(sample['free_vram_mib']>=8192,'Admission VRAM floor')
        require(sample['free_ram_kib']>=8*2**20 and sample['free_commit_bytes']>=4*2**30,'Admission RAM/commit floor')
        require(sample['disk_bytes']>=20*2**30,'Admission disk floor')
        require(clock()-began<60,'No stable memory admission within 60 seconds')
        if index<2:sleep(min(2,deadline.remaining()))
    deadline.remaining()
