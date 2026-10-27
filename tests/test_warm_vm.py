import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock

from controller.errors import Cancelled
from controller.warm_vm import WarmVM


class WarmVMTests(unittest.TestCase):
    def setUp(self):
        self.appliance = Mock(directory=Path('.'))
        self.vm, self.lease = Mock(), Mock()
        self.lease.request_pending.return_value=False
        self.vm.closed = threading.Event()
        self.vm.next.return_value = {'op':'ready','protocol':2}
        self.vm.close.side_effect = self.vm.closed.set
        self.factory, self.leases = Mock(return_value=self.vm), Mock(return_value=self.lease)
        self.warm = WarmVM(self.appliance, self.factory, self.leases)
        self.addCleanup(self.warm.close)

    def wait(self):
        self.warm.slot['thread'].join(timeout=2)

    def test_model_readiness_boots_once_and_first_task_adopts_that_same_vm(self):
        self.warm.prepare(); self.wait(); self.warm.prepare()
        self.factory.assert_called_once()
        self.assertTrue(self.warm.public()['ready'])
        slot = self.warm.take(threading.Event(), time.monotonic()+2)
        self.assertIs(slot['vm'], self.vm)
        self.vm.next.assert_called_once()
        self.assertFalse(self.warm.public()['ready'])
        self.vm.close.assert_not_called()
        slot['vm'].close(); slot['lease'].close()

    def test_unload_closes_an_unassigned_vm_and_releases_the_exclusive_lease(self):
        self.warm.prepare(); self.wait(); self.warm.close()
        self.vm.close.assert_called_once(); self.lease.close.assert_called_once()
        self.assertFalse(self.warm.public()['ready'])

    def test_unload_during_warmup_leaves_no_vm_or_lease_behind(self):
        started = threading.Event()
        def handshake(cancel, deadline):
            started.set()
            cancel.wait(2)
            raise Cancelled()
        self.vm.next.side_effect = handshake
        self.warm.prepare(); self.assertTrue(started.wait(2))
        self.warm.close()
        self.vm.close.assert_called_once(); self.lease.close.assert_called_once()

    def test_foreground_demand_cancels_an_incomplete_warmup(self):
        started=threading.Event()
        def handshake(cancel,deadline):
            started.set();cancel.wait(2);raise Cancelled()
        self.vm.next.side_effect=handshake
        self.warm.prepare();slot=self.warm.slot;self.assertTrue(started.wait(2))
        self.lease.request_pending.return_value=True
        slot['thread'].join(timeout=3)
        self.assertTrue(slot['cancel'].is_set())
        self.assertFalse(slot['thread'].is_alive());self.assertFalse(self.warm.public()['ready'])
        self.vm.close.assert_called_once();self.lease.close.assert_called_once()
