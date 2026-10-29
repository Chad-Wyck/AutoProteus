"""Protected VM policy and narrow broker. No seed modules are imported here."""
from __future__ import annotations

import base64
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import threading
import time

from .appliance import Appliance
# Keep existing imports available to saved study drivers and integrations.
from .artifacts import (Artifacts, MAX_FILE, MAX_FILES, MAX_EXPORT, SEED_TESTS,
                        packed_files, relative_name, safe_path, seed_files)
from .transport import MAX_FRAME, MAX_WIRE, PREFIX, WorkerTransport
from .errors import Cancelled, IsolationError
from .execution import ExecutionPolicy, NativeEnvironment
from .providers import DemoClient, ModelClient, ProviderError, ERROR_MESSAGES, PROTOCOL_HINTS, validate_context
from .storage import atomic_json
from .interactions import Inputs, Operations
from .inference_history import attach_history
from .web_access import WebAccess
from .thinking import Thinking
from .warm_vm import WarmVM
from .vm_lease import VMLease

MAX_JOURNAL = 64 * 1024 * 1024
MAX_SECONDS = 3600
RESPONSE_RETRIES = 2


def vm_command(appliance, bridge_port=0):
    """Fixed policy: no disk, NIC, monitor, UI, USB, sharing, or accelerator fallback."""
    runtime = appliance.directory
    linux = appliance.linux
    result = [str(appliance.binary()),
            '-no-user-config', '-nodefaults', '-machine', 'q35', '-accel', 'kvm' if linux else 'whpx',
            '-m', '2048', '-smp', '2', '-display', 'none', '-monitor', 'none',
            '-nic', 'none', '-serial', 'none', '-no-reboot',
            '-device', 'virtio-serial-pci', '-chardev', f'socket,id=bridge,host=127.0.0.1,port={bridge_port},server=off,nodelay=on',
            '-device', 'virtserialport,chardev=bridge,name=org.autoproteus.bridge',
            '-kernel', str(runtime / 'vmlinuz'), '-initrd', str(runtime / 'initrd.gz'),
            '-append', 'console=ttyS0 quiet panic=1 rdinit=/init']
    if linux:
        result.extend(['-sandbox', 'on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny'])
    return result


class VM(WorkerTransport):
    def __init__(self, appliance):
        super().__init__()
        self.bridge = None
        linux = appliance.linux
        if linux:
            from .linux_process import Job, command
        else:
            from .windows_job import Job
        self.job = Job()
        try:
            # No provider credentials or user-selected environment is inherited.
            environment = ({'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'} if linux else
                           {key: value for key, value in os.environ.items()
                            if key.upper() in ('SYSTEMROOT', 'WINDIR', 'TEMP', 'TMP')})
            # Windows QEMU stdio can drop input bytes. A private loopback
            # socket carries the same broker frames; the VM still has no NIC.
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
                if not linux:
                    listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                listener.bind(('127.0.0.1', 0))
                listener.listen(1)
                listener.settimeout(10)
                arguments = vm_command(appliance, listener.getsockname()[1])
                if linux:
                    arguments = command(arguments[0], arguments[1:], 'vm')
                self.process = subprocess.Popen(arguments,
                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                    cwd=appliance.directory, env=environment,
                    **({'start_new_session': True} if linux else
                       {'creationflags': subprocess.CREATE_NO_WINDOW | 0x4}))
                self.job.attach_and_resume(self.process)
                self.bridge, _ = listener.accept()
            self.bridge.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.process.stdin = self.bridge.makefile('wb', buffering=0)
            self.process.stdout = self.bridge.makefile('rb')
            self.start_readers()
        except Exception:
            self.close()
            raise

    def cleanup(self):
        if self.bridge:
            self.bridge.close()


class Broker:
    def __init__(self, store, session, client, config, cancel, activation_context='', human_message=None):
        self.store, self.session, self.client, self.cancel = store, session, client, cancel
        self.artifacts = Artifacts(store, session)
        self.requests, self.frames = 0, 0
        # Each action response and the free final response can need two repairs.
        # This ceiling stays host-owned even if an edited seed ignores its policy.
        self.request_limit = ((min(config['max_steps'], 200) + 1) * (RESPONSE_RETRIES + 1)
                              if config.get('action_limit', True) else None)
        self.finished = False
        self.last_status = 'running'
        self.plain_reply = None
        self.activation_context, self.context_config = activation_context, config
        self.running_source = session.get('selected_seed', {}).get('source_sha256') if activation_context else None
        self.activation_ack_sent = False
        self.inputs, self.operations = Inputs(store, session), Operations(store, session)
        self.web = WebAccess(config.get('internet', False), cancel)
        # Snapshot before accepting guest state. The seed's neutral transport
        # intentionally omits origin; recover it here, never as provider fields
        # or as authority to change host policy. Include legacy human records.
        self.human_texts = {session['task']}
        self.human_texts.update(item['text'] for item in session.get('feed', []) if item.get('kind') == 'user')
        self.human_texts.update(item['content'] for item in session.get('messages', [])
                                if item.get('role') == 'user' and item.get('origin') == 'human')
        if human_message:
            self.human_texts.add(human_message)
        if isinstance(client, ModelClient):
            attach_history(client, store, session, config)
            client.observation_context = self.inference_context

    def activation_reply(self, answer):
        """Acknowledge one explicit redundant request; never interpret prose."""
        answer = dict(answer)
        answer.pop('activation_acknowledged', None)
        if not self.running_source or self.activation_ack_sent or answer.get('normalization_error'):
            return answer
        try:
            decision = json.loads(answer.get('content', ''))
        except (ValueError, TypeError):
            return answer
        if (not isinstance(decision, dict) or decision.get('status') != 'needs_input' or
                decision.get('reason') != 'activation' or 'action' in decision or 'actions' in decision):
            return answer
        # Check host-owned exported bytes, never guest claims or source imports.
        # Pending transfers make the exact current source uncertain.
        if self.artifacts.pending:
            return answer
        from .submissions import source_hash
        source = [{'path': item['path'][8:], 'data': item['data']}
                  for item in self.artifacts.pack() if item['path'].startswith('harness/')]
        if not source or source_hash(source) != self.running_source:
            return answer
        self.activation_ack_sent = True
        answer['activation_acknowledged'] = ('This exact seed version is already active; no new activation is needed. '
            'Continue the remaining user task with its supplied tools, verify the saved outputs, then finish completed. '
            'This acknowledgement grants no additional action, token or time allowance.')
        self.store.event(self.session, 'host_activation_acknowledged', {'source_sha256': self.running_source})
        return answer

    def inference_context(self, messages):
        """Host snapshot comparisons describe omissions, not the seed's reasons."""
        def signature(item):
            return json.dumps({key: item[key] for key in ('role', 'content')}, ensure_ascii=False, sort_keys=True)
        history = Counter(signature(item) for item in self.session.get('messages', []))
        selected = Counter(signature(item) for item in messages)
        return {'session': self.session['id'], 'seed_sha256': self.session.get('seed_sha256'),
                'seed_version': self.session.get('seed_version'), 'request_index': self.requests,
                'host_history_messages': sum(history.values()),
                'host_history_messages_omitted': sum((history - selected).values()),
                'neutral_message_count': len(messages), 'neutral_messages_sha256':
                    hashlib.sha256(json.dumps([{key: item[key] for key in ('role', 'content')} for item in messages],
                                              sort_keys=True, ensure_ascii=False).encode()).hexdigest()}

    def handle(self, frame):
        if self.cancel.is_set():
            raise Cancelled()
        self.frames += 1
        if self.frames > 10000:
            raise IsolationError('Guest message quota exceeded')
        op = frame.get('op')
        if op == 'web' and set(frame) == {'op', 'request'}:
            result = self.web.request(frame['request'])
            # No request headers, bodies or credentials enter this host receipt.
            self.store.event(self.session, 'host_web_request', {
                'request_index': self.web.requests, 'status': result.get('status'),
                'bytes': result.get('bytes', 0), 'error': result.get('error')})
            return result
        if op == 'inputs' and set(frame) == {'op', 'mode'} and frame['mode'] in ('steer', 'finish'):
            messages = self.inputs.offer(frame['mode'])
            self.human_texts.update(item['content'] for item in messages)
            return messages
        if op == 'infer' and set(frame) in ({'op', 'messages'}, {'op', 'messages', 'tools'}):
            self.plain_reply = None
            messages = frame['messages']
            if isinstance(messages, list) and len(messages) > 2048:
                raise IsolationError('Model request exceeds the 2048-message limit')
            if (not isinstance(messages, list) or not 1 <= len(messages) <= 2048 or
                    any(not isinstance(m, dict) or set(m) != {'role', 'content'} or
                        m['role'] not in ('system', 'user', 'assistant') or not isinstance(m['content'], str)
                        for m in messages) or len(json.dumps(messages).encode()) > 1500000):
                raise IsolationError('Invalid model request')
            self.requests += 1
            if self.request_limit is not None and self.requests > self.request_limit:
                raise IsolationError('Model request quota exceeded')
            tools = frame.get('tools')
            if tools is not None:
                if (not isinstance(tools, list) or not 1 <= len(tools) <= 64 or len(json.dumps(tools).encode()) > 150000
                        or any(not isinstance(t, dict) or t.get('type') != 'function' or not isinstance(t.get('function'), dict)
                               or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', str(t['function'].get('name', '')))
                               or not isinstance(t['function'].get('parameters'), dict) for t in tools)):
                    raise IsolationError('Invalid guest tool descriptions')
            if self.session.get('selected_seed'):
                selected = self.session['selected_seed']
                if self.session.get('active_seed', {}).get('source_sha256') != selected['source_sha256']:
                    self.session['active_seed'] = {**selected, 'direct': [], 'development': []}
                self.store.save(self.session)
            if self.activation_context and not any(m['content'] == self.activation_context for m in messages):
                # Older seeds may omit the state. Insert it before task history,
                # leaving the newest actual result at the end of the request.
                index = next((i for i, m in enumerate(messages) if m['role'] != 'system'), len(messages))
                extended = messages[:index] + [{'role': 'user', 'content': self.activation_context}] + messages[index:]
                try:
                    validate_context(extended, tools, self.context_config)
                    fits = len(extended) <= 2048 and len(json.dumps(extended).encode()) <= 1500000
                except ProviderError:
                    fits = False
                if fits:
                    messages = extended
                else:
                    self.store.event(self.session, 'activation_context_omitted', {'reason': 'input_budget'})
            try:
                if isinstance(self.client, ModelClient):
                    # Schemas are data for the model, never host-executable capabilities.
                    forwarded = [{**item, **({'origin': 'human'} if item['role'] == 'user' and
                        item['content'] in self.human_texts else {})} for item in messages]
                    thinking = Thinking(self.store, self.session, self.cancel, self.client.key, self.context_config.get('thinking'))
                    outcome = 'failed'
                    try:
                        answer = self.client.complete(forwarded, self.cancel, progress=thinking, tools=tools)
                        if answer.get('reply_kind') == 'plain_reply':
                            self.plain_reply = json.loads(answer['content'])
                        thinking.thinking(answer.get('thinking', ''))
                        outcome = 'completed'
                        return self.activation_reply(answer)
                    except Cancelled:
                        outcome = 'interrupted'
                        raise
                    finally:
                        thinking.finish(outcome)
                return self.activation_reply(self.client.complete(messages, self.cancel))
            except Cancelled:
                raise
            except ProviderError as error:
                if error.category == 'cutoff':
                    # Discard partial text/calls. Only a fixed marker crosses the
                    # boundary; the seed can spend its bounded format retries.
                    self.store.event(self.session, 'provider_cutoff', {'partial_action_executed': False})
                    return {'content': '', 'provider_error': 'cutoff'}
                if error.category == 'protocol':
                    reason = error.response.get('protocol_reason') if isinstance(error.response, dict) else None
                    hint = PROTOCOL_HINTS.get(reason, 'Use the supplied tools with valid arguments. Prefer one tool call at a time.')
                    self.store.event(self.session, 'provider_protocol_error', {'reason': reason if reason in PROTOCOL_HINTS else 'unspecified',
                                                                             'partial_action_executed': False})
                    return {'content': '', 'provider_error': 'protocol', 'normalization_error': hint}
                self.session['error_category'] = error.category
                raise IsolationError(ERROR_MESSAGES[error.category]) from None
            except Exception:
                # Provider errors can echo headers or credentials. Keep them on the host.
                raise IsolationError('The configured model service could not complete this request. Check the host connection.') from None
        if op == 'file' and set(frame) == {'op', 'path', 'data'}:
            self.artifacts.put(frame['path'], frame['data'])
        elif op == 'checkpoint' and set(frame) == {'op', 'paths'}:
            with self.store.lock:
                self.artifacts.checkpoint(frame['paths'])
                self.operations.checkpoint()
        elif op == 'state' and set(frame) in ({'op', 'session'}, {'op', 'session', 'changes'}):
            value = frame['session']
            if 'changes' in frame:
                changes = frame['changes']
                if (not isinstance(value, dict) or {'messages', 'feed'} & value.keys() or
                        not isinstance(changes, dict) or set(changes) != {'messages', 'feed'}):
                    raise IsolationError('Invalid history changes')
                value = dict(value)
                for name in ('messages', 'feed'):
                    change = changes[name]
                    previous = self.session.get(name, [])
                    if (not isinstance(change, dict) or set(change) != {'prefix', 'items'} or
                            type(change['prefix']) is not int or not 0 <= change['prefix'] <= len(previous) or
                            not isinstance(change['items'], list) or change['prefix'] + len(change['items']) > 2000):
                        raise IsolationError('Invalid history changes')
                    value[name] = previous[:change['prefix']] + change['items']
            if not isinstance(value, dict) or len(json.dumps(value).encode()) > 1500000:
                raise IsolationError('Session state too large')
            fields = {'status', 'activity', 'messages', 'feed', 'steps', 'runs', 'todo', 'seed_version', 'seed_sha256'}
            if value.get('status') not in ('ready', 'running', 'stopping', 'paused', 'interrupted', 'completed', 'waiting', 'error'):
                raise IsolationError('Invalid session status')
            for name in ('activity', 'todo'):
                if not isinstance(value.get(name, ''), str) or len(value.get(name, '')) > 12000:
                    raise IsolationError('Invalid session text')
            for name in ('messages', 'feed'):
                if not isinstance(value.get(name), list) or len(value[name]) > 2000:
                    raise IsolationError('Invalid session history')
            for item in value['messages']:
                if not isinstance(item, dict) or item.get('role') not in ('system', 'user', 'assistant') or not isinstance(item.get('content'), str):
                    raise IsolationError('Invalid history message')
            for item in value['feed']:
                if (not isinstance(item, dict) or not isinstance(item.get('id'), str) or len(item['id']) > 64
                        or item.get('kind') not in ('user', 'assistant', 'notice', 'action', 'result', 'error')
                        or not isinstance(item.get('text'), str)):
                    raise IsolationError('Invalid display message')
            if len({item['id'] for item in value['feed']}) != len(value['feed']):
                raise IsolationError('Duplicate display message IDs')
            for name in ('steps', 'runs'):
                if type(value.get(name)) is not int or not 0 <= value[name] <= 100000:
                    raise IsolationError('Invalid session counter')
            for name in ('seed_version', 'seed_sha256'):
                if name in value and (not isinstance(value[name], str) or len(value[name]) > 100):
                    raise IsolationError('Invalid seed metadata')
            self.last_status = value['status']
            # Stop stays visible until the host has ended the VM.
            fields.remove('status')
            with self.store.lock:
                self.session.update({key: value[key] for key in fields if key in value})
                self.session.pop('waiting_reason', None)
                if self.last_status == 'waiting' and self.plain_reply is not None:
                    last = next((item['content'] for item in reversed(value['messages']) if item['role'] == 'assistant'), '')
                    try:
                        consumed = json.loads(last) == self.plain_reply
                    except ValueError:
                        consumed = False
                    if consumed:
                        self.session['waiting_reason'] = 'plain_reply'
                        self.session['activity'] = 'Paused without explicit completion'
                self.inputs.acknowledge(value['messages'])
                self.operations.acknowledge(value['messages'])
                self.session['status'] = 'running'
                self.store.save(self.session)
        elif op == 'event' and set(frame) == {'op', 'type', 'data'}:
            if (not isinstance(frame['type'], str) or frame['type'].startswith('host_') or
                    len(frame['type']) > 60 or len(json.dumps(frame['data']).encode()) > 1500000):
                raise IsolationError('Invalid journal event')
            journal = self.store.directory(self.session['id']) / 'events.jsonl'
            if journal.stat().st_size + len(json.dumps(frame).encode()) > MAX_JOURNAL:
                raise IsolationError('Session journal quota exceeded')
            event = self.store.event(self.session, frame['type'], frame['data'])
            with self.store.lock:
                self.operations.event(frame['type'], frame['data'], event['id'])
            if frame['type'] == 'action_result' and self.session.get('active_seed'):
                from .evaluation import tool_use
                try:
                    used = tool_use([{'type': frame['type'], 'data': frame['data']}])
                except (ValueError, TypeError, AttributeError, RecursionError):
                    used = {'direct': [], 'development': []}
                active = self.session['active_seed']
                for route in ('direct', 'development'):
                    active[route] = sorted(name for name in set(active.get(route, [])) | set(used[route])
                                           if isinstance(name, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,64}', name))[:64]
                self.store.save(self.session)
        elif op == 'done' and set(frame) == {'op'}:
            self.finished = True
        elif op == 'failure' and set(frame) == {'op', 'message'}:
            raise IsolationError('Guest stopped: ' + str(frame['message'])[:2000])
        else:
            raise IsolationError('Guest requested an unsupported host operation')
        return None


class IsolatedAgent:
    def __init__(self, root, store, settings, client_factory=None, execution=None):
        self.root, self.store, self.settings = Path(root).resolve(), store, settings
        self.execution = execution or ExecutionPolicy()
        self.appliance = NativeEnvironment(self.root) if self.execution.mode == 'native' else Appliance(self.root)
        self.client_factory = client_factory
        self.workers, self.vms = {}, {}
        self.lock = threading.RLock()
        # Enabled only by the interactive app. Graders and study drivers retain
        # their fresh-VM lifecycle; the seed cannot enable retention itself.
        self.can_retain = None
        self.idle = None
        self.warm = WarmVM(self.appliance, VM, VMLease)

    def keep_ready(self, config):
        if self.execution.mode != 'vm' or not self.can_retain:
            return
        loaded = bool(config.get('configured')) and self.can_retain(config)
        with self.lock:
            if not loaded:
                self.discard_idle()
                self.warm.close()
                return
            if self.idle:
                self.reap_idle()
            if (not self.idle and not any(thread.is_alive() for _, thread in self.workers.values())
                    and self.appliance.public()['ready']):
                self.warm.prepare()

    def discard_idle(self):
        with self.lock:
            idle, self.idle = self.idle, None
            if idle:
                try:
                    idle['vm'].close()
                finally:
                    idle['lease'].close()

    def retained_session(self):
        with self.lock:
            return self.idle['session'] if self.idle else None

    def reap_idle(self):
        with self.lock:
            if self.idle and (self.idle['vm'].closed.is_set() or not self.can_retain
                              or not self.can_retain(self.idle['config']) or self.idle['lease'].request_pending()):
                self.discard_idle()

    def start(self, session, message=None, candidate=None, verification=False, handoff='full', deadline=None):
        if handoff not in ('full', 'concise'):
            raise ValueError('Choose full or concise activation context')
        with self.lock:
            if deadline is not None and time.monotonic() >= deadline:
                raise IsolationError('The shared task deadline expired before VM startup')
            if any(thread.is_alive() for _, thread in self.workers.values()):
                raise IsolationError('Stop the current task before starting another isolated run')
            self.appliance.verify()
            config = dict(self.settings.values)
            if not config['configured']:
                raise ValueError('Connect a model first')
            client = self.client_factory(config) if self.client_factory else (DemoClient() if config['provider'] == 'demo' else ModelClient(config, self.settings.key()))
            inputs = Artifacts(self.store, session).pack() if 'artifacts' in session else packed_files(session['workspace'])
            source = seed_files(self.root)
            if candidate:
                source = [{'path': item['path'][8:], 'data': item['data']} for item in Artifacts(self.store, candidate).pack() if item['path'].startswith('harness/')]
                if not {'seed.py', 'autoproteus/agent.py'}.issubset({item['path'] for item in source}):
                    raise IsolationError('This candidate is missing seed.py or autoproteus/agent.py')
            elif session.get('candidate_from'):
                source = json.loads((self.store.directory(session['id']) / 'candidate.json').read_text(encoding='utf-8'))
            if verification:
                source = [item for item in source if not item['path'].startswith('__verify__/')]
                for name in SEED_TESTS:
                    source.append({'path': '__verify__/' + Path(name).name, 'data': base64.b64encode(
                        (self.root / name).read_bytes()).decode()})
            guest_config = {key: value for key, value in config.items() if key not in ('base_url', 'api_key')}
            guest_config['response_retries'] = RESPONSE_RETRIES
            if config.get('action_limit') is False:
                # Older edited loops understand max_steps but not the optional
                # switch. This value is unreachable within the independent
                # 10,000-frame host envelope, so those loops also stay uncapped.
                guest_config['max_steps'] = 100000
            guest_config.pop('activation_context', None)
            if candidate is session or session.get('candidate_from') == session['id']:
                bundle_hash = hashlib.sha256(json.dumps(source, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                guest_config['activation_context'] = (
                    'CURRENT ACTIVATION STATE\nRunning seed bundle SHA-256: ' + bundle_hash + '.\n'
                    'This version is already active; its earlier activation request is fulfilled. '
                    'Continue the remaining user task using the active tools. Do not repeat development checks solely '
                    'to request activation of this same version. Further source edits require another activation. '
                    'All original human requirements still apply.')
            boot = {'op': 'boot', 'seed': source, 'files': inputs,
                    'session': {k: v for k, v in session.items() if k not in ('input_queue', 'operation_receipts', 'thinking_spans')},
                    'config': guest_config, 'message': message, 'seed_activated': candidate is session,
                    'handoff': handoff}
            boot['verification'] = bool(verification)
            boot['recovery_notice'] = Operations(self.store, session).notice()
            if isinstance(verification, dict):
                boot['behavior_rules'] = verification['rules']
            # Do not send host directories, credentials, or quarantine metadata.
            boot['session'].pop('artifacts', None)
            boot['session']['workspace'] = '/work/task'
            boot['session']['execution_mode'] = self.execution.mode
            boot['session'].pop('isolation', None)
            if len(json.dumps({key: value for key, value in boot.items() if key not in ('seed', 'files')}).encode()) > MAX_FRAME - 100:
                raise IsolationError('Session history exceeds the restore limit')
            signature = hashlib.sha256(json.dumps({'source': source, 'config': guest_config,
                'artifacts': session.get('artifacts'), 'handoff': handoff}, sort_keys=True).encode()).hexdigest()
            retained = None
            if self.idle:
                if (not verification and candidate is None and self.idle['session'] == session['id']
                        and self.idle['signature'] == signature and not self.idle['vm'].closed.is_set()
                        and not self.idle['lease'].request_pending()
                        and self.can_retain and self.can_retain(config)):
                    retained = self.idle
                else:
                    self.discard_idle()
            boot['allow_retention'] = not verification
            if candidate:
                # Freeze only after input validation; candidate bytes never run here.
                atomic_json(self.store.directory(session['id']) / 'candidate.json', source)
            from .submissions import source_hash
            session['selected_seed'] = {'source_sha256': source_hash(source)}
            prepared = self.warm.public()
            session.update(status='running', activity='Continuing in your virtual machine…' if retained else 'Preparing your workspace…' if prepared['ready'] else 'Starting the virtual machine…' if self.execution.mode == 'vm'
                           else 'Starting without AutoProteus VM protection…',
                           isolation=self.execution.mode == 'vm', execution_mode=self.execution.mode)
            history = session.setdefault('execution_history', [])
            history.append({'mode': self.execution.mode, 'isolated': session['isolation']})
            del history[:-200]
            self.store.save(session)
            self.store.event(session, 'execution_started', {**self.execution.public(), 'vm_reused':bool(retained)})
            cancel = threading.Event()
            thread = threading.Thread(target=self._run, args=(session, boot, client, config, cancel, deadline, retained), daemon=True)
            self.workers[session['id']] = cancel, thread
            thread.start()
            if retained:
                self.idle = None

    def restart_seed(self, session, handoff='full', deadline=None):
        """Explicit controller action: activate this checkpoint in the same task."""
        with self.lock:
            previous = session.get('candidate_from')
            session['candidate_from'] = session['id']
            try:
                self.start(session, candidate=session, handoff=handoff, **({'deadline': deadline} if deadline is not None else {}))
            except Exception:
                if previous is None:
                    session.pop('candidate_from', None)
                else:
                    session['candidate_from'] = previous
                raise

    def _run(self, session, boot, client, config, cancel, run_deadline=None, retained=None):
        vm, broker = None, Broker(self.store, session, client, config, cancel, boot['config'].get('activation_context', ''), boot.get('message'))
        lease = None
        # Host deadline covers boot, inference, commands and all guest code.
        deadline = time.monotonic() + MAX_SECONDS
        if run_deadline is not None:
            deadline = min(deadline, run_deadline)
        broker.web.deadline = deadline
        watching = threading.Event()
        watcher = None
        successful = False
        prepared = None
        try:
            if retained:
                vm, lease = retained['vm'], retained['lease']
            else:
                prepared = self.warm.take(cancel, deadline)
                if prepared:
                    vm, lease = prepared['vm'], prepared['lease']
                else:
                    lease = VMLease(self.appliance.directory)
                    def waiting():
                        with self.store.lock:
                            session['activity'] = 'Waiting for another AutoProteus VM to finish…'
                            self.store.save(session)
                    lease.acquire(cancel, deadline, waiting)
            if time.monotonic() >= deadline:
                raise IsolationError('The shared task deadline expired before worker startup')
            if retained or prepared:
                pass
            elif self.execution.mode == 'native':
                from .native import NativeWorker
                vm = NativeWorker(self.root, self.execution)
            else:
                vm = VM(self.appliance)
            with self.lock:
                self.vms[session['id']] = vm
                if cancel.is_set():
                    raise Cancelled()
            if not retained and not prepared:
                ready = vm.next(cancel, min(deadline, time.monotonic() + 90))
                if ready != {'op': 'ready', 'protocol': 2}:
                    raise IsolationError('Guest handshake failed')
            # A blocked guest reader cannot stall the external watchdog or Stop.
            watcher = threading.Thread(target=self._watchdog, args=(vm, cancel, deadline, watching), daemon=True)
            watcher.start()
            if retained:
                vm.send({'op': 'continue', 'message': boot.get('message') or ''})
            else:
                vm.send({key: value for key, value in boot.items() if key not in ('seed', 'files', 'allow_retention')})
                if vm.next(cancel, deadline) != {'op': 'input_ready'}:
                    raise IsolationError('Guest did not accept the boot request')
                for area, files in (('seed', boot['seed']), ('workspace', boot['files'])):
                    for item in files:
                        checksum = hashlib.sha256(base64.b64decode(item['data'], validate=True)).hexdigest()
                        vm.send({'op': 'input', 'area': area, **item, 'sha256': checksum})
                        reply = vm.next(cancel, deadline)
                        if reply != {'op': 'input_saved'}:
                            raise IsolationError('Guest input transfer failed: ' + str(reply)[:1500])
                vm.send({'op': 'inputs_done'})
            while not broker.finished:
                frame = vm.next(cancel, deadline)
                value = broker.handle(frame)
                vm.send({'op': 'reply', 'value': value})
            if broker.last_status in ('running', 'stopping', 'ready'):
                raise IsolationError('The guest exited without a final session status')
            session['status'] = broker.last_status
            successful = broker.last_status in ('completed', 'waiting', 'paused')
        except Cancelled:
            session.update(status='paused', activity='Stopped. The last saved checkpoint is ready to resume.')
        except Exception as error:
            if cancel.is_set():
                session.update(status='paused', activity='Stopped. Your saved checkpoint is ready to resume.')
            else:
                session.update(status='error', activity='The isolated run stopped')
                self.store.feed(session, 'notice', str(error)[:3000])
        finally:
            watching.set()
            if watcher:
                watcher.join(timeout=1)
            try:
                with self.lock:
                    if (vm and successful and not cancel.is_set() and not vm.closed.is_set()
                            and self.execution.mode == 'vm' and boot['allow_retention']
                            and self.can_retain and self.can_retain(config)):
                        # Compare the final committed manifest on the next turn;
                        # an import or source/config change must force a reboot.
                        signature = hashlib.sha256(json.dumps({'source': boot['seed'], 'config': boot['config'],
                            'artifacts': session.get('artifacts'), 'handoff': boot['handoff']}, sort_keys=True).encode()).hexdigest()
                        self.idle = {'vm':vm, 'lease':lease, 'session':session['id'],
                                     'signature':signature, 'config':dict(config)}
                        vm, lease = None, None
                if vm:
                    vm.close()
            finally:
                if lease:
                    lease.close()
            with self.lock:
                self.vms.pop(session['id'], None)
            broker.artifacts.pending = {}
            broker.artifacts.cleanup()
            session['model_requests'] = broker.requests
            self.store.save(session)

    def _watchdog(self, vm, cancel, deadline, finished=None):
        while not (finished and finished.wait(0.1)) and not vm.closed.is_set():
            if finished is None:
                vm.closed.wait(0.1)
            if cancel.is_set() or time.monotonic() > deadline:
                vm.close()
                return

    def stop(self, session_id):
        with self.lock:
            if self.idle and self.idle['session'] == session_id:
                self.discard_idle()
            worker = self.workers.get(session_id)
            if worker and worker[1].is_alive():
                worker[0].set()
                vm = self.vms.get(session_id)
                if vm:
                    vm.close()

    def export_for_checks(self, session):
        """Trusted evaluator reads bytes only; it never runs exported verifier code."""
        artifacts = Artifacts(self.store, session)
        for name in session.get('artifacts', {}):
            path = safe_path(session['workspace'], name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(artifacts.read(name))

    def close(self):
        self.warm.close()
        self.discard_idle()
        for session_id in list(self.workers):
            self.stop(session_id)
        for _, thread in list(self.workers.values()):
            thread.join(timeout=5)
