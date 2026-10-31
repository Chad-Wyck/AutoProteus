"""Linux setup boundaries and real managed-process lifecycle checks."""
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import unittest
from unittest.mock import Mock, PropertyMock, patch

from controller.appliance import Appliance
from controller.config import Settings
from controller.errors import IsolationError
from controller.isolation import vm_command
from controller.runtime import LocalRuntime
from controller.storage import atomic_json
from controller import linux_process
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]


def process_exited(pid):
    try:
        state = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return True
    return state in ('Z', 'X')


class LinuxBoundaryTests(unittest.TestCase):
    def test_exit_observation_handles_disappearance_without_hiding_live_processes_or_read_errors(self):
        with patch.object(Path, 'read_text') as read:
            for state in ('S', 'R', 'D'):
                read.return_value = f'123 (fixture) {state} 0 123 0'
                self.assertFalse(process_exited(123))
            for state in ('Z', 'X'):
                read.return_value = f'123 (fixture) {state} 0 123 0'
                self.assertTrue(process_exited(123))
            for error in (FileNotFoundError, ProcessLookupError):
                read.side_effect = error
                self.assertTrue(process_exited(123))
            read.side_effect = PermissionError
            with self.assertRaises(PermissionError):
                process_exited(123)

    def test_group_observation_distinguishes_live_descendants_zombies_and_unrelated_processes(self):
        with temporary_directory() as directory:
            root = Path(directory)
            for pid, state, group in ((1, 'S', 999), (2, 'Z', 1234), (3, 'X', 1234), (4, 'S', 1234)):
                folder = root / str(pid); folder.mkdir()
                (folder / 'stat').write_text(f'{pid} (name with ) parentheses) {state} 0 {group} 0')
            with patch.object(linux_process, 'Path', return_value=root):
                self.assertTrue(linux_process.group_running(1234))
                (root / '4/stat').write_text('4 (finished) Z 0 1234 0')
                self.assertFalse(linux_process.group_running(1234))
                self.assertTrue(linux_process.group_running(999))

    def test_job_close_waits_for_descendants_after_supervisor_exit(self):
        job = linux_process.Job()
        job.descriptor, job.group = 41, 1234
        remaining = iter((True, True, False))
        with patch.object(linux_process.signal, 'pidfd_send_signal', create=True) as send, \
                patch.object(linux_process.select, 'poll', create=True) as poll, \
                patch.object(linux_process.select, 'POLLIN', 1, create=True), \
                patch.object(linux_process, 'group_running', create=True,
                             side_effect=lambda _: next(remaining)) as running, \
                patch.object(linux_process.time, 'sleep') as pause, \
                patch.object(linux_process.os, 'close') as close:
            poll.return_value.poll.return_value = [(41, 1)]
            job.close()
        self.assertEqual(running.call_count, 3, 'Supervisor exit alone must not finish cleanup')
        self.assertEqual(pause.call_count, 2)
        send.assert_called_once_with(41, signal.SIGTERM)
        close.assert_called_once_with(41)
        self.assertIsNone(job.descriptor)

    def test_job_close_reports_a_surviving_group_even_if_supervisor_already_exited(self):
        job = linux_process.Job()
        job.descriptor, job.group = 41, 1234
        with patch.object(linux_process.signal, 'pidfd_send_signal', create=True,
                          side_effect=ProcessLookupError), \
                patch.object(linux_process.select, 'poll', create=True) as poll, \
                patch.object(linux_process.select, 'POLLIN', 1, create=True), \
                patch.object(linux_process, 'group_running', create=True, return_value=True), \
                patch.object(linux_process.time, 'monotonic', side_effect=(0, 6)), \
                patch.object(linux_process.os, 'close') as close:
            poll.return_value.poll.return_value = [(41, 1)]
            with self.assertRaisesRegex(TimeoutError, 'process group did not stop'):
                job.close()
        close.assert_called_once_with(41)
        self.assertIsNone(job.descriptor)

    def test_kvm_command_preserves_no_sharing_policy_and_seccomp(self):
        appliance = Appliance(ROOT)
        with patch.object(Appliance, 'linux', new_callable=PropertyMock, return_value=True), \
                patch.object(appliance, 'binary', return_value=Path('/usr/bin/qemu-system-x86_64')):
            args = vm_command(appliance, 12345)
        self.assertEqual(args[args.index('-accel') + 1], 'kvm')
        self.assertIn('spawn=deny', args[args.index('-sandbox') + 1])
        self.assertEqual(args[args.index('-nic') + 1], 'none')
        self.assertNotIn('tcg', ' '.join(args))
        for flag in ('-drive', '-fsdev', '-virtfs', '-netdev', '-qmp'):
            self.assertNotIn(flag, args)

    def test_linux_runtime_record_rejects_a_changed_qemu_binary(self):
        with temporary_directory() as directory:
            root = Path(directory)
            (root / 'controller').mkdir(); (root / 'guest').mkdir()
            (root / 'controller/runtime-lock.json').write_text('{}')
            (root / 'guest/worker.py').write_text('# trusted worker')
            binary = root / 'qemu-system-x86_64'
            binary.write_bytes(b'original')
            appliance = Appliance(root)
            appliance.directory.mkdir(parents=True)
            sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
            with patch.object(Appliance, 'linux', new_callable=PropertyMock, return_value=True), \
                    patch.object(appliance, 'binary', return_value=binary), \
                    patch('controller.appliance.hypervisor_available', return_value=True):
                atomic_json(appliance.record_path, {'guest_sha256': sha(root / 'guest/worker.py'),
                    'lock_sha256': sha(root / 'controller/runtime-lock.json'), 'qemu_path': str(binary),
                    'qemu_sha256': sha(binary), 'files': {}})
                appliance.verify()
                binary.write_bytes(b'changed')
                with self.assertRaisesRegex(IsolationError, 'QEMU changed'):
                    appliance.verify()
                self.assertFalse(appliance.public()['installed'])

    def test_linux_tar_path_and_link_escapes_are_rejected_before_publication(self):
        for name, link in [('../outside', None), ('bin/link', '../../outside')]:
            with self.subTest(name=name), temporary_directory() as directory:
                root = Path(directory)
                (root / '.runtime').mkdir()
                stream = io.BytesIO()
                with tarfile.open(fileobj=stream, mode='w') as archive:
                    member = tarfile.TarInfo(name)
                    if link:
                        member.type = tarfile.SYMTYPE; member.linkname = link
                    else:
                        member.size = 1
                    archive.addfile(member, None if link else io.BytesIO(b'x'))
                stream.seek(0)
                process = Mock(stdout=stream)
                process.poll.return_value = 0
                runtime = LocalRuntime(root, None)
                with patch('controller.runtime.subprocess.Popen', return_value=process):
                    with self.assertRaises(tarfile.FilterError):
                        runtime._extract_linux(root / 'archive', root / '.runtime/ollama-linux', 1024)
                self.assertFalse((root / '.runtime/ollama-linux').exists())
                self.assertFalse((root / '.runtime/outside').exists())

    def test_verified_runtime_replaces_an_incomplete_cache_only_after_extraction(self):
        with temporary_directory() as directory:
            root = Path(directory)
            target = root / '.runtime/ollama-linux'
            target.mkdir(parents=True)
            (target / 'partial-download').write_bytes(b'incomplete')
            stream = io.BytesIO()
            with tarfile.open(fileobj=stream, mode='w') as archive:
                member = tarfile.TarInfo('bin/ollama')
                member.mode, member.size = 0o755, 6
                archive.addfile(member, io.BytesIO(b'engine'))
            stream.seek(0)
            process = Mock(stdout=stream)
            process.poll.return_value = process.wait.return_value = 0
            with patch('controller.runtime.subprocess.Popen', return_value=process):
                LocalRuntime(root, None)._extract_linux(root / 'archive', target, 1024)
            self.assertEqual((target / 'bin/ollama').read_bytes(), b'engine')
            self.assertFalse((target / 'partial-download').exists())
            backups = list(target.parent.glob('ollama-linux-incomplete-*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / 'partial-download').read_bytes(), b'incomplete')


@unittest.skipUnless(sys.platform == 'linux', 'Linux process and shell checks')
class LinuxLifecycleTests(unittest.TestCase):
    def test_group_restart_preserves_quoted_paths_and_arguments(self):
        function = next(line.strip() for line in (ROOT / 'launch.sh').read_text().splitlines()
                        if line.strip().startswith('task_quote()'))
        value = "AP's folder $(touch unexpected) ; literal $value"
        result = subprocess.run(['sh', '-c', function + '\nsh -c "printf \'%s\' $(task_quote "$1")"',
                                 'test-restart', value], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, value)
        self.assertFalse((ROOT / 'unexpected').exists())

    def test_managed_vm_stop_finishes_before_callers_kill_the_supervisor(self):
        from controller.linux_process import Job, command
        with temporary_directory() as directory:
            script = "import os,time; print(os.getpid(),flush=True); time.sleep(60)"
            process = subprocess.Popen(command(sys.executable, ['-c', script], 'vm'),
                                       start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            job, descriptor = Job(), None
            try:
                job.attach_and_resume(process)
                import select
                self.assertTrue(select.select([process.stdout], [], [], 5)[0], 'The managed VM must start')
                descriptor = os.pidfd_open(int(process.stdout.readline()))
                job.close()
                # The transport's subsequent kill/reap cannot strand the guest.
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=5)
                import select
                poll = select.poll(); poll.register(descriptor, select.POLLIN)
                self.assertTrue(poll.poll(1000), 'The managed VM child survived Stop')
            finally:
                job.close()
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
                process.stderr.close()
                process.stdout.close()
                if descriptor is not None:
                    os.close(descriptor)

    def test_managed_group_stops_after_controller_crash(self):
        with temporary_directory() as directory:
            marker = Path(directory) / 'managed.pid'
            code = (
                'import pathlib,subprocess,sys,time,os,select\n'
                'from controller.linux_process import command\n'
                f'marker=pathlib.Path({str(marker)!r})\n'
                "child=\"import os,time; print(os.getpid(),flush=True); time.sleep(60)\"\n"
                "p=subprocess.Popen(command(sys.executable,['-c',child],'vm'),start_new_session=True,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)\n"
                'assert select.select([p.stdout],[],[],5)[0]\n'
                'marker.write_bytes(p.stdout.readline())\n'
                'os._exit(0)\n')
            subprocess.run([sys.executable, '-c', code], cwd=ROOT, check=True, timeout=10)
            # A zombie has exited; init is responsible for reaping adopted children.
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if process_exited(int(marker.read_text())):
                    break
                time.sleep(.02)
            else:
                self.fail('The managed VM survived the controller crash')

    def test_linux_does_not_decrypt_or_clear_a_windows_saved_key(self):
        with temporary_directory() as directory, patch.dict(os.environ, {'AUTOPROTEUS_API_KEY': ''}):
            root = Path(directory)
            credential = root / 'credential.bin'
            credential.write_bytes(b'windows-encrypted-fixture')
            settings = Settings(root)
            self.assertEqual(settings.key(), '')
            self.assertFalse(settings.public()['has_key'])
            settings.update({'api_key': 'memory-only-test'})
            self.assertEqual(settings.key(), 'memory-only-test')
            settings.update({'clear_key': True})
            self.assertEqual(credential.read_bytes(), b'windows-encrypted-fixture')
            self.assertNotIn('memory-only-test', settings.path.read_text())

    def test_bootstrap_rejects_corrupt_python_before_launching_the_app(self):
        with temporary_directory() as directory:
            root = Path(directory)
            shutil.copy2(ROOT / 'launch.sh', root / 'launch.sh')
            tools = root / 'tools'; tools.mkdir()
            for name, script in {
                'curl': '#!/bin/sh\nwhile [ "$1" != --output ]; do shift; done\nprintf bad-download > "$2"\n',
                'zstd': '#!/bin/sh\nexit 0\n',
                'xdg-open': '#!/bin/sh\nexit 0\n',
            }.items():
                path = tools / name; path.write_text(script); path.chmod(0o755)
            result = subprocess.run(['sh', str(root / 'launch.sh'), '--execution', 'native',
                                     '--acknowledge-host-access', '--no-browser'],
                                    env=dict(os.environ, PATH=str(tools) + ':/usr/bin:/bin'),
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn('integrity check', result.stderr)
            self.assertFalse((root / '.runtime/python-linux').exists())
            self.assertEqual(list((root / '.data').glob('startup-*')), [])

    @unittest.skipUnless(shutil.which('gio'), 'Desktop parser requires GLib desktop tools')
    def test_desktop_entry_launches_from_a_path_with_spaces_and_shell_characters(self):
        import ctypes
        with temporary_directory() as directory:
            root = Path(directory) / "AP's folder $(touch unexpected)"
            root.mkdir()
            entry = root / 'Start AutoProteus.desktop'
            entry.write_text((ROOT / entry.name).read_text().replace('Terminal=true', 'Terminal=false'))
            (root / 'launch.sh').write_text('#!/bin/sh\nprintf "%s" "$0" > "$(dirname -- "$0")/launched"\n')
            # Use the file-manager API. Older `gio launch` creates an anonymous
            # keyfile object and loses the filename needed to expand %k.
            gio = ctypes.CDLL('libgio-2.0.so.0')
            gio.g_desktop_app_info_new_from_filename.argtypes = [ctypes.c_char_p]
            gio.g_desktop_app_info_new_from_filename.restype = ctypes.c_void_p
            gio.g_app_info_launch.argtypes = [ctypes.c_void_p] * 4
            gio.g_app_info_launch.restype = ctypes.c_int
            gio.g_object_unref.argtypes = [ctypes.c_void_p]
            info = gio.g_desktop_app_info_new_from_filename(str(entry).encode())
            self.assertTrue(info)
            try:
                self.assertEqual(gio.g_app_info_launch(info, None, None, None), 1)
            finally:
                gio.g_object_unref(info)
            deadline = time.monotonic() + 5
            while not (root / 'launched').exists() and time.monotonic() < deadline:
                time.sleep(.02)
            self.assertEqual((root / 'launched').read_text(), str(root / 'launch.sh'))
            self.assertFalse((ROOT / 'unexpected').exists())

    def test_managed_engine_survives_setup_thread_and_stop_kills_runner(self):
        from controller.linux_process import Job, command
        with temporary_directory() as directory:
            pidfile = Path(directory) / 'runner.pid'
            script = "import pathlib,subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); path=pathlib.Path(sys.argv[1]); path.with_suffix('.tmp').write_text(str(p.pid)); path.with_suffix('.tmp').rename(path); time.sleep(60)"
            job, processes = Job(), []
            def start():
                p = subprocess.Popen(command(sys.executable, ['-c', script, str(pidfile)], 'engine'),
                                     start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                processes.append(p); job.attach_and_resume(p)
            starter = threading.Thread(target=start)
            starter.start(); starter.join(timeout=5)
            process = processes[0]
            descriptor = None
            try:
                deadline = time.monotonic() + 5
                while not pidfile.exists() and time.monotonic() < deadline:
                    time.sleep(.02)
                self.assertTrue(pidfile.exists())
                time.sleep(.3)
                self.assertIsNone(process.poll(), 'Finishing setup must not kill the service')
                descriptor = os.pidfd_open(int(pidfile.read_text()))
                job.close(); process.wait(timeout=5)
                import select
                poll = select.poll(); poll.register(descriptor, select.POLLIN)
                self.assertTrue(poll.poll(5000), 'The runner must also stop')
            finally:
                job.close()
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
                process.stderr.close()
                if descriptor is not None:
                    os.close(descriptor)

    def test_native_launch_without_acknowledgement_does_not_bootstrap(self):
        result = subprocess.run(['sh', str(ROOT / 'launch.sh'), '--execution', 'native'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Both --execution native', result.stderr)
        self.assertNotIn('Preparing private Python', result.stdout)

    def test_linux_shell_files_are_valid(self):
        for name in ('launch.sh', 'controller/linux_setup.sh'):
            subprocess.run(['sh', '-n', str(ROOT / name)], check=True, capture_output=True)
