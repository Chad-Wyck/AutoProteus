"""Real process locks and fake VM transport: no hypervisor or model required."""
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
import unittest
from unittest.mock import Mock

from controller.vm_lease import VMLease
from controller.warm_vm import WarmVM
from test_seed import temporary_directory

ROOT=Path(__file__).resolve().parents[1]
CHILD='''import sys,threading,time
sys.path.insert(0,sys.argv[3])
from controller.vm_lease import VMLease
from controller.errors import IsolationError
lease=VMLease(sys.argv[1])
try:
 lease.acquire(threading.Event(),time.monotonic()+float(sys.argv[2]),lambda:print('waiting',flush=True))
 print('acquired',flush=True)
 sys.stdin.readline()
except IsolationError:print('expired',flush=True)
finally:lease.close()
'''


class VMLeaseTests(unittest.TestCase):
    def child(self,root,timeout=5):
        proc=subprocess.Popen([sys.executable,'-u','-c',CHILD,str(root),str(timeout),str(ROOT)],cwd=ROOT,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        lines=queue.Queue()
        def read():
            for line in proc.stdout:lines.put(line.strip())
        thread=threading.Thread(target=read,daemon=True);thread.start()
        def cleanup():
            if proc.poll() is None:proc.stdin.write('release\n');proc.stdin.flush()
            try:proc.wait(timeout=6)
            except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=3)
            thread.join(timeout=1)
            for stream in (proc.stdin,proc.stdout,proc.stderr):stream.close()
        self.addCleanup(cleanup)
        return proc,lines

    def cache(self,root):
        def make(_):
            vm=Mock();vm.closed=threading.Event();vm.close.side_effect=vm.closed.set
            vm.next.return_value={'op':'ready','protocol':2}
            return vm
        factory=Mock(side_effect=make)
        warm=WarmVM(Mock(directory=root),factory,VMLease);self.addCleanup(warm.close)
        warm.prepare();slot=warm.slot;slot['thread'].join(timeout=3)
        self.assertTrue(warm.public()['ready'])
        return warm,slot,factory

    def test_foreground_process_reclaims_idle_cache_and_blocks_rewarming_until_done(self):
        root=Path(self.enterContext(temporary_directory()));warm,slot,factory=self.cache(root)
        proc,lines=self.child(root)
        first=lines.get(timeout=5)
        if first=='waiting':first=lines.get(timeout=5)
        self.assertEqual(first,'acquired')
        self.assertTrue(slot['vm'].closed.is_set());self.assertFalse(warm.public()['ready'])
        warm.prepare();pending=warm.slot
        if pending:pending['thread'].join(timeout=2)
        self.assertEqual(factory.call_count,1)  # No cache can jump ahead of actual work.
        proc.stdin.write('release\n');proc.stdin.flush();proc.wait(timeout=3)
        warm.prepare();pending=warm.slot;pending['thread'].join(timeout=2)
        self.assertTrue(warm.public()['ready']);self.assertEqual(factory.call_count,2)

    def test_adopted_vm_is_never_preempted(self):
        root=Path(self.enterContext(temporary_directory()));warm,slot,_=self.cache(root)
        owned=warm.take(threading.Event(),time.monotonic()+3)
        self.addCleanup(slot['lease'].close);self.addCleanup(slot['vm'].close)
        self.assertIs(owned,slot)
        proc,lines=self.child(root)
        self.assertEqual(lines.get(timeout=5),'waiting')
        time.sleep(.2);self.assertFalse(slot['vm'].closed.is_set())
        self.assertIsNone(proc.poll())
        slot['vm'].close();slot['lease'].close()
        self.assertEqual(lines.get(timeout=5),'acquired')

    def test_expired_request_does_not_leave_a_stale_priority_signal(self):
        root=Path(self.enterContext(temporary_directory()));lease=VMLease(root)
        lease.acquire(threading.Event(),time.monotonic()+2);self.addCleanup(lease.close)
        proc,lines=self.child(root,.3)
        self.assertEqual(lines.get(timeout=5),'waiting')
        self.assertEqual(lines.get(timeout=5),'expired');proc.wait(timeout=3)
        self.assertFalse(lease.request_pending())
