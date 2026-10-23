import json, threading, unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from controller.config import DEFAULTS
from controller.providers import ModelClient, ProviderError, model_response, normalize_tool_response, wire_messages
from unittest.mock import patch
from autoproteus.agent import parse_action
from autoproteus.providers import tool_definitions


class FakeModelServer:
    def __init__(self, cut_short=False, hosted=False, native=False, diagnostic=False, frames=None):
        self.payloads = []; parent = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                parent.payloads.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(200); self.send_header('Content-Type', 'application/json'); self.end_headers()
                if frames is not None:
                    for frame in frames:
                        self.wfile.write((json.dumps(frame) + '\n').encode())
                    return
                content = json.dumps({'message': 'Ready', 'status': 'completed'})
                calls = [{'function': {'name': 'write_file', 'arguments': {'path': 'sample.txt', 'content': 'sample'}}}]
                if diagnostic:
                    messages = parent.payloads[-1]['messages']
                    if messages[-1]['content'].startswith('All rounds are complete.'):
                        decision = {'message': 'Connection checked.', 'status': 'completed'}
                        calls = [{'function': {'name': 'finish', 'arguments': decision}}]
                    elif messages[-1]['role'] == 'tool' or messages[-1]['content'].startswith('ACTION RESULT\n'):
                        result = json.loads(messages[-1]['content'].removeprefix('ACTION RESULT\n'))
                        if result.get('ok') is False:
                            value = next(item['content'].split('Test value: ')[1] for item in reversed(messages)
                                         if item['role'] == 'user' and item['content'].startswith('Test value: '))
                            decision = {'action': {'tool': 'diagnostic_echo', 'arguments': {'value': value}}}
                            calls = [{'function': {'name': 'diagnostic_echo', 'arguments': {'value': value}}}]
                        else:
                            arguments = {'receipt': result['result']['receipt']}
                            decision = {'action': {'tool': 'diagnostic_confirm', 'arguments': arguments}}
                            calls = [{'function': {'name': 'diagnostic_confirm', 'arguments': arguments}}]
                    else:
                        value = messages[-1]['content'].split('Test value: ')[1]
                        decision = {'action': {'tool': 'diagnostic_echo', 'arguments': {'value': value}}}
                        calls = [{'function': {'name': 'diagnostic_echo', 'arguments': {'value': value}}}]
                    content = json.dumps(decision)
                if hosted:
                    message = {'content': '' if native else content}
                    if native:
                        message['tool_calls'] = calls
                    self.wfile.write(json.dumps({'choices': [{'message': message, 'finish_reason': 'length' if cut_short else 'tool_calls' if native else 'stop'}]}).encode())
                else:
                    message = {'content': '' if native else content}
                    if native:
                        message['tool_calls'] = calls
                    self.wfile.write((json.dumps({'message': message, 'done': False}) + '\n').encode())
                    if not cut_short:
                        self.wfile.write((json.dumps({'message': {'content': ''}, 'done': True, 'done_reason': 'stop'}) + '\n').encode())
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start(); self.url = 'http://127.0.0.1:' + str(self.server.server_port)
    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()


class HostProviderTests(unittest.TestCase):
    def test_bad_native_arguments_and_oversized_batches_are_repairable_protocol_errors(self):
        call = {'function': {'name': 'write_file', 'arguments': {'path': 'partial.txt', 'content': 'must not run'}}}
        fixtures = [([{'message': {'tool_calls': [call] * 33}}], 'tool_batch'),
                    ([{'error': 'llama-server returned invalid tool call arguments for edit_file: invalid JSON'}], 'tool_arguments')]
        for frames, reason in fixtures:
            server = FakeModelServer(frames=frames)
            events = []
            try:
                config = {**DEFAULTS, 'provider': 'ollama', 'base_url': server.url}
                with self.assertRaises(ProviderError) as caught:
                    ModelClient(config, observer=events.append).complete([{'role':'user','content':'test'}],
                        threading.Event(), tools=tool_definitions())
                self.assertEqual(caught.exception.category, 'protocol')
                self.assertEqual(caught.exception.response, {'protocol_reason': reason})
                self.assertNotIn('content', caught.exception.response)
                self.assertTrue(any(e['type'] == 'provider_response' for e in events))
            finally:
                server.close()

    def test_protocol_classification_is_narrow_and_error_details_are_redacted_before_truncation(self):
        secret = 'private-test-provider-key'
        events = []
        config = {**DEFAULTS, 'provider':'hosted'}
        error = ProviderError('invalid tool call arguments ' + secret + 'x' * 3000)
        with patch('controller.providers.request_json', side_effect=error), self.assertRaises(ProviderError) as caught:
            ModelClient(config, secret, events.append).complete([{'role':'user','content':'test'}],
                threading.Event(), tools=tool_definitions())
        self.assertEqual(caught.exception.category, 'protocol')
        self.assertNotIn(secret, json.dumps(events))
        detail = next(e['data']['error_detail'] for e in events if e['type'] == 'call_end')
        self.assertIn('[REDACTED]', detail)
        self.assertLessEqual(len(detail), 2000)
        for protocol in ('json', 'native'):
            for text in ('service unavailable', 'authentication rejected', 'invalid tool call arguments' if protocol == 'json' else 'unknown backend error'):
                with patch('controller.providers.request_json', side_effect=ProviderError(text)), self.assertRaises(ProviderError) as caught:
                    ModelClient({**config,'protocol':protocol}).complete([{'role':'user','content':'test'}],
                        threading.Event(), tools=tool_definitions())
                self.assertEqual(caught.exception.category, 'connection')

    def test_journal_provenance_is_not_sent_to_either_model_protocol(self):
        for native in (False, True):
            server = FakeModelServer(hosted=True, native=native)
            try:
                config = {**DEFAULTS, 'provider': 'hosted', 'base_url': server.url,
                          'protocol': 'native' if native else 'json'}
                messages = [{'role': 'user', 'content': 'Use the supplied tool.', 'origin': 'human'}]
                ModelClient(config).complete(messages, threading.Event(), tools=tool_definitions() if native else None)
                self.assertEqual(server.payloads[0]['messages'][-1], {'role': 'user', 'content': 'Use the supplied tool.'})
                self.assertNotIn('origin', json.dumps(server.payloads[0]['messages']))
                self.assertEqual(messages[0]['origin'], 'human')
            finally:
                server.close()

    def run_client(self, server, hosted=False):
        config = dict(DEFAULTS)
        config.update(provider='hosted' if hosted else 'ollama', base_url=server.url, protocol='json', response_tokens=2048)
        return ModelClient(config).complete([{'role': 'user', 'content': 'test'}], threading.Event())

    def test_complete_ollama_stream_and_generation_budget(self):
        server = FakeModelServer()
        try:
            answer = self.run_client(server)
            self.assertEqual(parse_action(answer['content'])['status'], 'completed')
            self.assertEqual(server.payloads[0]['options']['num_predict'], 2048)
        finally: server.close()

    def test_incomplete_ollama_stream_is_discarded(self):
        server = FakeModelServer(cut_short=True)
        try:
            with self.assertRaises(ProviderError) as result: self.run_client(server)
            self.assertTrue(result.exception.response['incomplete'])
            self.assertIn('Ready', result.exception.response['raw_content'])
        finally: server.close()

    def test_hosted_response_and_cutoff_are_distinguished(self):
        for cut_short in (False, True):
            server = FakeModelServer(cut_short=cut_short, hosted=True)
            try:
                if cut_short:
                    with self.assertRaises(ProviderError): self.run_client(server, hosted=True)
                else:
                    self.assertEqual(parse_action(self.run_client(server, hosted=True)['content'])['status'], 'completed')
                self.assertEqual(server.payloads[0]['max_tokens'], 2048)
            finally: server.close()

    def test_native_calls_are_normalized_for_both_adapters(self):
        for hosted in (False, True):
            server = FakeModelServer(hosted=hosted, native=True)
            try:
                config = dict(DEFAULTS)
                config.update(provider='hosted' if hosted else 'ollama', base_url=server.url)
                tools = tool_definitions()
                response = ModelClient(config).complete([{'role':'user','content':'Create sample.txt'}], threading.Event(), tools=tools)
                decision = parse_action(response['content'])
                self.assertEqual(decision['action']['arguments']['path'], 'sample.txt')
                self.assertEqual(server.payloads[0]['tools'], tools)
                self.assertIn('read_section', [tool['function']['name'] for tool in server.payloads[0]['tools']])
                self.assertNotIn('format', server.payloads[0])
            finally: server.close()

    def test_native_inference_requires_explicit_seed_tool_definitions(self):
        for provider in ('ollama', 'hosted'):
            config = {**DEFAULTS, 'provider': provider}
            with self.subTest(provider=provider), self.assertRaisesRegex(ProviderError, 'supplied by the seed'):
                ModelClient(config).complete([{'role': 'user', 'content': 'test'}], threading.Event())

    def test_tool_history_has_matching_ids_and_orphans_remain_context(self):
        messages = [{'role':'assistant','content':json.dumps({'message':'Writing','action':{'tool':'write_file','arguments':{'path':'x','content':'hi'}}})},
                    {'role':'user','content':'ACTION RESULT\n' + json.dumps({'tool':'write_file','ok':True,'result':{'written':True}})}]
        wire = wire_messages(messages, False)
        self.assertEqual(wire[0]['tool_calls'][0]['id'], wire[1]['tool_call_id'])
        self.assertEqual(wire[1]['role'], 'tool')
        self.assertEqual(wire_messages(messages[1:], False)[0]['role'], 'user')

    def test_multiple_calls_are_ordered_and_plain_text_is_not_completion(self):
        call = {'function':{'name':'write_file','arguments':{'path':'x','content':'hi'}}}
        normalized = json.loads(normalize_tool_response('', [call, call]))
        self.assertEqual(len(normalized['actions']), 2)
        finish = {'function':{'name':'finish','arguments':{'message':'Done','status':'completed'}}}
        normalized = json.loads(normalize_tool_response('', [call, finish]))
        self.assertEqual(len(normalized['actions']), 1)
        self.assertTrue(normalized['deferred_finish'])
        for prose in ('All done.', 'Which filename?', ''):
            with self.subTest(prose=prose), self.assertRaisesRegex(ValueError, 'Call finish'):
                normalize_tool_response(prose, [])
            response = model_response(prose, [], True)
            self.assertEqual(response['raw_content'], prose)
            self.assertIn('Call finish', response['normalization_error'])
        decision = parse_action(normalize_tool_response('', [{'function': {'name': 'finish',
            'arguments': {'message': 'Which filename?', 'status': 'needs_input'}}}]))
        self.assertEqual(decision, {'message': 'Which filename?', 'status': 'needs_input'})
