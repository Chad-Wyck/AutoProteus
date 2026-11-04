"""Windows training watchdog. Imported only by an explicitly authorized start."""
from datetime import datetime, timezone
import csv
import importlib.util
import json
import os
import ntpath
from pathlib import Path
import shutil
import subprocess
import sys
import time
import uuid

from lora6k_state import atomic, exclusive, read, sha


DESKTOP_GPU_PROCESSES = frozenset(name.lower() for name in (
    'dwm.exe', 'explorer.exe', 'ShellHost.exe', 'ShellExperienceHost.exe', 'SearchHost.exe',
    'StartMenuExperienceHost.exe', 'CrossDeviceResume.exe', 'TextInputHost.exe', 'TabTip.exe',
    'Taskmgr.exe', 'LockApp.exe', 'LogonUI.exe', 'ApplicationFrameHost.exe', 'RuntimeBroker.exe',
    'msedgewebview2.exe', 'msedge.exe', 'chrome.exe', 'brave.exe', 'firefox.exe',
    'Discord.exe', 'steamwebhelper.exe', 'steam.exe', 'ms-teams.exe', 'FileWatcher.exe',
    'EdgeGameAssist.exe', 'notepad++.exe', 'ChatGPT.exe', 'codex-computer-use-swift.exe',
    'Riot Client.exe', 'RiotClientServices.exe', 'vgtray.exe', 'WindowsTerminal.exe'))


def check_owners(rows, names, active_compute):
    """WDDM reports GUI contexts as compute-apps with N/A memory. Fail closed for
    unknown owners, measured compute owners, Python/model services, or active compute.
    Desktop allowlisting is an idle heuristic, not a security/process identity boundary.
    """
    if active_compute: raise ValueError('Active GPU compute engine detected; no process was stopped')
    desktop = []
    for row in rows:
        if len(row) != 3: raise ValueError('Cannot interpret GPU ownership report')
        pid, reported, memory = (part.strip() for part in row)
        if not pid.isdigit(): raise ValueError('Cannot identify GPU owner')
        name = names.get(int(pid)) or ntpath.basename(reported)
        if memory not in ('[N/A]', 'N/A', '[Not Supported]') or name.lower() not in DESKTOP_GPU_PROCESSES:
            raise ValueError('GPU compute/unknown owner detected: ' + name + '; no process was stopped')
        desktop.append({'pid': int(pid), 'name': name, 'classification': 'WDDM desktop context; memory unreported'})
    return desktop


def ownership(*, remaining=None, owned_pids=(), evidence=None, context=None):
    """Optional synchronous evidence sink; recording failures also fail closed."""
    timeout = lambda cap: min(cap, remaining()) if remaining else cap
    record={'observation_id':uuid.uuid4().hex,'began_utc':datetime.now(timezone.utc).isoformat(),
        'owned_pids':sorted(set(owned_pids)),'context':context or {}}
    def publish(stage, error=None):
        record.update(stage=stage,recorded_utc=datetime.now(timezone.utc).isoformat())
        if error is not None:record['error']=type(error).__name__+': '+str(error)
        if evidence is not None:evidence(record)
    try:
        record['nvidia_query_began_utc']=datetime.now(timezone.utc).isoformat()
        raw = subprocess.check_output(['nvidia-smi', '--id=0', '--query-compute-apps=pid,process_name,used_gpu_memory',
            '--format=csv,noheader,nounits'], text=True, timeout=timeout(10)).strip()
        record.update(nvidia_query_ended_utc=datetime.now(timezone.utc).isoformat(),nvidia_raw=raw)
        rows = list(csv.reader(raw.splitlines())) if raw and raw != 'No running processes found' else []
        record['nvidia_rows_unfiltered']=rows
        record['cim_query_began_utc']=datetime.now(timezone.utc).isoformat()
        code = ("$ErrorActionPreference='Stop'; $p=@(Get-CimInstance Win32_Process | Select-Object ProcessId,Name,ParentProcessId,CreationDate); "
        "$c=@(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | "
        "Where-Object {$_.Name -match 'engtype_(Compute|CUDA)' -and $_.UtilizationPercentage -gt 0} | "
        "Select-Object Name,UtilizationPercentage); [pscustomobject]@{processes=$p;compute=$c} | ConvertTo-Json -Compress -Depth 4")
        cim_raw=subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', code],
            text=True, timeout=timeout(20))
        record.update(cim_query_ended_utc=datetime.now(timezone.utc).isoformat(),cim_raw=cim_raw)
        value = json.loads(cim_raw);record['processes']=value['processes'];record['compute_unfiltered']=value['compute']
        publish('collected_before_filter')
        names = {int(p['ProcessId']): p['Name'] for p in value['processes']}
        owned=set(owned_pids)
        rows=[r for r in rows if int(r[0].strip()) not in owned]
        compute=[r for r in value['compute'] if not any(r['Name'].startswith('pid_'+str(p)+'_') for p in owned)]
        record.update(nvidia_rows_filtered=rows,compute_filtered=compute)
        publish('before_decision')
        desktop = check_owners(rows, names, compute)
    except BaseException as error:
        publish('rejected_or_query_failed',error)
        raise
    record['desktop_contexts']=desktop;publish('accepted')
    return {'desktop_contexts': desktop, 'active_compute': compute,
        'policy': 'Measured/unknown compute owners blocked; known WDDM desktop contexts separately classified.'}


def snapshot(pids=(), *, timeout=20):
    if not 0 < timeout <= 20: raise ValueError('Invalid host snapshot timeout')
    pattern = '^pid_(' + '|'.join(str(int(pid)) for pid in pids) + ')_' if pids else '(?!)'
    code = ("$o=Get-CimInstance Win32_OperatingSystem; $m=Get-CimInstance Win32_PerfFormattedData_PerfOS_Memory; "
        "$g=@(Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory | Where-Object {$_.Name -match '"
        + pattern + "'}); [pscustomobject]@{free_ram_kib=$o.FreePhysicalMemory; "
        "free_commit_bytes=([long]$m.CommitLimit-[long]$m.CommittedBytes); "
        "gpu=@($g | Select-Object Name,SharedUsage,DedicatedUsage)} | ConvertTo-Json -Compress -Depth 4")
    value = json.loads(subprocess.check_output(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', code], text=True, timeout=timeout))
    if not isinstance(value.get('free_ram_kib'), (int, float)) or not isinstance(value.get('free_commit_bytes'), (int, float)):
        raise ValueError('Host resource counters unavailable; refusing unmonitored training')
    return value


def reason(state, guards, operation_age, charged_seconds, stopped=False, disk_free=None):
    if stopped: return 'operator_stop'
    if state['free_ram_kib'] < guards['minimum_free_host_ram_mib'] * 1024: return 'host_ram_floor'
    if state['free_commit_bytes'] < guards['minimum_commit_headroom_mib'] * 2**20: return 'commit_floor'
    gpu = state.get('gpu') or []
    if isinstance(gpu, dict): gpu = [gpu]
    if sum(int(row.get('SharedUsage', 0)) for row in gpu) > guards['shared_gpu_memory_mib'] * 2**20: return 'shared_gpu_allowance'
    if operation_age > guards['update_seconds']: return 'operation_time_guard'
    if charged_seconds >= guards['full_run_seconds']: return 'cumulative_time_guard'
    if disk_free is not None and disk_free < 3 * 2**30: return 'disk_floor'
    return None


def idle():
    states = []
    for index in range(3):
        raw = subprocess.check_output(['nvidia-smi', '--id=0', '--query-gpu=memory.total,memory.free,utilization.gpu',
            '--format=csv,noheader,nounits'], text=True, timeout=10)
        total, free, utilization = [int(x.strip()) for x in raw.strip().split(',')]
        states.append({'total_mib': total, 'free_mib': free, 'utilization': utilization})
        if free < .9 * total or utilization > 5: raise ValueError('GPU is occupied; no other process was stopped')
        states[-1]['ownership'] = ownership()
        if index != 2: time.sleep(2)
    return states


def start(args):
    if not getattr(args, 'start_training', False) or not getattr(args, 'confirm_gpu_idle', False):
        raise ValueError('Explicit start-training and GPU-idle acknowledgement are required')
    if os.name != 'nt': raise ValueError('This measured 6K training configuration currently supports Windows only')
    from lora6k import MODULES, offline, verify
    run = Path(args.input).resolve()
    with exclusive(run):
        plan, _ = verify(run, full_checkpoint=True)
        for name in MODULES:
            if sha(Path(__file__).parent / name) != plan['code'][name]:
                raise ValueError('Invoke the frozen code/lora6k.py entry point for this run')
        attempts = run / 'attempts'; attempts.mkdir(exist_ok=True)
        previous = list(attempts.iterdir())
        if previous and not args.resume: raise ValueError('Run has prior work; explicitly use --resume')
        if not previous and args.resume: raise ValueError('No prior attempt exists to resume')
        if (run / 'training-result.json').exists(): raise ValueError('Single-epoch pilot is already complete; no additional passes allowed')
        if (run / 'STOP').exists():
            if not args.clear_stop: raise ValueError('STOP is present; explicit --clear-stop is needed when resuming')
            if not args.resume: raise ValueError('Clear STOP only with an explicit resume')
            (run / 'STOP').rename(run / ('STOP-acknowledged-' + uuid.uuid4().hex))
        prior = read(run / 'supervisor.json') if (run / 'supervisor.json').exists() else {}
        charged = prior.get('charged_seconds', 0.)
        # An unclean parent exit has at most one unsampled 5s/20s-counter interval.
        # Charge a conservative tail instead of granting free time on each crash.
        tail = 30 if prior.get('status') in ('running', 'starting') and not prior.get('finished') else 0
        charged += tail
        guards = plan['pilot']['guards']
        if charged >= guards['full_run_seconds']: raise ValueError('Cumulative four-hour allowance exhausted')
        gpu = idle(); initial = snapshot()
        if initial['free_ram_kib'] < 8 * 1024**2: raise ValueError('At least 8 GiB free RAM is required before loading')
        initial_reason = reason(initial, guards, 0, charged, disk_free=shutil.disk_usage(run).free)
        if initial_reason: raise ValueError('Initial resource guard: ' + initial_reason)
        attempt = attempts / ('attempt-%03d' % (len(previous) + 1)); attempt.mkdir()
        token = uuid.uuid4().hex
        atomic(attempt / 'START.json', {'token': token, 'plan_sha256': (run / 'run-plan.sha256').read_text().strip()})
        record = {'status': 'starting', 'attempt': attempt.name, 'pid': os.getpid(), 'charged_seconds': charged,
            'unclean_previous_attempt_tail_charged_seconds': tail,
            'guards': guards, 'initial_gpu': gpu, 'initial_host': initial, 'training_started': False}
        atomic(run / 'supervisor.json', record)
        spec = importlib.util.spec_from_file_location('lora_owned_job', run / 'code/windows_job.py')
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        job = module.Job(vm_limits=False); child = None; tick = time.monotonic(); stopped = None
        try:
            with (attempt / 'worker.log').open('w', encoding='utf-8') as log:
                child = subprocess.Popen([plan['python'], '-X', 'utf8', '-B', '-u', str(run / 'code/lora6k_worker.py'),
                    '--input', str(run), '--attempt', str(attempt), '--supervisor-token', token],
                    stdout=log, stderr=subprocess.STDOUT, env=offline(), cwd=run,
                    creationflags=subprocess.CREATE_NO_WINDOW | 0x4)
                # Start suspended, assign kill-on-close ownership, then resume.
                # This job imposes no VM-specific 3-GiB/CPU/process-count quota.
                job.attach_and_resume(child)
                record.update(status='running', training_started=True, launcher_pid=child.pid)
                while child.poll() is None:
                    progress = read(attempt / 'progress.json') if (attempt / 'progress.json').exists() else {}
                    pids = {child.pid, int(progress.get('pid', child.pid))}
                    state = snapshot(pids)
                    now = time.monotonic(); charged += now - tick; tick = now
                    operation = progress.get('operation_started_at')
                    age = (datetime.now(timezone.utc) - datetime.fromisoformat(operation)).total_seconds() if operation else 0
                    stopped = reason(state, guards, age, charged, disk_free=shutil.disk_usage(run).free)
                    record.update(charged_seconds=charged, progress=progress, stopped=stopped)
                    atomic(run / 'supervisor.json', record)
                    with (attempt / 'resources.jsonl').open('a', encoding='utf-8') as stream:
                        stream.write(json.dumps({'time': datetime.now(timezone.utc).isoformat(), **state}) + '\n')
                    if stopped: break
                    # STOP is graceful: the worker commits an in-flight update before pausing.
                    # Resource/time failures close the job immediately and keep the last complete checkpoint.
                    time.sleep(5)
                if stopped: job.close()
                child.wait(timeout=30)
            result = read(attempt / 'result.json') if (attempt / 'result.json').exists() else {}
            record.update(status='stopped' if stopped else result.get('status', 'worker_failed'),
                returncode=child.returncode, result=result)
        except BaseException as error:
            record.update(status='supervisor_failed', error=type(error).__name__ + ': ' + str(error))
            raise
        finally:
            job.close()
            if child is not None and child.poll() is None:
                child.kill(); child.wait(timeout=30)
            charged += time.monotonic() - tick
            record.update(charged_seconds=charged, owned_worker_closed=child is None or child.poll() is not None,
                finished=datetime.now(timezone.utc).isoformat())
            atomic(run / 'supervisor.json', record); atomic(attempt / 'supervisor-result.json', record)
        print(json.dumps({'status': record['status'], 'attempt': str(attempt), 'charged_seconds': charged}))
        if record['status'] not in ('completed_one_epoch', 'paused'): raise RuntimeError('Training stopped or failed; inspect the saved receipts')
