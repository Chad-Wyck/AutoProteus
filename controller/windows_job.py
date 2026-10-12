"""External Windows quotas. Closing this job terminates the VM on host exit."""
import ctypes
from ctypes import wintypes as w


class Basic(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', w.DWORD),
                ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t), ('processes', w.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]


class Extended(ctypes.Structure):
    _fields_ = [('basic', Basic), ('io', ctypes.c_uint64 * 6), ('process_memory', ctypes.c_size_t),
                ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]


class CPU(ctypes.Structure):
    _fields_ = [('flags', w.DWORD), ('rate', w.DWORD)]


class Job:
    def __init__(self):
        self.dll = ctypes.WinDLL('kernel32', use_last_error=True)
        self.dll.CreateJobObjectW.argtypes = [ctypes.c_void_p, w.LPCWSTR]
        self.dll.CreateJobObjectW.restype = w.HANDLE
        self.dll.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        self.dll.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        self.dll.CloseHandle.argtypes = [w.HANDLE]
        self.handle = self.dll.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            limit = Extended()
            # Kill on close, no child processes, bounded host commit for guest RAM + overhead.
            limit.basic.flags = 0x2000 | 0x8 | 0x200
            limit.basic.processes = 1
            limit.job_memory = 3 * 1024**3
            self._check(self.dll.SetInformationJobObject(self.handle, 9, ctypes.byref(limit), ctypes.sizeof(limit)))
            cpu = CPU(1 | 4, 2500)  # hard cap: 25% of host CPU time
            self._check(self.dll.SetInformationJobObject(self.handle, 15, ctypes.byref(cpu), ctypes.sizeof(cpu)))
        except Exception:
            self.close()
            raise

    def _check(self, value):
        if not value:
            raise ctypes.WinError(ctypes.get_last_error())

    def attach_and_resume(self, process):
        self._check(self.dll.AssignProcessToJobObject(self.handle, w.HANDLE(int(process._handle))))
        dll = ctypes.WinDLL('ntdll')
        dll.NtResumeProcess.argtypes = [w.HANDLE]
        dll.NtResumeProcess.restype = ctypes.c_long
        if dll.NtResumeProcess(w.HANDLE(int(process._handle))) != 0:
            raise RuntimeError('Could not start the quota-controlled VM')

    def close(self):
        if self.handle:
            self.dll.CloseHandle(self.handle)
            self.handle = None
