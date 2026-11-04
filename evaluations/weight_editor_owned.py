"""Owned native research worker. Importing this module does not touch the GPU."""
import os
from pathlib import Path
import shutil
import subprocess
import time
import uuid
import ctypes

from lora6k_state import atomic, read
from weight_editor_runtime import Deadline, account_before_grading, alive, completed, require


def process_in_job(job,pid):
    """Prove the reported venv worker belongs to this launcher's kill-on-close job."""
    from ctypes import wintypes as w
    dll=job.dll
    dll.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];dll.OpenProcess.restype=w.HANDLE
    dll.IsProcessInJob.argtypes=[w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)]
    handle=dll.OpenProcess(0x1000,False,pid)
    require(bool(handle),'Cannot inspect reported worker ownership')
    try:
        member=w.BOOL();require(bool(dll.IsProcessInJob(handle,job.handle,ctypes.byref(member))),'Cannot query worker job')
        require(bool(member.value),'Reported worker is outside the owned job')
    finally:dll.CloseHandle(handle)


def await_ownership(folder,token,pid,deadline,*,sleep=time.sleep):
    """The child cannot initialize native inference before the supervisor sees its PID."""
    folder=Path(folder);ack=folder/'OWNERSHIP-ACK.json';end=deadline.child(60)
    while True:
        end.remaining();require(not (folder.parent.parent/'STOP').exists(),'Operator stop during worker handshake')
        if ack.exists():
            value=read(ack);require(value.get('token')==token and value.get('pid')==pid,'Ownership handshake binding mismatch')
            return value
        sleep(min(.05,end.remaining()))


def admission(observe, deadline, *, sleep=time.sleep, clock=time.monotonic, availability_only=False):
    """A single deadline includes idle admission; never launch after it expires."""
    idle, began = 0, clock()
    while idle < 3:
        deadline.remaining()
        sample = observe(min(10, deadline.remaining()))
        deadline.remaining()
        require(sample['free_vram_mib'] >= 8192, 'Admission VRAM floor')
        require(sample['free_ram_kib'] >= 8 * 2**20 and sample['free_commit_bytes'] >= 4 * 2**30, 'Admission RAM/commit floor')
        require(sample['disk_bytes'] >= 20 * 2**30, 'Admission disk floor')
        idle = idle + 1 if availability_only or sample['utilization'] <= 15 else 0
        require(clock() - began < 60, 'No stable idle admission within 60 seconds')
        if idle < 3:
            sleep(min(2, deadline.remaining()))
    deadline.remaining()


def running_guard(sample, progress, now, end, disk):
    if now >= end:
        return 'shared_deadline'
    if any(now >= value for value in progress.get('request_deadlines', {}).values()):
        return 'request_deadline'
    if sample['free_ram_kib'] < 6 * 2**20:
        return 'ram_floor'
    if sample['free_commit_bytes'] < 4 * 2**30:
        return 'commit_floor'
    if sum(row['SharedUsage'] for row in (sample.get('gpu') or [])) > 512 * 2**20:
        return 'shared_gpu'
    if disk < 5 * 2**30:
        return 'disk_floor'
    return None


def launch(root, folder, command, deadline):
    """Caller must hold the study lock. Never retries a stopped/completed phase."""
    from lora6k_supervisor import ownership, snapshot
    # The frozen publication supplies this host-owned helper beside this file.
    try:
        from windows_job import Job
    except ImportError:
        from controller.windows_job import Job
    root, folder = Path(root), Path(folder)
    strict=read(root/'manifest.json').get('overnight',False) if (root/'manifest.json').exists() else False
    from memory_availability_policy import config as memory_config,observe as memory_observe
    memory_policy=memory_config(root) if (root/'manifest.json').exists() else None
    folder.mkdir(exist_ok=False)
    token = uuid.uuid4().hex
    record = {'status': 'admission', 'token': token, 'guard': None}
    started = time.monotonic()
    child = job = None
    failure = None

    def capture_owners(*, remaining, owned_pids=(), context=None):
        def persist(value):
            atomic(folder/'ownership'/(value['observation_id']+'-'+value['stage']+'.json'),value)
        return ownership(remaining=remaining,owned_pids=owned_pids,evidence=persist,
            context={'token':token,'launcher_pid':record.get('launcher_pid'),
                'worker_pid':record.get('worker_pid'),**(context or {})})

    def observe(timeout):
        if memory_policy:
            value=memory_observe(root,folder,deadline.remaining,stage='admission',context={'token':token})
            atomic(folder/'admission.json',value);return value
        raw = subprocess.check_output(['nvidia-smi', '--query-gpu=memory.free,utilization.gpu',
            '--format=csv,noheader,nounits'], text=True, timeout=timeout)
        deadline.remaining()
        capture_owners(remaining=deadline.remaining,context={'phase':'admission'})
        free, percent = [int(value.strip()) for value in raw.split(',')]
        host = snapshot(timeout=min(20, deadline.remaining()))
        value = {**host, 'free_vram_mib': free, 'utilization': percent, 'disk_bytes': shutil.disk_usage(root).free}
        atomic(folder / 'admission.json', value)
        return value

    try:
        admission(observe, deadline,availability_only=bool(memory_policy))
        deadline.remaining(reserve=1)
        job = Job(vm_limits=False)
        env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '0', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
               'TOKENIZERS_PARALLELISM': 'false', 'OMP_NUM_THREADS': '2', 'MKL_NUM_THREADS': '2',
               'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONOPTIMIZE': '0'}
        with (folder / 'stdout.log').open('w', encoding='utf8') as out, (folder / 'stderr.log').open('w', encoding='utf8') as err:
            deadline.remaining()
            child = subprocess.Popen(command + [str(root), str(folder), token, str(deadline.end)],
                stdout=out, stderr=err, cwd=root, env=env,
                creationflags=0x4 | 0x08000000 | subprocess.BELOW_NORMAL_PRIORITY_CLASS)
            record.update(status='running', launcher_pid=child.pid, worker_pid=child.pid)
            job.attach_and_resume(child)
            missing = None
            while child.poll() is None:
                tick = time.monotonic()
                progress = read(folder / 'progress.json') if (folder / 'progress.json').exists() else {}
                if progress.get('token') != token:
                    progress = {}
                pid = int(progress.get('pid', child.pid))
                if strict and progress.get('token')==token:
                    process_in_job(job,pid)
                    ack=folder/'OWNERSHIP-ACK.json'
                    if not ack.exists():atomic(ack,{'token':token,'pid':pid,'launcher_pid':child.pid})
                record['worker_pid'] = pid
                measurement_end = min([deadline.end, *progress.get('request_deadlines', {}).values()])
                measurement_deadline = Deadline(end=measurement_end)
                if memory_policy:
                    sample=memory_observe(root,folder,measurement_deadline.remaining,owned_pids={pid,child.pid},stage='running',
                        context={'token':token,'progress':progress,'launcher_pid':child.pid,'worker_pid':pid})
                else:sample = snapshot({pid, child.pid}, timeout=min(20, measurement_deadline.remaining()))
                if strict and not memory_policy:
                    capture_owners(remaining=measurement_deadline.remaining,owned_pids={pid,child.pid},
                        context={'phase':'running','progress':progress,'resource_sample':sample})
                # Platform sampling time counts against the same deadline.
                now = time.monotonic()
                reason = running_guard(sample, progress, now, deadline.end, shutil.disk_usage(root).free)
                if (root / 'STOP').exists():
                    reason = 'operator_stop'
                if progress.get('gpu_loaded') and not sample.get('gpu'):
                    missing = missing or now
                    if now - missing >= 15:
                        reason = 'gpu_counters_missing'
                else:
                    missing = None
                record.update(progress=progress, latest=sample, guard=reason, seconds=now-started)
                atomic(folder / 'supervisor.json', record)
                if reason:
                    raise RuntimeError('Owned worker stopped: ' + reason)
                time.sleep(max(0, min(5 - (time.monotonic()-tick), deadline.end-time.monotonic())))
            record['returncode'] = child.returncode
            require(child.returncode == 0, 'Nonzero worker exit')
        result = read(folder / 'RESULT.json')
        require(result.get('token') == token and result.get('status') == 'completed'
                and result.get('cleanup_complete') is True, 'Missing matching result')
        record['status'] = 'completed'
    except BaseException as error:
        failure = error
        record.update(status='stopped', error=type(error).__name__ + ': ' + str(error))
    finally:
        cleanup_errors = []
        if job:
            try:
                job.close()
            except Exception as error:
                cleanup_errors.append(str(error))
        if child:
            try:
                if child.poll() is None:
                    child.kill()
                child.wait(timeout=20)
                record['returncode'] = child.returncode
            except Exception as error:
                cleanup_errors.append(str(error))
        try:
            pids = {record.get('launcher_pid'), record.get('worker_pid')} - {None}
            for _ in range(20):
                if not any(alive(pid) for pid in pids):
                    break
                time.sleep(.25)
            record['owned_worker_closed'] = not cleanup_errors and not any(alive(pid) for pid in pids)
        except Exception as error:
            cleanup_errors.append(str(error))
            record['owned_worker_closed'] = False
        record.update(cleanup_errors=cleanup_errors, seconds=time.monotonic()-started)
        atomic(folder / 'CLOSED.json', record)
    if failure:
        raise failure
    # A successful model response cannot escape final closure validation.
    return completed(folder, token=token)


def inference_phase(root, folder, command, deadline, request_path, study_usage, phase, grade):
    """Shared coordinator boundary: reconcile even a failed launch, then grade."""
    from lora6k_state import sha
    request = read(request_path)
    measured = None
    try:
        result = launch(root, folder, command, deadline)
    finally:
        # Failed admission has no generated-token budget; a failed loaded worker
        # can have a reserved crash tail and must be charged before propagating.
        if (Path(folder) / 'usage.json').exists():
            binding = read(Path(folder) / 'usage.json')['binding']
            require(binding['request_sha256'] == sha(request_path), 'Usage/request binding mismatch')
            if (Path(folder) / 'CLOSED.json').exists():
                require(read(Path(folder) / 'CLOSED.json')['token'] == binding['nonce'], 'Usage/closure nonce mismatch')
            measured = account_before_grading(study_usage, phase, folder,
                binding)
    require(result['request_sha256'] == sha(request_path), 'Request identity mismatch')
    require(measured is not None and measured['measurement_complete'] and measured['charged_tokens'] == result['generated_tokens'], 'Usage incomplete')
    require(set(result['responses']) == {c['id'] for c in request['cases']}, 'Incomplete response coverage')
    rows = []
    for case in request['cases']:
        deadline.remaining()
        response = read(Path(folder) / (case['id'] + '.json'))
        require(response['generated_tokens'] == measured['per_case'][case['id']], 'Response/journal count mismatch')
        rows.append(grade(case, response, min(10, deadline.remaining())))
    return rows
