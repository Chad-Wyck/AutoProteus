"""Research-only diskless VM. Guest Python has no host execution interface."""
import ctypes
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import threading
import time
import traceback

from controller.appliance import Appliance
from controller.isolation import vm_command
from controller.transport import WorkerTransport, PREFIX, MAX_FRAME
from controller.vm_lease import VMLease
from controller.windows_job import Job, Extended, CPU
from lora6k_state import read, sha, atomic
from weight_editor_runtime import require
from tensor_workspace_errors import InfrastructureStop, GlobalDeadlineStop, CellAllowanceExceeded


class TensorVM(WorkerTransport):
    def __init__(self,project,image,receipt,deadline,*,debug_console=None,bridge_seconds=15,readiness_seconds=60):
        super().__init__();self.bridge=None;self.lease=VMLease(Path(project)/'.runtime/isolation')
        self.receipt=Path(receipt);self.counter=0;self.cancel=threading.Event();self.deadline=deadline
        self.record={'status':'starting','cells':0,'isolation':'diskless VM; no NIC, mounts or guest host-code execution'}
        self.startup_began=time.monotonic();self.record['startup_trace']=[]
        self.record.update(bridge_seconds=bridge_seconds,readiness_seconds=readiness_seconds)
        self.stamp('constructor_begin')
        try:
            require(bridge_seconds in (15,30) and readiness_seconds==60,'Unsupported bounded startup timeout')
            require(os.name=='nt','This pinned research VM currently requires Windows WHPX')
            require(sha(image['image'])==image['image_sha256'] and sha(image['kernel'])==image['kernel_sha256'],'Research VM image changed')
            appliance=Appliance(project)
            self.stamp('image_verified')
            self.stamp('lease_requested')
            self.lease.acquire(self.cancel,min(deadline.end,time.monotonic()+30))
            self.stamp('lease_acquired')
            self.job=Job(vm_limits=False);limit=Extended();limit.basic.flags=0x2000|0x8|0x200
            limit.basic.processes=1;limit.job_memory=3*1024**3
            self.job._check(self.job.dll.SetInformationJobObject(self.job.handle,9,ctypes.byref(limit),ctypes.sizeof(limit)))
            cpu=CPU(1|4,2500);self.job._check(self.job.dll.SetInformationJobObject(self.job.handle,15,ctypes.byref(cpu),ctypes.sizeof(cpu)))
            with socket.socket() as listener:
                listener.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                listener.bind(('127.0.0.1',0));listener.listen(1);listener.settimeout(min(bridge_seconds,deadline.remaining()))
                self.stamp('bridge_listener_ready',port=listener.getsockname()[1])
                command=vm_command(appliance,listener.getsockname()[1])
                # QEMU's default virtual CPU predates the pinned NumPy x86-v2 baseline.
                command.extend(['-cpu','Nehalem'])
                command[command.index('-m')+1]='2048';command[command.index('-initrd')+1]=image['image']
                if debug_console:command[command.index('-serial')+1]='file:'+str(Path(debug_console).resolve())
                self.record['command']=command
                env={k:v for k,v in os.environ.items() if k.upper() in ('SYSTEMROOT','WINDIR','TEMP','TMP')}
                self.process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
                    cwd=appliance.directory,env=env,creationflags=0x4|subprocess.CREATE_NO_WINDOW)
                self.record['pid']=self.process.pid;self.stamp('process_created_suspended',pid=self.process.pid)
                self.job.attach_and_resume(self.process);self.stamp('process_resumed',pid=self.process.pid)
                self.stamp('bridge_wait_started',timeout_seconds=min(bridge_seconds,deadline.remaining()))
                self.bridge,_=listener.accept()
                self.stamp('bridge_connected')
            self.bridge.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            self.process.stdin=self.bridge.makefile('wb',buffering=0);self.process.stdout=self.bridge.makefile('rb');self.start_readers()
            self.stamp('readiness_wait_started')
            ready=self.next(self.cancel,min(deadline.end,time.monotonic()+readiness_seconds))
            require(ready=={'op':'ready','uid':1000,'numpy':'2.4.6','persistent':True},'Research kernel readiness mismatch')
            self.record.update(status='ready',ready=ready);self.stamp('kernel_ready')
        except BaseException as error:
            self.record['error']=type(error).__name__+': '+str(error)
            self.record['startup_traceback']=traceback.format_exc()[-16000:]
            self.stamp('startup_error',process_alive=bool(self.process and self.process.poll() is None))
            if self.process and self.process.poll() is not None:
                self.record['startup_stderr']=self.process.stderr.read(64000).decode(errors='replace')
            self.close();raise

    def stamp(self,stage,**fields):
        self.record['startup_trace'].append({'stage':stage,'unix':time.time(),
            'elapsed_seconds':time.monotonic()-self.startup_began,**fields})
        atomic(self.receipt,self.record)

    def _read(self):
        try:
            while not self.closed.is_set():
                raw=self.process.stdout.readline(MAX_FRAME+1);self.output_bytes+=len(raw)
                require(raw and len(raw)<=MAX_FRAME and self.output_bytes<=3*1024**3,'VM wire quota/EOF')
                require(raw.startswith(PREFIX),'Invalid guest frame')
                value=json.loads(raw[len(PREFIX):]);require(isinstance(value,dict),'Invalid guest message')
                while not self.closed.is_set():
                    try:self.frames.put(value,timeout=.1);break
                    except queue.Full:pass
        except Exception as error:
            try:self.frames.put(error,timeout=.1)
            except queue.Full:self.close()

    def execute(self,code,policy,*,seconds=60):
        require(isinstance(code,str) and len(code.encode())<=64000,'Cell source limit')
        require(not self.closed.is_set(),'Kernel is closed');self.counter+=1;cell=self.counter
        end=min(self.deadline.end,time.monotonic()+seconds);seen=set()
        try:
            self.send({'op':'execute','cell':cell,'code':code})
            while True:
                frame=self.next(self.cancel,end)
                require(frame.get('cell')==cell,'Guest cell mismatch')
                if frame.get('op')=='cell_result':
                    require(set(frame)=={'op','cell','output','error'} and isinstance(frame['output'],str) and len(frame['output'])<=12030
                        and (frame['error'] is None or isinstance(frame['error'],str) and len(frame['error'])<=4000),'Invalid cell result')
                    # Cell completion is diagnostic only. It grants no correctness or host permissions.
                    self.record.update(status='ready',cells=cell);atomic(self.receipt,self.record);return frame
                require(set(frame)=={'op','cell','id','request'} and frame['op']=='rpc' and type(frame['id']) is int
                    and frame['id'] not in seen and len(seen)<20000,'Invalid/repeated guest RPC');seen.add(frame['id'])
                request=frame['request'];started=time.monotonic()
                try:value=policy.handle(request);reply={'value':value}
                except Exception as error:reply={'error':type(error).__name__+': '+str(error)[:1200]}
                # Only trusted, bounded inference may suspend the cell CPU wall allowance.
                if isinstance(request,dict) and request.get('op')=='forward':end=min(self.deadline.end,end+time.monotonic()-started)
                self.send({'op':'rpc_result','cell':cell,'id':frame['id'],**reply})
        except BaseException as error:
            expired=time.monotonic()
            self.close()
            if isinstance(error,InfrastructureStop):raise
            if expired>=self.deadline.end:raise GlobalDeadlineStop('Study deadline expired during cell') from error
            if expired>=end:raise CellAllowanceExceeded('Model cell exceeded CPU-wall allowance') from error
            raise InfrastructureStop('Guest transport/protocol failure: '+type(error).__name__+': '+str(error)) from error

    def cleanup(self):
        if self.bridge:self.bridge.close()
        self.lease.close()
        if hasattr(self,'startup_began'):self.stamp('lease_released',process_closed=self.process is None or self.process.poll() is not None)
        self.record.update(status='closed',cells=self.counter,owned_vm_closed=self.process is None or self.process.poll() is not None,
            returncode=None if self.process is None else self.process.returncode,stderr=self.stderr.decode(errors='replace')[-8000:])
        atomic(self.receipt,self.record)
