"""Real hostile-guest tests. Opt in with AUTOPROTEUS_VM_TESTS=1 on a prepared Windows host."""
import base64
import json
import os
from pathlib import Path
import tempfile
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
from unittest.mock import patch

from controller.config import Settings
from controller.isolation import Artifacts, IsolatedAgent, seed_files
from controller.storage import Store

ROOT = Path(__file__).resolve().parents[1]


class ScriptedClient:
    def __init__(self, actions):
        self.actions, self.index = actions, 0

    def complete(self, messages, cancel):
        result = self.actions[min(self.index, len(self.actions) - 1)]
        self.index += 1
        return {'content': json.dumps(result), 'usage': {}}


@unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS') == '1', 'Real VM checks require explicit opt in')
class RealVMTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.data/test-tmp'
        parent.mkdir(exist_ok=True, parents=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.data = Path(self.temp.name)
        self.store = Store(self.data / 'sessions')
        self.settings = Settings(self.data)
        self.settings.values.update(configured=True, provider='hosted', model='offline-boundary-test',
                                    protocol='json', terminal=True, max_steps=8)
        self.agents = []

    def tearDown(self):
        for agent in self.agents:
            agent.close()
        self.temp.cleanup()

    def agent(self, actions):
        client = ScriptedClient(actions)
        agent = IsolatedAgent(ROOT, self.store, self.settings, lambda _: client)
        self.agents.append(agent)
        return agent

    def wait(self, agent, session, seconds=45):
        agent.workers[session['id']][1].join(timeout=seconds)
        if agent.workers[session['id']][1].is_alive():
            agent.stop(session['id'])
            self.fail('VM test did not finish within its deadline')
        return session['status']

    def candidate(self, text):
        session = self.store.create('candidate', 'hosted', 'offline-boundary-test')
        artifacts = Artifacts(self.store, session)
        files = {item['path']: item['data'] for item in seed_files(ROOT)}
        files['seed.py'] = base64.b64encode(text.encode()).decode()
        for name, encoded in files.items():
            artifacts.put('harness/' + name, encoded)
        artifacts.checkpoint(['harness/' + name for name in files])
        return session

    def test_commands_cannot_read_host_files_or_change_host_policy_and_have_no_network(self):
        sentinel = self.data / 'host-sentinel.txt'
        sentinel.write_text('HOST SENTINEL MUST SURVIVE')
        policy = (ROOT / 'controller/isolation.py').read_bytes()
        probe = '''import json,os,pathlib,socket,subprocess
report={"uid":os.getuid(),"interfaces":os.listdir('/sys/class/net'),"host_visible":pathlib.Path(HOST).exists(),"controller_visible":pathlib.Path('/controller/isolation.py').exists()}
try:
 os.setuid(0); report['became_root']=True
except PermissionError:
 report['became_root']=False
try:
 socket.create_connection(('10.0.2.2',47831),timeout=1).close(); report['host_network']=True
except OSError:
 report['host_network']=False
try:
 pathlib.Path('/seed/seed.py').write_text('damaged'); report['changed_starter']=True
except PermissionError:
 report['changed_starter']=False
report['remount_exit']=subprocess.run(['mount','-o','remount,size=1g','/work'],capture_output=True).returncode
pathlib.Path('boundary.json').write_text(json.dumps(report))
'''.replace('HOST', repr(str(sentinel)))
        encoded = base64.b64encode(probe.encode()).decode()
        command = "python3 -c \"import base64; exec(base64.b64decode('" + encoded + "'))\""
        agent = self.agent([
            {'message': 'Probe the guest boundary', 'action': {'tool': 'run_command', 'arguments': {'command': command}}},
            {'message': 'Verified', 'status': 'completed'},
        ])
        session = self.store.create('Test boundary', 'hosted', 'offline-boundary-test')
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        report = json.loads(Artifacts(self.store, session).read('boundary.json'))
        self.assertEqual(report['uid'], 1000)
        self.assertEqual(report['interfaces'], ['lo'])
        for key in ('host_visible', 'controller_visible', 'became_root', 'host_network', 'changed_starter'):
            self.assertFalse(report[key], report)
        self.assertNotEqual(report['remount_exit'], 0)
        self.assertEqual(sentinel.read_text(), 'HOST SENTINEL MUST SURVIVE')
        self.assertEqual((ROOT / 'controller/isolation.py').read_bytes(), policy)
        # Restore the checkpoint into another fresh VM using the same policy.
        agent.start(session, 'Verify the saved boundary report')
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        self.assertEqual(json.loads(Artifacts(self.store, session).read('boundary.json')), report)

    def test_native_provider_gateway_keeps_credentials_outside_guest_and_saves_verified_output(self):
        requests = []
        secret = 'boundary-test-key-never-send-to-guest'
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append((payload, self.headers.get('Authorization')))
                name = 'write_file' if len(requests) == 1 else 'finish'
                args = {'path': 'gateway.txt', 'content': 'Protected native gateway works\n'} if name == 'write_file' else {'message': 'Verified', 'status': 'completed'}
                body = json.dumps({'choices': [{'finish_reason': 'tool_calls', 'message': {'content': '', 'tool_calls': [
                    {'id': 'native-test', 'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}}]}).encode()
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            self.settings.update({'base_url': f'http://127.0.0.1:{server.server_port}/v1', 'api_key': secret, 'protocol': 'native'})
            agent = IsolatedAgent(ROOT, self.store, self.settings)
            self.agents.append(agent)
            session = self.store.create('Verify the native provider gateway', 'hosted', 'offline-boundary-test')
            agent.start(session)
            self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
            self.assertEqual(Artifacts(self.store, session).read('gateway.txt'), b'Protected native gateway works\n')
            self.assertEqual(len(requests), 2)
            self.assertTrue(all(auth == 'Bearer ' + secret for _, auth in requests))
            self.assertTrue(requests[0][0]['tools'])
            trace = (self.store.directory(session['id']) / 'events.jsonl').read_text(encoding='utf-8')
            self.assertNotIn(secret, trace)
            self.assertNotIn(self.settings.values['base_url'], trace)
        finally:
            server.shutdown(); server.server_close(); thread.join()

    def test_editable_seed_regressions_run_inside_the_guest(self):
        agent = self.agent([
            {'message': 'Check the seed', 'action': {'tool': 'run_command', 'arguments': {
                'command': 'cd harness && python3 -m unittest discover -s tests -v'}}},
            {'message': 'Checked', 'status': 'completed'},
        ])
        session = self.store.create('Run the editable seed tests', 'hosted', 'offline-boundary-test')
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])
        events = [json.loads(line) for line in (self.store.directory(session['id']) / 'events.jsonl').read_text(encoding='utf-8').splitlines()]
        result = next(event['data']['result'] for event in events if event['type'] == 'action_result')
        self.assertEqual(result['exit_code'], 0, result['output'])
        self.assertIn('OK', result['output'])

    def test_host_rejects_a_forged_export_from_arbitrary_candidate_code(self):
        candidate = self.candidate('''def run(*args):
 import __main__,base64
 __main__.call({'op':'file','path':'../../controller/isolation.py','data':base64.b64encode(b'damaged').decode()})
''')
        policy = (ROOT / 'controller/isolation.py').read_bytes()
        agent = self.agent([])
        session = self.store.create('Try hostile candidate', 'hosted', 'offline-boundary-test')
        agent.start(session, candidate=candidate)
        self.assertEqual(self.wait(agent, session), 'error')
        self.assertIn('Invalid export path', session['feed'][-1]['text'])
        self.assertEqual((ROOT / 'controller/isolation.py').read_bytes(), policy)
        self.assertEqual(session.get('artifacts', {}), {})

    def test_stop_terminates_a_noncooperating_candidate_then_starter_recovers(self):
        candidate = self.candidate('''def run(*args):
 import time
 while True: time.sleep(0.1)
''')
        agent = self.agent([{'message': 'Recovered', 'status': 'completed'}])
        session = self.store.create('Try stuck candidate', 'hosted', 'offline-boundary-test')
        agent.start(session, candidate=candidate)
        limit = time.monotonic() + 15
        while session['id'] not in agent.vms and time.monotonic() < limit:
            time.sleep(.05)
        time.sleep(2)
        process = agent.vms[session['id']].process
        started = time.monotonic()
        agent.stop(session['id'])
        self.assertEqual(self.wait(agent, session, seconds=5), 'paused')
        self.assertLess(time.monotonic() - started, 5)
        self.assertIsNotNone(process.poll())
        agent.start(session)
        self.assertEqual(self.wait(agent, session), 'completed', session['feed'])

    def test_comparison_checks_actual_files_from_a_frozen_candidate(self):
        from controller.evaluation import EvaluationService, source_identity, candidate_source
        candidate = self.candidate('''from autoproteus.agent import Agent
def run(root, store, settings, client_factory, session, message=None):
 import json
 class Client:
  calls=0
  def complete(self, messages, cancel):
   self.calls+=1
   return {'content':json.dumps({'action':{'tool':'write_file','arguments':{'path':'greeting.txt','content':'Wrong\\n'}}} if self.calls==1 else {'message':'All tests passed','status':'completed'})}
 agent=Agent(root,store,settings,lambda _:Client())
 agent.start(session,message)
 return agent
''')
        task_agent = self.agent([])
        service = EvaluationService(ROOT, self.data / 'evaluations', self.settings, task_agent)
        task = {'name':'exact-file', 'task':'Create greeting.txt', 'checks':[{'path':'greeting.txt','equals':'Hello, AutoProteus!\n'}]}
        original = Path.read_text
        def read_text(path, *args, **kwargs):
            return json.dumps([task]) if path == ROOT / 'evaluations/tasks.json' else original(path, *args, **kwargs)
        def make_agent(root, store, settings, execution=None):
            return IsolatedAgent(root, store, settings, lambda _: ScriptedClient([
                {'action':{'tool':'write_file','arguments':{'path':'greeting.txt','content':'Hello, AutoProteus!\n'}}},
                {'status':'completed'}]), execution=execution)
        try:
            with patch.object(Path, 'read_text', read_text), patch('controller.evaluation.IsolatedAgent', side_effect=make_agent):
                initial = service.start(candidate, repeats=1)
            expected = initial['edited_sha256']
            # Later workspace edits must not change the frozen version under test.
            a = Artifacts(self.store, candidate)
            a.put('harness/seed.py', base64.b64encode(b'raise RuntimeError("later edit")').decode())
            a.checkpoint(list(candidate['artifacts']))
            service.thread.join(timeout=80)
            self.assertFalse(service.busy)
            report = service.public()
            self.assertEqual(report['status'], 'completed', report)
            self.assertEqual(report['edited_sha256'], expected)
            self.assertNotEqual(source_identity(candidate_source(self.store, candidate)), expected)
            self.assertEqual(report['summary']['starter']['passed'], 1)
            self.assertEqual(report['summary']['edited']['passed'], 0)
            self.assertEqual(report['results'][1]['status'], 'completed')
            self.assertTrue(report['regressions']['starter']['passed'], report['regressions']['starter'])
        finally:
            service.close()

    def test_damaged_input_is_rejected_before_seed_execution(self):
        from controller.isolation import VM
        agent = self.agent([{'status':'completed'}])
        session = self.store.create('damaged input', 'hosted', 'offline-test')
        send = VM.send
        def tamper(vm, value):
            if value.get('op') == 'input' and value.get('area') == 'seed' and value.get('path') == 'seed.py':
                value = {**value, 'data':base64.b64encode(b'raise RuntimeError("must not execute")').decode()}
            return send(vm, value)
        with patch.object(VM, 'send', tamper):
            agent.start(session)
            self.assertEqual(self.wait(agent, session), 'error')
        self.assertIn('Input integrity check failed', session['feed'][-1]['text'])
        self.assertEqual(session['model_requests'], 0)
        self.assertEqual(session.get('artifacts', {}), {})


if __name__ == '__main__':
    unittest.main()
