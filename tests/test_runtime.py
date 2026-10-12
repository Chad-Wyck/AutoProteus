import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest

from controller.runtime import LocalRuntime
from test_seed import temporary_directory


@unittest.skipUnless(os.name == 'nt', 'Windows managed model process tree')
class EngineLifecycleTests(unittest.TestCase):
    def test_closing_owned_runtime_ends_runner_children(self):
        from controller.windows_job import Job
        with temporary_directory() as directory:
            path = Path(directory) / 'child.pid'
            runtime = LocalRuntime(Path(directory), None)
            runtime.job = Job(vm_limits=False)
            script = "import pathlib,subprocess,sys,time; child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(60)"
            runtime.process = subprocess.Popen([sys.executable, '-c', script, str(path)],
                                               creationflags=subprocess.CREATE_NO_WINDOW | 0x4)
            handle = None
            dll = ctypes.WinDLL('kernel32', use_last_error=True)
            dll.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            dll.OpenProcess.restype = wintypes.HANDLE
            dll.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            dll.CloseHandle.argtypes = [wintypes.HANDLE]
            try:
                runtime.job.attach_and_resume(runtime.process)
                deadline = time.monotonic() + 5
                while not path.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(path.exists())
                handle = dll.OpenProcess(0x100000, False, int(path.read_text()))
                self.assertTrue(handle)
                self.assertEqual(dll.WaitForSingleObject(handle, 0), 258)
                runtime.close()
                self.assertEqual(dll.WaitForSingleObject(handle, 5000), 0)
                self.assertIsNotNone(runtime.process.poll())
            finally:
                runtime.close()
                if handle:
                    dll.CloseHandle(handle)
