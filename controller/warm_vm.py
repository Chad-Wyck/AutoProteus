"""Keep one clean, unassigned VM ready for the loaded local model."""
import threading
import time

from .errors import Cancelled, IsolationError


class WarmVM:
    def __init__(self, appliance, factory, lease_factory):
        self.appliance, self.factory, self.lease_factory = appliance, factory, lease_factory
        self.lock = threading.RLock()
        self.slot = None

    def prepare(self):
        with self.lock:
            if self.slot:
                if self.slot['thread'].is_alive() or (self.slot['vm'] and not self.slot['vm'].closed.is_set()):
                    return
                if self.slot['lease']:
                    self.slot['lease'].close()
                self.slot = None
            slot = self.slot = {'cancel':threading.Event(), 'watch_stop':threading.Event(),
                                'vm':None, 'lease':None, 'prepared':False}
            slot['thread'] = threading.Thread(target=self._prepare, args=(slot,), daemon=True)
            slot['thread'].start()

    def _prepare(self, slot):
        vm = lease = None
        try:
            self.appliance.verify()
            deadline = time.monotonic()+90
            lease = self.lease_factory(self.appliance.directory)
            lease.acquire(slot['cancel'], deadline, background=True)
            with self.lock:
                slot['lease']=lease
            slot['watcher']=threading.Thread(target=self._watch,args=(slot,),daemon=True)
            slot['watcher'].start()
            if slot['cancel'].is_set():
                raise Cancelled()
            vm = self.factory(self.appliance)
            if vm.next(slot['cancel'], deadline) != {'op':'ready','protocol':2}:
                raise IsolationError('Guest warm-up handshake failed')
            with self.lock:
                if self.slot is slot and not slot['cancel'].is_set():
                    slot.update(vm=vm, lease=lease, prepared=True)
                    vm = lease = None
        except Exception:
            slot['watch_stop'].set()
            with self.lock:
                if self.slot is slot:
                    self.slot = None
        finally:
            if vm:
                vm.close()
            if lease:
                lease.close()

    def _watch(self,slot):
        while not slot['watch_stop'].wait(.1):
            with self.lock:
                if self.slot is not slot:return
                pending=slot['lease'].request_pending() is True
                if pending and not slot['prepared']:
                    slot['cancel'].set()
                    return
            if pending:
                self._discard(slot)
                return

    def take(self, cancel, deadline):
        with self.lock:
            slot = self.slot
        if not slot:
            return None
        while slot['thread'].is_alive():
            if cancel.is_set():
                self.close()
                raise Cancelled()
            if time.monotonic() >= deadline:
                self.close()
                raise IsolationError('The task deadline expired during VM warm-up')
            slot['thread'].join(timeout=.1)
        with self.lock:
            if self.slot is slot:
                if slot['vm'] and not slot['vm'].closed.is_set() and not slot['lease'].request_pending():
                    self.slot = None
                    slot['watch_stop'].set()
                    return slot
        self._discard(slot)
        return None

    def close(self):
        with self.lock:
            slot=self.slot
        if slot:self._discard(slot)

    def _discard(self,slot):
        with self.lock:
            if self.slot is not slot:return
            self.slot=None
            slot['cancel'].set()
            slot['watch_stop'].set()
            if slot['prepared']:
                try:
                    slot['vm'].close()
                finally:
                    slot['lease'].close()
        slot['thread'].join(timeout=1)

    def public(self):
        with self.lock:
            return {'warming':bool(self.slot and self.slot['thread'].is_alive()),
                    'ready':bool(self.slot and self.slot['vm'] and not self.slot['vm'].closed.is_set())}
