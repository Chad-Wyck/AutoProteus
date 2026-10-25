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
            slot = self.slot = {'cancel':threading.Event(), 'vm':None, 'lease':None}
            slot['thread'] = threading.Thread(target=self._prepare, args=(slot,), daemon=True)
            slot['thread'].start()

    def _prepare(self, slot):
        vm = lease = None
        try:
            self.appliance.verify()
            deadline = time.monotonic()+90
            lease = self.lease_factory(self.appliance.directory)
            lease.acquire(slot['cancel'], deadline)
            if slot['cancel'].is_set():
                raise Cancelled()
            vm = self.factory(self.appliance)
            if vm.next(slot['cancel'], deadline) != {'op':'ready','protocol':2}:
                raise IsolationError('Guest warm-up handshake failed')
            with self.lock:
                if self.slot is slot and not slot['cancel'].is_set():
                    slot.update(vm=vm, lease=lease)
                    vm = lease = None
        except Exception:
            with self.lock:
                if self.slot is slot:
                    self.slot = None
        finally:
            if vm:
                vm.close()
            if lease:
                lease.close()

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
                self.slot = None
                if slot['vm'] and not slot['vm'].closed.is_set():
                    return slot
                if slot['lease']:
                    slot['lease'].close()
        return None

    def close(self):
        with self.lock:
            slot, self.slot = self.slot, None
            if not slot:
                return
            slot['cancel'].set()
            if slot['vm']:
                try:
                    slot['vm'].close()
                finally:
                    slot['lease'].close()
        slot['thread'].join(timeout=1)

    def public(self):
        with self.lock:
            return {'warming':bool(self.slot and self.slot['thread'].is_alive()),
                    'ready':bool(self.slot and self.slot['vm'] and not self.slot['vm'].closed.is_set())}
