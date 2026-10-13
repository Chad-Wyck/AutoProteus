import io
import json
from types import SimpleNamespace
import unittest

from controller.appliance import Appliance
from controller.isolation import PREFIX, WorkerTransport, vm_command


class TransportTests(unittest.TestCase):
    def test_large_frame_preserves_every_byte_across_partial_writes(self):
        class PartialPipe(io.BytesIO):
            def write(self, value):
                return super().write(value[:31])
        transport = WorkerTransport()
        pipe = PartialPipe()
        transport.process = SimpleNamespace(stdin=pipe)
        value = {'content': 'café 🙂\r\n' * 10000}
        transport.send(value)
        self.assertEqual(json.loads(pipe.getvalue()[len(PREFIX):]), value)

    def test_bridge_is_a_loopback_character_channel_with_no_guest_nic(self):
        from pathlib import Path
        command = vm_command(Appliance(Path(__file__).resolve().parents[1]), 54321)
        bridge = command[command.index('-chardev') + 1]
        self.assertEqual(bridge, 'socket,id=bridge,host=127.0.0.1,port=54321,server=off,nodelay=on')
        self.assertEqual(command[command.index('-nic') + 1], 'none')
        self.assertNotIn('-netdev', command)
