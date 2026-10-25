"""The seed loop: request one action, execute it, journal it, continue."""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from . import __version__
from .providers import ProviderError, tool_definitions, argument_overrides
from .context import build_messages
from .storage import snapshot_seed
# Preserve imports used by existing edited seeds and checks.
from .protocol import GUIDANCE, PROTOCOL, NATIVE_PROMPT, parse_action, parse_decisions
from .tools import Cancelled, Workspace, clipped, EditConflict

class Agent:
    def __init__(self, root, store, settings, client_factory=None):
        self.root, self.store, self.settings = Path(root), store, settings
        self.client_factory = client_factory
        self.workers = {}
        self.lock = threading.Lock()

    def snapshot(self, session):
        snapshot_seed(self.root, session, __version__)

    def start(self, session, message=None):
        if __import__('os').environ.get('AUTOPROTEUS_GUEST') != '1' and self.client_factory is None:
            raise ValueError('The seed must run inside the isolated VM. Start AutoProteus with app.py.')
        with self.lock:
            existing = self.workers.get(session["id"])
            if existing and existing[1].is_alive():
                raise ValueError("This session is already running")
            config = dict(self.settings.values)
            if not config["configured"] and config["provider"] != "demo":
                raise ValueError("Connect a model first")
            if self.client_factory is None:
                raise ValueError("The VM supplies the model client. Use the protected launcher.")
            client = self.client_factory(config)
            self.snapshot(session)
            if not session["messages"]:
                session["messages"].append({"role": "user", "content": session["task"], "origin": "human"})
                self.store.feed(session, "user", session["task"])
            elif message:
                session["messages"].append({"role": "user", "content": message, "origin": "human"})
                self.store.feed(session, "user", message)
            else:
                notice = "Resume this task. Inspect current files and todo.txt before continuing. A previous action may have been interrupted or completed without its result being recorded. Do not blindly repeat it."
                session["messages"].append({"role": "user", "content": notice, "origin": "internal"})
                self.store.feed(session, "notice", "Session resumed. Checking the current workspace before continuing.")
            session.update(status="running", activity="Starting…", provider=config["provider"], model=config["model"], runs=session["runs"] + 1)
            self.store.event(session, "run_started", {"settings": config, "seed_version": session.get("seed_version"), "seed_sha256": session.get("seed_sha256")})
            self.store.save(session)
            cancel = threading.Event()
            thread = threading.Thread(target=self._run, args=(session, config, client, cancel), daemon=True)
            self.workers[session["id"]] = cancel, thread
            thread.start()

    def stop(self, session_id):
        with self.lock:
            worker = self.workers.get(session_id)
            if worker and worker[1].is_alive():
                session = self.store.get(session_id)
                session.update(status="stopping", activity="Stopping…")
                self.store.save(session)
                worker[0].set()

    def messages(self, session, config, steps=0):
        return build_messages(session, config, steps)

    def receive_inputs(self, session, client, mode):
        if getattr(client, 'supports_inputs', False) is not True:
            return False
        incoming = client.inputs(mode)
        known = {m.get('input_id') for m in session['messages']}
        for item in incoming:
            if item['id'] not in known:
                session['messages'].append({'role': 'user', 'content': item['content'],
                                            'origin': 'human', 'input_id': item['id']})
                self.store.feed(session, 'user', item['content'])
                known.add(item['id'])
        if incoming:
            self.store.save(session)
        return bool(incoming)

    def _run(self, session, config, client, cancel):
        workspace = Workspace(Path(session["workspace"]), config["terminal"], cancel, config["command_timeout"])
        repairs = 0
        previous_result, repeats = None, 0
        read_streak = 0
        argument_schemas = {item['function']['name']: item['function']['parameters'] for item in tool_definitions(config['terminal'])}
        try:
            steps = 0
            while True:
                final_request = config.get('action_limit', True) and steps >= config['max_steps']
                if cancel.is_set():
                    raise Cancelled()
                self.receive_inputs(session, client, 'steer')
                session["activity"] = "Thinking…"
                self.store.save(session)
                messages = self.messages(session, config, steps)
                self.store.event(session, "model_request", {"messages": messages, "model": config["model"], "provider": config["provider"]})
                try:
                    response = client.complete(messages, cancel)
                except ProviderError as error:
                    if error.response is not None:
                        self.store.event(session, 'model_response', error.response)
                    raise
                if cancel.is_set():
                    raise Cancelled()
                self.store.event(session, "model_response", response)
                if self.receive_inputs(session, client, 'steer'):
                    self.store.event(session, 'response_superseded', {'reason': 'new_human_input', 'action_executed': False})
                    continue
                try:
                    if response.get('provider_error') == 'cutoff':
                        raise ValueError('The response exceeded its output budget. Send a smaller action or patch. '
                                         'Generate large test data with short code rather than repeated literal text.')
                    decisions, deferred_finish = parse_decisions(response)
                except (ValueError, KeyError, TypeError) as error:
                    repairs += 1
                    self.store.event(session, "invalid_response", {"error": str(error)})
                    if repairs > config.get('response_retries', 2):
                        raise ValueError("This model did not follow the action format after two retries. Try another model or adjust its settings.")
                    instruction = 'Use the supplied tools with valid arguments, or explicitly finish following the response instructions.'
                    session["messages"].append({"role": "user", "content": "Your response was not accepted: " + str(error) + '. ' + instruction + " No action was executed.", "origin": "internal"})
                    self.store.feed(session, "notice", "The response format was invalid. Asking the model to correct it; no action was executed.")
                    continue
                repairs = 0
                for decision in decisions:
                    if cancel.is_set():
                        raise Cancelled()
                    if 'action' in decision and config.get('action_limit', True) and steps >= config['max_steps']:
                        break
                    if "status" in decision:
                        mode = 'finish' if decision['status'] == 'completed' and not final_request else 'steer'
                        if self.receive_inputs(session, client, mode):
                            self.store.event(session, 'finish_deferred', {'reason': 'queued_human_input'})
                            break
                    session["messages"].append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
                    if decision.get("message"):
                        self.store.feed(session, "assistant", decision["message"])
                    if "status" in decision:
                        session.update(status="completed" if decision["status"] == "completed" else "waiting", activity="Finished" if decision["status"] == "completed" else "Waiting for your reply")
                        self.store.event(session, "run_finished", {"status": session["status"], "verification": "model_reported"})
                        self.store.save(session)
                        return
                    action = decision["action"]
                    steps += 1
                    session["steps"] += 1
                    session["activity"] = "Working…"
                    session["pending_action"] = action
                    self.store.event(session, "action_started", action)
                    self.store.feed(session, "action", action["tool"], arguments=action["arguments"])
                    try:
                        result = workspace.execute(action["tool"], action["arguments"])
                        ok = not (result.get("timed_out") or result.get('output_limited') or result.get("exit_code", 0) != 0)
                    except Cancelled:
                        raise
                    except (ValueError, OSError, KeyError, TypeError) as error:
                        result, ok = {"error": str(error)}, False
                        if isinstance(error, EditConflict):
                            result.update(error.details)
                    overrides = argument_overrides(action['tool'], action['arguments'], argument_schemas)
                    feedback = {'argument_overrides': overrides} if overrides else {}
                    signature = (action['tool'], json.dumps(action['arguments'], sort_keys=True),
                                 hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest())
                    repeats = repeats + 1 if signature == previous_result else 1
                    previous_result = signature
                    read_streak = read_streak + 1 if ok and action['tool'] in ('read_file', 'read_section', 'search_files') else 0
                    if repeats == 3:
                        result = {**result, 'progress_hint': 'The same arguments produced the same result three times. Compare the saved outcome with the remaining user requirements; finish if verified, otherwise change the approach. Repeat only when intentional, such as polling.'}
                        self.store.feed(session, 'notice', 'Repeated identical results received a progress hint. Tools remain available.')
                    elif read_streak and read_streak % 8 == 0:
                        result = {**result, 'progress_hint': f'{read_streak} consecutive source reads without an edit or check. If you have enough context, make a small change and test it. Otherwise search for the missing detail and read a useful section.'}
                    self.store.event(session, "action_result", {"action": action, "result": result, "ok": ok, **feedback})
                    session.pop("pending_action", None)
                    session["messages"].append({"role": "user", "content": "ACTION RESULT\n" + json.dumps({"tool": action["tool"], "ok": ok, "result": result, **feedback}, ensure_ascii=False), "origin": "tool"})
                    self.store.feed(session, "result", "Done" if ok else "Action needs attention", result=result, ok=ok, **feedback)
                    self.messages(session, config, steps)
                    self.store.save(session)
                    if self.receive_inputs(session, client, 'steer'):
                        break
                    if not ok:
                        # Later calls may depend on this result. Let the model replan.
                        break
                if deferred_finish:
                    session['messages'].append({'role': 'user', 'content': 'Your finish call was deferred until you inspect the tool results above. Verify the requested outcome before finishing.', 'origin': 'internal'})
                if final_request:
                    break
            session.update(status="paused", activity="Action allowance reached")
            self.store.feed(session, "notice", "The optional action allowance was reached. Your work is saved. Resume to continue, or raise or turn off the allowance in Settings.")
        except Cancelled:
            session.update(status="paused", activity="Stopped")
            self.store.event(session, "run_stopped", {"pending_action": session.get("pending_action")})
            self.store.feed(session, "notice", "Stopped. Your files and session are saved.")
        except Exception as error:
            session.update(status="error", activity="Needs attention")
            self.store.event(session, "run_error", {"error": str(error)})
            self.store.feed(session, "error", str(error))
        finally:
            self.store.save(session)

    def close(self):
        with self.lock:
            workers = list(self.workers.values())
        for cancel, _ in workers:
            cancel.set()
        for _, thread in workers:
            thread.join(timeout=2)
