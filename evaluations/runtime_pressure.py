"""Host-only pressure observations. No cache clearing or system setting changes."""
import ctypes
import math
import mmap
import os
from pathlib import Path

GIB = 1024**3


class PagingReader:
    def __init__(self):
        self.query = ctypes.c_void_p()
        self.counter = ctypes.c_void_p()
        self.available = False
        if os.name == 'nt':
            self.pdh = ctypes.WinDLL('pdh')
            self.pdh.PdhOpenQueryW.argtypes = [ctypes.c_wchar_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
            self.pdh.PdhAddEnglishCounterW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
            self.pdh.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
            self.pdh.PdhCloseQuery.argtypes = [ctypes.c_void_p]
            self.pdh.PdhGetFormattedCounterValue.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p]
            if self.pdh.PdhOpenQueryW(None, 0, ctypes.byref(self.query)) == 0:
                self.available = (self.pdh.PdhAddEnglishCounterW(self.query, r'\Memory\Pages Input/sec', 0,
                                  ctypes.byref(self.counter)) == 0 and self.pdh.PdhCollectQueryData(self.query) == 0)

    def read(self):
        if os.name != 'nt':
            # PSI measures time all non-idle tasks are stalled on memory. It
            # includes file-backed refault pressure, not just swap traffic.
            try:
                line = next(line for line in Path('/proc/pressure/memory').read_text().splitlines() if line.startswith('full '))
                values = dict(item.split('=') for item in line.split()[1:])
                return {'memory_stall_percent': float(values['avg10']), 'pressure_source': 'linux_memory_psi'}
            except (OSError, ValueError, KeyError, StopIteration):
                return {'pressure_source': 'unavailable'}
        if self.available:
            class Value(ctypes.Structure):
                _fields_ = [('status', ctypes.c_ulong), ('value', ctypes.c_double)]
            value = Value()
            if (self.pdh.PdhCollectQueryData(self.query) == 0 and
                    self.pdh.PdhGetFormattedCounterValue(self.counter, 0x200, None, ctypes.byref(value)) == 0 and
                    value.status in (0, 1) and math.isfinite(value.value) and value.value >= 0):
                return {'page_in_bytes_per_second': value.value*mmap.PAGESIZE, 'pressure_source': 'windows_pages_input'}
        return {'pressure_source': 'unavailable'}

    def close(self):
        if self.query.value:
            self.pdh.PdhCloseQuery(self.query)
            self.query = ctypes.c_void_p()


class PressureGuard:
    """Require sustained low RAM plus paging/stalls; normal cold reads alone pass."""
    def __init__(self, floor=4*GIB, seconds=15):
        self.floor, self.seconds = floor, seconds
        self.since = None

    def observe(self, sample, at):
        low = sample['available_physical'] < self.floor
        paging = sample.get('page_in_bytes_per_second', 0) >= 32*1024**2
        stalled = sample.get('memory_stall_percent', 0) >= 20 or sample.get('health_unresponsive') is True
        if not (low and (paging or stalled)):
            self.since = None
            return None
        if self.since is None:
            self.since = at
        if at-self.since >= self.seconds:
            return 'Sustained host memory pressure (low RAM with paging or stalls); owned inference stopped'
        return None
