import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
import unittest
from unittest.mock import PropertyMock, patch

from controller.appliance import Appliance, build_initrd
from controller.errors import IsolationError
from test_seed import temporary_directory


def archive(files):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode='w') as stream:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            stream.addfile(member, io.BytesIO(content))
    return gzip.compress(raw.getvalue())


class ApplianceBuildTests(unittest.TestCase):
    def fixture(self, directory, kernel=True):
        root = Path(directory)
        for name in ('controller', 'guest', 'cache', 'output'):
            (root / name).mkdir()
        (root / 'guest/worker.py').write_text('# trusted fixture')
        files = {'rootfs.tar.gz': archive({'etc/fixture': b'base'}),
                 'linux-virt.apk': archive({'boot/vmlinuz-virt': b'pinned kernel'} if kernel else {})}
        for name, raw in files.items():
            (root / 'cache' / name).write_bytes(raw)
        sources = [{'name': name, 'sha256': hashlib.sha256(raw).hexdigest()} for name, raw in files.items()]
        (root / 'controller/runtime-lock.json').write_text(json.dumps({'sources': sources}))
        return root

    def test_build_uses_only_verified_manifest_archives_and_bundled_kernel(self):
        with temporary_directory() as directory:
            root = self.fixture(directory)
            (root / 'cache/extra.apk').write_bytes(archive({'unexpected-code': b'never include'}))
            build_initrd(root, root / 'cache', root / 'output/initrd.gz')
            self.assertEqual((root / 'output/vmlinuz').read_bytes(), b'pinned kernel')
            image = gzip.decompress((root / 'output/initrd.gz').read_bytes())
            self.assertIn(b'guest.py', image)
            self.assertNotIn(b'unexpected-code', image)

    def test_tampered_archive_and_missing_kernel_fail_closed(self):
        for tamper in (True, False):
            with self.subTest(tamper=tamper), temporary_directory() as directory:
                root = self.fixture(directory, kernel=tamper)
                if tamper:
                    (root / 'cache/rootfs.tar.gz').write_bytes(b'corrupted')
                with self.assertRaises(IsolationError):
                    build_initrd(root, root / 'cache', root / 'output/initrd.gz')
                self.assertFalse((root / 'output/initrd.gz').exists())

    def test_empty_cache_download_rejects_wrong_hash_before_installation(self):
        for linux in (False, True):
            with self.subTest(linux=linux), temporary_directory() as directory:
                root = self.fixture(directory)
                (root / 'controller/runtime-lock.json').write_text(json.dumps({'sources': [
                    {'name': 'rootfs.tar.gz', 'url': 'https://example.invalid/pinned', 'sha256': '0' * 64}]}))
                appliance = Appliance(root)
                # This unit test targets checksum rejection, independent of the
                # runner's QEMU installation or operating system.
                with patch.object(Appliance, 'linux', new_callable=PropertyMock, return_value=linux), \
                        patch.object(appliance, 'binary', return_value=root / 'qemu-fixture') as binary, \
                        patch('controller.appliance.urllib.request.urlopen', return_value=io.BytesIO(b'wrong bytes')) as download, \
                        patch('controller.appliance.build_initrd') as build, \
                        patch.object(appliance, '_install_windows') as install_windows:
                    with self.assertRaisesRegex(IsolationError, 'integrity check'):
                        appliance.install()
                    download.assert_called_once_with('https://example.invalid/pinned', timeout=60)
                    self.assertEqual(binary.call_count, int(linux))
                    build.assert_not_called()
                    install_windows.assert_not_called()
                    self.assertFalse(appliance.record_path.exists())
                self.assertFalse((appliance.cache / 'rootfs.tar.gz').exists())
                self.assertFalse((appliance.cache / 'rootfs.tar.download').exists())

    def test_release_lock_has_no_unused_index_or_mutable_netboot_kernel(self):
        root = Path(__file__).resolve().parents[1]
        sources = json.loads((root / 'controller/runtime-lock.json').read_text())['sources']
        self.assertNotIn('APKINDEX.tar.gz', [item['name'] for item in sources])
        self.assertNotIn('vmlinuz-virt', [item['name'] for item in sources])


if __name__ == '__main__':
    unittest.main()
