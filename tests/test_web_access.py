"""Exercise the protected web boundary without contacting public services."""
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from autoproteus.providers import tool_definitions
from autoproteus.tools import Workspace
from controller.config import Settings
from controller.errors import Cancelled, IsolationError
from controller.isolation import Broker
from controller.storage import Store
from controller.web_access import WebAccess, WebError, destination, public_address, resolve
from test_seed import temporary_directory


def response(data=b'public response', status=200, headers=None):
    value = Mock(status=status)
    value.getheaders.return_value = list((headers or {}).items())
    value.getheader.side_effect = lambda name: (headers or {}).get(name)
    value.read1.side_effect = [data, b'']
    return value


class WebPolicyTests(unittest.TestCase):
    def test_private_reserved_transition_and_metadata_addresses_are_rejected(self):
        for ip in ('127.0.0.1', '0.0.0.0', '10.2.3.4', '172.16.1.2', '192.168.1.1',
                   '169.254.169.254', '100.100.100.200', '100.64.0.1', '198.18.0.1',
                   '224.0.0.1', '255.255.255.255', '168.63.129.16', '::', '::1',
                   'fd00::1', 'fe80::1', 'ff02::1', '::ffff:127.0.0.1',
                   '64:ff9b::7f00:1', '2002:7f00:1::', '2001:db8::1'):
            with self.subTest(ip=ip):
                self.assertFalse(public_address(ip))
        for ip in ('1.1.1.1', '8.8.8.8', '2606:4700:4700::1111'):
            self.assertTrue(public_address(ip), ip)

    def test_url_parsing_cannot_select_local_protocols_ports_or_credentials(self):
        for url in ('file:///etc/passwd', 'ftp://example.com', 'https://user:pass@example.com',
                    'http://example.com:47831', 'https://example.com:0', 'https://example.com:80',
                    'http://localhost', 'http://a.local', 'http://metadata.google.internal',
                    'http://[fe80::1%25eth0]', 'http://example.com\\@127.0.0.1',
                    'https://example.com/\nHost:localhost', 'http://example.com/a b',
                    'https://[broken', '//example.com'):
            with self.subTest(url=url), self.assertRaises(WebError):
                destination(url)
        self.assertEqual(destination('https://example.com/é?q=é#fragment')[3:],
                         ('/%C3%A9?q=%C3%A9', 'https://example.com/%C3%A9?q=%C3%A9'))

    def test_all_dns_answers_must_be_public_including_numeric_aliases(self):
        answer = lambda ip: (socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, 80))
        for answers in ([answer('127.0.0.1')], [answer('1.1.1.1'), answer('10.0.0.1')], []):
            with patch('controller.web_access.socket.getaddrinfo', return_value=answers), self.assertRaises(WebError):
                resolve('2130706433', 80)
        with patch('controller.web_access.socket.getaddrinfo', return_value=[answer('1.1.1.1')]):
            self.assertEqual(resolve('example.com', 80), ['1.1.1.1'])

    def fetch_mock(self, replies, url='https://example.com', request=None):
        access = WebAccess(True, threading.Event())
        connection = Mock()
        connection.sock = None
        connection.getresponse.side_effect = replies
        with patch('controller.web_access.resolve', return_value=['1.1.1.1']), \
                patch('controller.web_access.http.client.HTTPSConnection', return_value=connection) as factory:
            result = access.request(request or {'url': url})
        return result, access, connection, factory

    def test_api_methods_statuses_and_binary_body_are_preserved(self):
        result, access, connection, factory = self.fetch_mock([response(b'\x00\xff', 422)], request={
            'url': 'https://example.com/api', 'method': 'POST',
            'headers': {'Authorization': 'Bearer explicit-user-key', 'Content-Type': 'application/json'},
            'body': '{"name":"é"}'})
        self.assertEqual(result['status'], 422)
        self.assertEqual(base64.b64decode(result['data']), b'\x00\xff')
        self.assertEqual(access.received, 2)
        args = connection.request.call_args
        self.assertEqual(args.args, ('POST', '/api'))
        self.assertEqual(args.kwargs['body'], '{"name":"é"}'.encode())
        self.assertEqual(args.kwargs['headers']['authorization'], 'Bearer explicit-user-key')
        self.assertEqual(factory.call_args.args, ('example.com', 443))
        self.assertNotIn('context', factory.call_args.kwargs)  # Normal certificate verification.

    def test_redirect_revalidates_and_never_replays_writes_or_leaks_cross_origin_headers(self):
        result, _, connection, _ = self.fetch_mock([
            response(status=302, headers={'Location': 'https://other.example/result'}), response()], request={
                'url': 'https://example.com', 'headers': {'Authorization': 'secret', 'Cookie': 'secret',
                                                        'X-Api-Key': 'secret', 'Accept': 'text/plain'}})
        headers = connection.request.call_args_list[-1].kwargs['headers']
        self.assertEqual(result['url'], 'https://other.example/result')
        self.assertEqual(headers['accept'], 'text/plain')
        self.assertFalse({'authorization', 'cookie', 'x-api-key'} & headers.keys())
        result, _, connection, _ = self.fetch_mock([
            response(status=307, headers={'Location': 'https://other.example/'})], request={
                'url': 'https://example.com', 'method': 'POST', 'body': 'do something'})
        self.assertEqual(result['status'], 307)
        self.assertEqual(connection.request.call_count, 1)
        result, _, connection, _ = self.fetch_mock([
            response(status=302, headers={'Location': 'http://other.example/'})])
        self.assertIn('unencrypted', result['error'])
        self.assertEqual(connection.request.call_count, 1)

    def test_redirect_to_private_dns_is_blocked_before_second_connection(self):
        access = WebAccess(True, threading.Event())
        connection = Mock(sock=None)
        connection.getresponse.return_value = response(status=302, headers={'Location': 'https://127.0.0.1/'})
        with patch('controller.web_access.resolve', side_effect=[['1.1.1.1'], WebError('private blocked')]) as dns, \
                patch('controller.web_access.http.client.HTTPSConnection', return_value=connection):
            result = access.request({'url': 'https://example.com'})
        self.assertIn('private', result['error'])
        self.assertEqual(dns.call_count, 2)
        self.assertEqual(connection.request.call_count, 1)

    def test_connection_uses_validated_ip_not_the_hostname_again(self):
        connection, sock = Mock(sock=None), Mock()
        connection.getresponse.return_value = response()
        connection.request.side_effect = lambda *args, **kwargs: connection._create_connection(('example.com', 443), 10)
        with patch('controller.web_access.resolve', return_value=['1.1.1.1']) as dns, \
                patch('controller.web_access.http.client.HTTPSConnection', return_value=connection), \
                patch('controller.web_access.socket.create_connection', return_value=sock) as connect:
            result = WebAccess(True, threading.Event()).request({'url': 'https://example.com'})
        self.assertEqual(result['status'], 200)
        self.assertEqual(connect.call_args.args, (('1.1.1.1', 443),))
        self.assertEqual(dns.call_count, 1)
        sock.shutdown.assert_called()

    def test_request_headers_body_and_unknown_fields_are_bounded(self):
        bad = [{'url': 'https://example.com', 'headers': {'Host': 'localhost'}},
               {'url': 'https://example.com', 'headers': {'Proxy-Authorization': 'secret'}},
               {'url': 'https://example.com', 'headers': {'X': 'ok\r\nHost:localhost'}},
               {'url': 'https://example.com', 'headers': {'X': '1', 'x': '2'}},
               {'url': 'https://example.com', 'headers': {'X': 'x' * 8193}},
               {'url': 'https://example.com', 'body': 'x'},
               {'url': 'https://example.com', 'method': 'POST', 'body': 'x' * 65537},
               {'url': 'https://example.com', 'method': 'POST', 'body': '\ud800'},
               {'url': 'https://example.com', 'method': 'CONNECT'},
               {'url': 'https://example.com', 'verify_tls': False}, None]
        with patch('controller.web_access.resolve') as dns:
            for request in bad:
                with self.subTest(request=str(request)[:100]):
                    self.assertIn('error', WebAccess(True, threading.Event()).request(request))
            dns.assert_not_called()

    def test_oversize_responses_and_run_budgets_include_failed_reads(self):
        with patch('controller.web_access.MAX_RESPONSE', 4):
            result, access, _, _ = self.fetch_mock([response(b'12345')])
        self.assertIn('limit', result['error'])
        self.assertEqual(access.received, 5)
        for field, limit in (('requests', 200), ('received', 32 * 1024 * 1024)):
            access = WebAccess(True, threading.Event())
            setattr(access, field, limit)
            with patch('controller.web_access.resolve') as dns:
                self.assertIn('allowance', access.request({'url': 'https://example.com'})['error'])
                dns.assert_not_called()

    def test_redirect_loops_and_large_response_headers_stop_within_fixed_limits(self):
        result, _, connection, _ = self.fetch_mock([
            response(status=302, headers={'Location': '/again'}) for _ in range(6)])
        self.assertIn('redirects', result['error'])
        self.assertEqual(connection.request.call_count, 6)
        result, _, _, _ = self.fetch_mock([response(headers={'X-Large': 'x' * 16385})])
        self.assertIn('headers', result['error'])

    def test_real_socket_stop_interrupts_partial_http_headers(self):
        entered, release = threading.Event(), threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.wfile.write(b'HTTP/1.1 200 OK\r\nX-Incomplete: ')
                self.wfile.flush()
                entered.set()
                release.wait(5)
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        original, cancel, outcome = socket.create_connection, threading.Event(), []
        def run():
            try:
                outcome.append(WebAccess(True, cancel).request({'url': 'http://example.com'}))
            except Cancelled:
                outcome.append('cancelled')
        try:
            with patch('controller.web_access.resolve', return_value=['1.1.1.1']), \
                    patch('controller.web_access.socket.create_connection', side_effect=lambda address, **kwargs: original(server.server_address, **kwargs)):
                worker = threading.Thread(target=run)
                worker.start()
                self.assertTrue(entered.wait(2))
                cancel.set()
                worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertEqual(outcome, ['cancelled'])
        finally:
            cancel.set()
            release.set()
            server.shutdown()
            server.server_close()
            thread.join(2)

    def test_disabled_access_cancel_and_deadline_never_start_dns(self):
        with patch('controller.web_access.resolve') as dns:
            access = WebAccess(False, threading.Event())
            self.assertIn('disabled', access.request({'url': 'https://example.com'})['error'])
            access = WebAccess(True, threading.Event(), time.monotonic() - 1)
            self.assertIn('deadline', access.request({'url': 'https://example.com'})['error'])
            access.cancel.set()
            with self.assertRaises(Cancelled):
                access.request({'url': 'https://example.com'})
            dns.assert_not_called()

    def test_stop_and_total_deadline_interrupt_a_stalled_dns_worker(self):
        for stop in (True, False):
            entered, release = threading.Event(), threading.Event()
            cancel = threading.Event()
            access = WebAccess(True, cancel)
            outcome = []
            def dns(*args):
                entered.set()
                release.wait(5)
                return ['1.1.1.1']
            def run():
                try:
                    outcome.append(access.request({'url': 'https://example.com'}))
                except Cancelled:
                    outcome.append('cancelled')
            with patch('controller.web_access.resolve', side_effect=dns), patch('controller.web_access.TIMEOUT', .2), \
                    patch('controller.web_access.socket.create_connection') as connect:
                thread = threading.Thread(target=run)
                thread.start()
                self.assertTrue(entered.wait(1))
                if stop:
                    cancel.set()
                thread.join(2)
                self.assertFalse(thread.is_alive())
                self.assertEqual(outcome[0], 'cancelled') if stop else self.assertIn('timed out', outcome[0]['error'])
                release.set()
                # Resolve returns, but stopped workers cannot open a connection.
                time.sleep(.05)
                connect.assert_not_called()

    def test_real_http_round_trip_uses_explicit_headers_ignores_proxy_and_preserves_errors(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append((self.path, dict(self.headers), self.rfile.read(int(self.headers['Content-Length']))))
                self.send_response(418)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"actual":"response"}')
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        original = socket.create_connection
        def route(address, **kwargs):
            self.assertEqual(address, ('1.1.1.1', 80))
            return original(server.server_address, **kwargs)
        try:
            # Only this test's transport is rerouted to its fixture. Production
            # DNS validation remains covered separately and never allows it.
            with patch('controller.web_access.resolve', return_value=['1.1.1.1']), \
                    patch('controller.web_access.socket.create_connection', side_effect=route), \
                    patch.dict('os.environ', {'HTTP_PROXY': 'http://secret@127.0.0.1:1'}):
                value = WebAccess(True, threading.Event()).request({
                    'url': 'http://example.com/api', 'method': 'POST', 'body': 'hello', 'headers': {'X-User': 'explicit'}})
            self.assertEqual(value['status'], 418)
            self.assertEqual(base64.b64decode(value['data']), b'{"actual":"response"}')
            self.assertEqual(seen[0][2], b'hello')
            self.assertEqual(seen[0][1]['Host'], 'example.com')
            self.assertEqual(seen[0][1]['x-user'], 'explicit')
            self.assertNotIn('Proxy-Authorization', seen[0][1])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)


class WebBridgeTests(unittest.TestCase):
    def test_seed_saves_exact_binary_bytes_rejects_escape_and_previews_untrusted_text(self):
        def request(value):
            return {'url': value['url'], 'status': 200, 'headers': {}, 'bytes': 3,
                    'data': base64.b64encode(b'\x00\xffA').decode()}
        with temporary_directory() as directory, patch.dict(sys.modules, {'autoproteus_web': SimpleNamespace(request=Mock(side_effect=request))}):
            workspace = Workspace(Path(directory))
            value = workspace.execute('web_request', {'url': 'https://example.com', 'path': 'downloads/data.bin'})
            self.assertTrue(value['saved'])
            self.assertEqual((workspace.root / 'downloads/data.bin').read_bytes(), b'\x00\xffA')
            value = workspace.execute('web_request', {'url': 'https://example.com'})
            self.assertIn('untrusted', value['notice'])
            self.assertIn('content', value)
            self.assertNotIn('data', value)
            bridge = sys.modules['autoproteus_web'].request
            bridge.reset_mock()
            for path in ('../outside.bin', str(Path(directory).parent / 'outside.bin')):
                with self.assertRaises(ValueError):
                    workspace.execute('web_request', {'url': 'https://example.com', 'path': path})
            bridge.assert_not_called()
        self.assertIn('web_request', {tool['function']['name'] for tool in tool_definitions()})

    def test_host_permission_and_frame_validation_cannot_be_changed_by_guest(self):
        with temporary_directory() as directory:
            settings = Settings(Path(directory))
            self.assertTrue(settings.values['internet'])
            settings.update({'internet': False})
            self.assertFalse(Settings(Path(directory)).values['internet'])
            with self.assertRaises(ValueError):
                settings.update({'internet': 'true'})
            store = Store(Path(directory) / 'sessions')
            session = store.create('Research', 'demo', 'fixture')
            broker = Broker(store, session, Mock(), settings.values, threading.Event())
            frame = {'op': 'web', 'request': {'url': 'https://example.com'}}
            self.assertIn('disabled', broker.handle(frame)['error'])
            for bad in ({**frame, 'internet': True}, {'op': 'configure', 'internet': True}):
                with self.assertRaises(IsolationError):
                    broker.handle(bad)
            self.assertIn('disabled', broker.handle(frame)['error'])

    def test_default_on_preserves_saved_choices_and_rejects_invalid_values(self):
        with temporary_directory() as directory:
            root = Path(directory)
            cases = [({'model': 'old-model'}, True), ({'internet': True}, True),
                     ({'internet': False}, False), ({'internet': 'true'}, False),
                     ({'internet': None}, False), ({'internet': 1}, False)]
            for saved, expected in cases:
                (root / 'settings.json').write_text(json.dumps(saved), encoding='utf-8')
                settings = Settings(root)
                self.assertEqual(settings.values['internet'], expected)
                self.assertEqual(settings.preview({'temperature': .5})['internet'], expected)
            settings.update({'internet': True})
            self.assertTrue(Settings(root).values['internet'])
            settings.update({'temperature': .4})
            self.assertTrue(Settings(root).values['internet'])
            settings.update({'internet': False})
            self.assertFalse(Settings(root).values['internet'])

    def test_missing_permission_in_a_legacy_broker_config_is_denied(self):
        with temporary_directory() as directory:
            settings = Settings(Path(directory))
            config = {key: value for key, value in settings.values.items() if key != 'internet'}
            store = Store(Path(directory) / 'sessions')
            session = store.create('Legacy session', 'demo', 'fixture')
            broker = Broker(store, session, Mock(), config, threading.Event())
            with patch('controller.web_access.resolve') as dns:
                self.assertIn('disabled', broker.handle({'op': 'web', 'request': {'url': 'https://example.com'}})['error'])
                dns.assert_not_called()


if __name__ == '__main__':
    unittest.main()
