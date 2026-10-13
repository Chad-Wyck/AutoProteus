"""Native mode consent and honest labeling; Linux cases use trusted offline fixtures."""
import argparse
import base64
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

from app import existing_instance
from controller.config import Settings
from controller.execution import ExecutionPolicy, add_execution_arguments, execution_from_args
from controller.evaluation import EvaluationService, freeze_source, run_regressions
from controller.isolation import Artifacts, Broker, IsolatedAgent, seed_files, VMLease
from controller.native import NativeWorker
from controller.server import Application, make_server
from controller.storage import Store
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]


class PolicyTests(unittest.TestCase):
    def test_vm_is_default_and_native_needs_acknowledgement_even_on_linux(self):
        parser = argparse.ArgumentParser()
        add_execution_arguments(parser)
        self.assertEqual(execution_from_args(parser, parser.parse_args([])).mode, 'vm')
        with patch('controller.execution.sys.platform', 'linux'), self.assertRaisesRegex(ValueError, 'acknowledge'):
            ExecutionPolicy('native')
        with self.assertRaises(ValueError):
            ExecutionPolicy('vm', True)
        with patch('controller.execution.sys.platform', 'win32'), self.assertRaisesRegex(ValueError, 'Linux only'):
            ExecutionPolicy('native', True)

    def test_native_policy_is_fixed_and_settings_cannot_choose_it(self):
        with temporary_directory() as directory:
            settings = Settings(Path(directory))
            settings.update({'execution_mode':'native', 'acknowledge_host_access':True})
            store = Store(Path(directory) / 'sessions')
            self.assertEqual(IsolatedAgent(ROOT, store, settings).execution.mode, 'vm')
        with patch('controller.execution.sys.platform', 'linux'):
            policy = ExecutionPolicy('native', True)
        with self.assertRaises(AttributeError):
            policy.mode = 'vm'
        with patch('controller.native.subprocess.Popen') as process, self.assertRaises(ValueError):
            NativeWorker(ROOT, ExecutionPolicy())
        process.assert_not_called()

    def test_existing_instance_cannot_silently_reuse_another_execution_mode(self):
        with temporary_directory() as directory:
            path = Path(directory) / 'server.json'
            path.write_text(json.dumps({'url':'http://127.0.0.1:1'}))
            response = io.BytesIO(json.dumps({'identity':'test', 'execution_mode':'native',
                                            'isolation_required':False}).encode())
            with patch('app.urllib.request.urlopen', return_value=response), self.assertRaisesRegex(RuntimeError, 'different execution mode'):
                existing_instance(path, 'test', True)

    def test_broker_does_not_accept_seed_changes_to_execution_metadata(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            session = store.create('task', 'demo', 'test')
            session.update(execution_mode='vm', isolation=True)
            frame = {'op':'state', 'session':{**session, 'execution_mode':'native', 'isolation':False}}
            broker = Broker(store, session, None, {'max_steps':4}, threading.Event())
            broker.handle(frame)
            self.assertEqual(session['execution_mode'], 'vm')
            self.assertTrue(session['isolation'])

    def test_seed_prompt_describes_native_permissions_in_both_model_protocols(self):
        from autoproteus.agent import Agent
        with temporary_directory() as directory:
            settings = Settings(Path(directory))
            store = Store(Path(directory) / 'sessions')
            session = store.create('task', 'hosted', 'test')
            session['execution_mode'] = 'native'
            agent = Agent(ROOT, store, settings, None)
            for protocol in ('native', 'json'):
                config = {**settings.values, 'provider':'hosted', 'protocol':protocol}
                prompt = agent.messages(session, config)[0]['content']
                self.assertIn('no AutoProteus VM protection', prompt)
                self.assertNotIn('Host files and the controller are unavailable', prompt)

    def test_browser_settings_cannot_switch_the_launched_mode(self):
        with temporary_directory() as directory:
            app = Application(ROOT, data=Path(directory))
            server = make_server(app, 0)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            url = 'http://127.0.0.1:' + str(server.server_port)
            try:
                headers = {'Content-Type':'application/json', 'X-AutoProteus-Token':app.token}
                with self.assertRaises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(urllib.request.Request(url + '/api/settings',
                        data=b'{"execution_mode":"native","acknowledge_host_access":true}', headers=headers), timeout=5)
                self.assertEqual(error.exception.code, 400)
                with urllib.request.urlopen(url + '/health', timeout=5) as response:
                    health = json.load(response)
                self.assertEqual(health['execution_mode'], 'vm')
                self.assertTrue(health['isolation_required'])
            finally:
                app.close(); server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_native_comparison_preserves_policy_and_qualifies_results(self):
        with temporary_directory() as directory, patch('controller.execution.sys.platform', 'linux'):
            directory = Path(directory)
            settings = Settings(directory)
            settings.values.update(provider='hosted', model='offline', configured=True)
            store = Store(directory / 'sessions')
            source = freeze_source(store, seed_files(ROOT), 'candidate')
            policy = ExecutionPolicy('native', True)
            task_agent = IsolatedAgent(ROOT, store, settings, execution=policy)
            service = EvaluationService(ROOT, directory / 'evaluations', settings, task_agent)
            visited = []
            def task(agent, *args, **kwargs):
                visited.append(agent.execution)
                return {'task':'fixture', 'session':'f'*32, 'status':'completed', 'passed':True,
                        'checks':[], 'steps':1, 'seconds':0, 'format_repairs':0, 'action_errors':0}
            with patch('controller.evaluation.run_task', side_effect=task), \
                    patch('controller.evaluation.run_regressions', return_value={'passed':True, 'tests':23}) as regressions:
                report = service.start(source, repeats=1)
                service.thread.join(timeout=10)
                final = service.load(report['id'])
                self.assertEqual(final['status'], 'completed')
                self.assertTrue(visited)
                self.assertTrue(all(execution is policy for execution in visited))
                self.assertTrue(all(call.kwargs['execution'] is policy for call in regressions.call_args_list))
                self.assertEqual(final['execution_mode'], 'native')
                self.assertFalse(final['isolated'])
                self.assertFalse(final['checks_protected'])
                self.assertIsNone(final['runtime_sha256'])
                self.assertIn('not protected', final['scope'])
            service.close()


@unittest.skipUnless(sys.platform == 'linux', 'Linux native worker integration')
class NativeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = temporary_directory()
        self.directory = Path(self.temp.name)
        self.settings = Settings(self.directory)
        self.settings.values.update(provider='demo', model='scripted-demo', configured=True)
        self.store = Store(self.directory / 'sessions')
        self.execution = ExecutionPolicy('native', True)
        self.agent = IsolatedAgent(ROOT, self.store, self.settings, execution=self.execution)

    def tearDown(self):
        self.agent.close()
        self.temp.cleanup()

    def wait(self, session):
        self.agent.workers[session['id']][1].join(timeout=20)
        self.assertFalse(self.agent.workers[session['id']][1].is_alive(), session['activity'])

    def test_demo_exports_resume_and_persists_native_mode_history(self):
        session = self.store.create('demo', 'demo', 'scripted-demo')
        with patch('controller.isolation.VM') as vm:
            self.agent.start(session)
            self.wait(session)
            vm.assert_not_called()
        self.assertEqual(session['status'], 'completed', session['feed'])
        self.assertFalse(session['isolation'])
        self.assertEqual(session['execution_mode'], 'native')
        artifacts = Artifacts(self.store, session)
        self.assertIn(b'Hello from AutoProteus', artifacts.read('welcome.md'))
        artifacts.put('restored.txt', base64.b64encode(b'saved checkpoint').decode())
        artifacts.checkpoint([*session['artifacts'], 'restored.txt'])
        self.agent.start(session, 'Continue')
        self.wait(session)
        self.assertEqual(Artifacts(self.store, session).read('restored.txt'), b'saved checkpoint')
        self.assertEqual([run['mode'] for run in session['execution_history']], ['native', 'native'])
        saved = Store(self.store.root).get(session['id'])
        self.assertEqual(saved['execution_mode'], 'native')

    def test_unchanged_seed_regressions_are_functional_and_explicitly_unprotected(self):
        source = freeze_source(self.store, seed_files(ROOT), 'starter')
        result = run_regressions(ROOT, self.store, source, execution=self.execution)
        self.assertTrue(result['passed'], result['output'])
        self.assertEqual(result['tests'], 23)
        self.assertEqual(result['execution_mode'], 'native')
        self.assertFalse(result['checks_protected'])
        self.assertFalse(result['isolated'])

    def test_native_web_launch_readiness_and_saved_artifacts_without_vm_setup(self):
        app = Application(ROOT, data=self.directory / 'web', execution=self.execution)
        app.settings.values.update(provider='demo', model='scripted-demo', configured=True)
        server = make_server(app, 0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = 'http://127.0.0.1:' + str(server.server_port)
        headers = {'Content-Type':'application/json', 'X-AutoProteus-Token':app.token}
        try:
            with urllib.request.urlopen(url + '/health', timeout=5) as response:
                self.assertEqual(json.load(response)['execution_mode'], 'native')
            with urllib.request.urlopen(urllib.request.Request(url + '/api/state', headers=headers), timeout=5) as response:
                state = json.load(response)
            self.assertTrue(state['isolation']['ready'])
            self.assertFalse(state['execution']['isolated'])
            self.assertIn('controller', state['execution']['warning'])
            with urllib.request.urlopen(urllib.request.Request(url + '/api/start',
                data=b'{"task":"scripted native web test","execution_mode":"vm"}', headers=headers), timeout=5) as response:
                session_id = json.load(response)['id']
            app.agent.workers[session_id][1].join(timeout=20)
            session = app.store.get(session_id)
            self.assertEqual(session['status'], 'completed', session['feed'])
            self.assertEqual(session['execution_mode'], 'native')
            self.assertIn(b'Hello from AutoProteus', Artifacts(app.store, session).read('welcome.md'))
        finally:
            app.close(); server.shutdown(); server.server_close(); thread.join(timeout=5)

    def test_stop_reaches_an_ordinary_child_in_its_own_process_group(self):
        source = seed_files(ROOT)
        code = ("import subprocess, sys, time\n"
                "subprocess.Popen([sys.executable, '-c', \"import os,time,pathlib; pathlib.Path('child.pid').write_text(str(os.getpid())); time.sleep(120)\"], start_new_session=True)\n"
                "while True: time.sleep(1)\n")
        source = [{**item, 'data':base64.b64encode(code.encode()).decode()} if item['path'] == 'seed.py' else item for item in source]
        frozen = freeze_source(self.store, source, 'trusted stop fixture')
        session = self.store.create('stop', 'demo', 'test')
        self.agent.start(session, candidate=frozen)
        deadline, pid, worker = time.monotonic() + 10, None, None
        while time.monotonic() < deadline:
            worker = self.agent.vms.get(session['id'])
            path = worker.workspace / 'task/child.pid' if worker else None
            if path and path.exists():
                try:
                    pid = int(path.read_text()); break
                except ValueError:
                    pass
            time.sleep(.05)
        self.assertIsNotNone(pid)
        self.agent.stop(session['id'])
        self.wait(session)
        self.assertEqual(session['status'], 'paused')
        self.assertFalse(worker.workspace.exists())
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                state = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]
            except FileNotFoundError:
                return
            if state == 'Z':
                return
            time.sleep(.05)
        self.fail('Ordinary command child survived Stop')

    def test_controller_exit_terminates_the_ordinary_worker(self):
        marker = self.directory / 'worker.pid'
        code = ("import os,pathlib,threading,time\n"
                "from controller.execution import ExecutionPolicy\n"
                "from controller.native import NativeWorker\n"
                f"worker=NativeWorker(pathlib.Path({str(ROOT)!r}),ExecutionPolicy('native',True))\n"
                "assert worker.next(threading.Event(),time.monotonic()+10)=={'op':'ready','protocol':2}\n"
                f"pathlib.Path({str(marker)!r}).write_text(str(worker.process.pid)+'\\n'+str(worker.workspace))\n"
                "os._exit(0)\n")
        result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, timeout=15,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        saved = marker.read_text().splitlines()
        pid, workspace = int(saved[0]), Path(saved[1])
        self.assertTrue(workspace.resolve().is_relative_to((ROOT / '.data/native-runs').resolve()))
        self.addCleanup(lambda: workspace.rmdir() if workspace.exists() else None)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                state = Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[0]
            except FileNotFoundError:
                return
            if state == 'Z':
                return
            time.sleep(.05)
        os.kill(pid, signal.SIGKILL)
        self.fail('Native worker survived controller exit')

    def test_linux_lease_prevents_overlapping_workers(self):
        self.agent.appliance.verify()
        first, second = VMLease(self.agent.appliance.directory), VMLease(self.agent.appliance.directory)
        try:
            first.acquire(threading.Event(), time.monotonic() + 1)
            with self.assertRaisesRegex(Exception, 'Timed out'):
                second.acquire(threading.Event(), time.monotonic() + .2)
        finally:
            first.close(); second.close()

    def test_worker_does_not_inherit_provider_keys_or_python_injection_environment(self):
        with patch.dict(os.environ, {'AUTOPROTEUS_API_KEY':'fixture-secret',
                                   'PYTHONPATH':'fixture-path', 'LD_PRELOAD':'fixture-library'}):
            worker = NativeWorker(ROOT, self.execution)
        try:
            self.assertEqual(worker.next(threading.Event(), time.monotonic()+10), {'op':'ready','protocol':2})
            environment = Path(f'/proc/{worker.process.pid}/environ').read_bytes()
            for value in (b'fixture-secret', b'fixture-path', b'fixture-library'):
                self.assertNotIn(value, environment)
        finally:
            worker.close()


if __name__ == '__main__':
    unittest.main()
