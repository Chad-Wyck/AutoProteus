"""Explicitly opted-in memory admission; background GPU activity is advisory."""
import csv,json,math,re,shutil,subprocess,time,uuid
from datetime import datetime,timezone
from pathlib import Path
from lora6k_state import atomic,read
from weight_editor_runtime import require

NAME='memory-availability-v1'
FLOORS={'admission_free_vram_mib':8192,'running_free_vram_mib':2048,
    'admission_free_ram_mib':8192,'running_free_ram_mib':6144,'free_commit_mib':4096,
    'owned_shared_gpu_mib':512,'admission_disk_gib':20,'running_disk_gib':5}


def config(root):
    value=read(Path(root)/'manifest.json').get('resource_policy')
    if value is None:return None
    require(value.get('name')==NAME and value.get('floors')==FLOORS,'Unreviewed resource policy')
    require(value.get('background_utilization_is_advisory') is True,'Resource policy changed')
    require(isinstance(value.get('gpu_uuid'),str) and isinstance(value.get('gpu_pci_bus_id'),str),'Missing selected GPU identity')
    return value


def validate_memory(sample,stage):
    require(stage in ('admission','running'),'Unknown resource phase')
    for key in ('free_vram_mib','total_vram_mib','free_ram_kib','free_commit_bytes','disk_bytes'):
        value=sample[key];require(type(value) in (int,float) and math.isfinite(value) and value>=0,'Invalid critical measurement: '+key)
    require(sample['total_vram_mib']>0 and sample['free_vram_mib']<=sample['total_vram_mib'],'Invalid aggregate VRAM measurement')
    require(sample['free_vram_mib']>=FLOORS[stage+'_free_vram_mib'],'Memory policy VRAM floor')
    require(sample['free_ram_kib']>=FLOORS[stage+'_free_ram_mib']*1024,'Memory policy RAM floor')
    require(sample['free_commit_bytes']>=FLOORS['free_commit_mib']*2**20,'Memory policy commit floor')
    require(sample['disk_bytes']>=FLOORS[stage+'_disk_gib']*2**30,'Memory policy disk floor')
    for row in sample['gpu']:
        for key in ('SharedUsage','DedicatedUsage'):
            require(type(row[key]) in (int,float) and math.isfinite(row[key]) and row[key]>=0,'Invalid owned GPU memory counter')
    require(sum(row['SharedUsage'] for row in sample['gpu'])<=FLOORS['owned_shared_gpu_mib']*2**20,'Memory policy shared GPU floor')
    return sample


def observe(root,folder,remaining,*,owned_pids=(),stage,context=None):
    root,folder=Path(root),Path(folder);policy=config(root);require(policy is not None,'Memory policy opt-in required')
    owned=sorted(set(int(p) for p in owned_pids));nonce=uuid.uuid4().hex
    record={'observation_id':nonce,'stage':stage,'began_utc':datetime.now(timezone.utc).isoformat(),
        'policy':NAME,'owned_pids':owned,'context':context or {}}
    def persist(status):
        record.update(status=status,recorded_utc=datetime.now(timezone.utc).isoformat())
        atomic(folder/'resources'/(nonce+'-'+status+'.json'),record)
    try:
        remaining()
        raw=subprocess.check_output(['nvidia-smi','--id=0','--query-gpu=uuid,pci.bus_id,memory.total,memory.free,utilization.gpu',
            '--format=csv,noheader,nounits'],text=True,timeout=min(10,remaining()))
        record['nvidia_memory_raw']=raw
        values=list(csv.reader(raw.strip().splitlines()));require(len(values)==1 and len(values[0])==5,'Ambiguous aggregate GPU measurement')
        gpu_id,pci,total,free,util=(v.strip() for v in values[0])
        require(gpu_id==policy['gpu_uuid'] and pci==policy['gpu_pci_bus_id'],'Selected GPU identity changed')
        pattern='^pid_('+'|'.join(str(p) for p in owned)+')_' if owned else '(?!)'
        command=("$ErrorActionPreference='Stop'; $o=Get-CimInstance Win32_OperatingSystem; "
            "$m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; "
            "$g=@(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory | Where-Object {$_.Name -match '"+pattern+"'}); "
            "[pscustomobject]@{free_ram_kib=$o.FreePhysicalMemory;free_commit_bytes=([long]$m.CommitLimit-[long]$m.CommittedBytes); "
            "gpu=@($g | Select-Object Name,SharedUsage,DedicatedUsage)} | ConvertTo-Json -Depth 4 -Compress")
        host_raw=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],text=True,timeout=min(20,remaining()))
        record['critical_cim_raw']=host_raw;host=json.loads(host_raw)
        try:percent=float(util);percent=percent if math.isfinite(percent) and 0<=percent<=100 else None
        except ValueError:percent=None
        require(isinstance(host.get('gpu'),list),'Missing owned GPU memory schema')
        for item in host['gpu']:
            require(any(item['Name'].startswith('pid_'+str(p)+'_') for p in owned),'Unbound owned GPU memory row')
        sample={**host,'gpu_uuid':gpu_id,'gpu_pci_bus_id':pci,'total_vram_mib':int(total),'free_vram_mib':int(free),
            'utilization':percent,'disk_bytes':shutil.disk_usage(root).free}
        record['sample']=sample;validate_memory(sample,stage);persist('memory_validated')
    except BaseException as error:
        record['error']=type(error).__name__+': '+str(error);persist('critical_failure');raise
    # Advisory telemetry cannot become a utilization/name-based stop. Its absence
    # is explicit, while critical memory/owned-process monitoring stays mandatory.
    try:
        command=("$ErrorActionPreference='Stop';$p=@(Get-CimInstance Win32_Process | Select-Object ProcessId,Name,ParentProcessId,CreationDate); "
            "$e=@(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | Select-Object Name,UtilizationPercentage); "
            "[pscustomobject]@{processes=$p;engines=$e} | ConvertTo-Json -Depth 4 -Compress")
        raw=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],text=True,timeout=min(5,remaining()))
        record['advisory_cim_raw']=raw;value=json.loads(raw);record['background']=value
        require(isinstance(value['processes'],list) and isinstance(value['engines'],list),'Advisory counter schema')
        sample['advisory_status']='available'
    except Exception as error:
        record['advisory_error']=type(error).__name__+': '+str(error);sample['advisory_status']='unavailable'
    try:remaining()
    except BaseException as error:
        record['error']=type(error).__name__+': '+str(error);persist('critical_failure');raise
    record['sample']=sample;persist('accepted')
    return sample
