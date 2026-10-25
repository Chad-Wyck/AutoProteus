"""Public HTTP(S) capability. Destination and resource policy stay on the host."""
from __future__ import annotations

import base64
import http.client
import ipaddress
import queue
import re
import socket
import threading
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit

from .errors import Cancelled

MAX_RESPONSE = 2 * 1024 * 1024
MAX_BODY = 64 * 1024
MAX_REQUESTS = 200
MAX_TOTAL = 32 * 1024 * 1024
TIMEOUT = 20
WORKERS = threading.BoundedSemaphore(4)
METHODS = {'GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'}
BLOCKED_HEADERS = {'host', 'connection', 'content-length', 'transfer-encoding', 'upgrade',
                   'te', 'trailer', 'accept-encoding', 'proxy-authorization', 'proxy-connection'}


class WebError(ValueError):
    pass


def destination(url):
    if (not isinstance(url, str) or len(url) > 8192 or '\\' in url or
            any(ord(char) < 33 or ord(char) == 127 for char in url)):
        raise WebError('Use an absolute public HTTP or HTTPS URL without spaces or control characters.')
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').encode('idna').decode('ascii').lower().rstrip('.')
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == 'https' else 80)
    except (ValueError, UnicodeError):
        raise WebError('Invalid web URL.') from None
    if (parsed.scheme not in ('http', 'https') or not host or parsed.username is not None or
            parsed.password is not None or '%' in host or
            port != (443 if parsed.scheme == 'https' else 80)):
        raise WebError('Use public HTTP on port 80 or HTTPS on port 443, without URL credentials.')
    if host == 'localhost' or host.endswith(('.localhost', '.local', '.internal', '.lan', '.home', '.localdomain')):
        raise WebError('Local and private network destinations are unavailable.')
    path = quote(parsed.path or '/', safe="/%:@!$&'()*+,;=-._~")
    query = quote(parsed.query, safe="/%?:@!$&'()*+,;=-._~")
    target = path + ('?' + query if query else '')
    authority = '[' + host + ']' if ':' in host else host
    return parsed.scheme, host, port, target, urlunsplit((parsed.scheme, authority, path, query, ''))


def public_address(value):
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return False
    if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_loopback or ip.is_link_local:
        return False
    if str(ip) == '168.63.129.16':  # Azure host infrastructure virtual address.
        return False
    if ip.version == 6:
        # Do not let transition/translation addresses tunnel to private IPv4.
        if ip.ipv4_mapped or ip.sixtofour or ip.teredo:
            return False
        if any(ip in ipaddress.ip_network(prefix) for prefix in ('64:ff9b::/96', '64:ff9b:1::/48')):
            return False
    return True


def resolve(host, port):
    try:
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise WebError('Could not resolve the public website.') from None
    if not answers or any(not public_address(item[4][0]) for item in answers):
        raise WebError('Local, private and reserved network destinations are unavailable.')
    return list(dict.fromkeys(item[4][0] for item in answers))


def validate_request(request):
    if not isinstance(request, dict) or set(request) - {'url', 'method', 'headers', 'body'} or 'url' not in request:
        raise WebError('Supply url and optional method, headers and UTF-8 body only.')
    destination(request['url'])
    method, headers, body = request.get('method', 'GET'), request.get('headers', {}), request.get('body', '')
    if not isinstance(method, str) or method not in METHODS:
        raise WebError('Use GET, HEAD, POST, PUT, PATCH, DELETE or OPTIONS.')
    try:
        encoded = body.encode('utf-8') if isinstance(body, str) else None
    except UnicodeError:
        encoded = None
    if encoded is None or len(encoded) > MAX_BODY:
        raise WebError('Request body must be UTF-8 text of at most 64 KiB.')
    if method in ('GET', 'HEAD') and body:
        raise WebError('GET and HEAD requests cannot include a body.')
    if not isinstance(headers, dict) or len(headers) > 32:
        raise WebError('Supply at most 32 request headers.')
    checked = {}
    for name, value in headers.items():
        if (not isinstance(name, str) or not re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) or
                name.lower() in BLOCKED_HEADERS or name.lower() in checked or
                not isinstance(value, str) or any(ord(char) < 32 or ord(char) > 126 for char in value)):
            raise WebError('Invalid or reserved request header.')
        checked[name.lower()] = value
    if sum(len(key) + len(value) for key, value in checked.items()) > 8192:
        raise WebError('Request headers exceed 8 KiB.')
    return method, checked, encoded


class WebAccess:
    def __init__(self, enabled, cancel, deadline=None):
        self.enabled, self.cancel, self.deadline = enabled is True, cancel, deadline
        self.requests, self.received = 0, 0
        self.usage_lock = threading.Lock()

    def request(self, request):
        if self.cancel.is_set():
            raise Cancelled()
        if not self.enabled:
            return {'error': 'Internet access is disabled in Settings. Enable it before the next run.'}
        self.requests += 1
        if self.requests > MAX_REQUESTS or self.received >= MAX_TOTAL:
            return {'error': 'Web allowance reached: 200 requests or 32 MiB per run. Resume for a fresh allowance.'}
        try:
            method, headers, body = validate_request(request)
        except WebError as error:
            return {'error': str(error)}
        end = min(time.monotonic() + TIMEOUT, self.deadline or float('inf'))
        if time.monotonic() >= end:
            return {'error': 'Web request deadline reached.'}
        if not WORKERS.acquire(blocking=False):
            return {'error': 'Web connections are busy. Try again shortly.'}
        result, stopped, sockets, guard = queue.Queue(maxsize=1), threading.Event(), [], threading.Lock()

        def track(sock):
            with guard:
                if stopped.is_set():
                    sock.close()
                    raise WebError('Web request stopped.')
                sockets.append(sock)
            return sock

        def fetch():
            try:
                value = self._fetch(request['url'], method, headers, body, end, stopped, track)
            except WebError as error:
                value = {'error': str(error)}
            except Exception:
                # Never reflect host paths, environment, proxy settings or TLS diagnostics.
                value = {'error': 'Web request failed. Check the URL, connectivity and HTTPS certificate. '
                                  'A sent request may already have taken effect; inspect before retrying.'}
            finally:
                WORKERS.release()
            result.put(value)

        threading.Thread(target=fetch, daemon=True).start()
        try:
            while True:
                if self.cancel.is_set():
                    raise Cancelled()
                if time.monotonic() >= end:
                    return {'error': 'Web request timed out; a sent request may already have taken effect. Inspect before retrying.'}
                try:
                    return result.get(timeout=min(.05, max(.001, end - time.monotonic())))
                except queue.Empty:
                    pass
        finally:
            stopped.set()
            with guard:
                for sock in sockets:
                    try:
                        sock.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    sock.close()

    def _fetch(self, url, method, headers, body, end, stopped, track):
        for hop in range(6):
            scheme, host, port, target, clean_url = destination(url)
            addresses = resolve(host, port)
            connection = (http.client.HTTPSConnection if scheme == 'https' else http.client.HTTPConnection)(
                host, port, timeout=max(.001, end - time.monotonic()))

            def connect(address, timeout, source_address=None):
                if stopped.is_set() or time.monotonic() >= end:
                    raise WebError('Web request deadline reached.')
                # Connect to the validated IP itself: no second DNS lookup/rebinding.
                # HTTPSConnection still verifies TLS/SNI against the original hostname.
                for ip in addresses:
                    if stopped.is_set() or time.monotonic() >= end:
                        raise WebError('Web request deadline reached.')
                    try:
                        return track(socket.create_connection((ip, port), timeout=min(timeout, 5)))
                    except OSError:
                        continue
                raise WebError('Could not connect to the public website.')

            connection._create_connection = connect
            try:
                actual = {'user-agent': 'AutoProteus/0.8', 'accept-encoding': 'identity', 'connection': 'close', **headers}
                connection.request(method, target, body=body or None, headers=actual)
                if connection.sock:
                    track(connection.sock)  # Also close the wrapped TLS socket on Stop.
                response = connection.getresponse()
                pairs = response.getheaders()
                if sum(len(key) + len(value) for key, value in pairs) > 16384:
                    raise WebError('Response headers exceed 16 KiB.')
                location = response.getheader('Location')
                if method in ('GET', 'HEAD') and response.status in (301, 302, 303, 307, 308) and location:
                    if hop == 5:
                        raise WebError('Too many web redirects.')
                    next_url = urljoin(clean_url, location)
                    next_destination = destination(next_url)
                    if scheme == 'https' and next_destination[0] != 'https':
                        raise WebError('HTTPS redirects to unencrypted HTTP are blocked.')
                    if (scheme, host, port) != next_destination[:3]:
                        headers = {key: value for key, value in headers.items()
                                   if key in ('accept', 'accept-language', 'user-agent')}
                    url = next_url
                    continue
                data = bytearray()
                while True:
                    if stopped.is_set() or time.monotonic() >= end:
                        raise WebError('Web request deadline reached.')
                    with self.usage_lock:
                        remaining = min(MAX_RESPONSE - len(data), MAX_TOTAL - self.received)
                    chunk = response.read1(min(65536, max(1, remaining + 1)))
                    with self.usage_lock:
                        self.received += len(chunk)
                        over_budget = self.received > MAX_TOTAL
                    if not chunk:
                        break
                    data.extend(chunk)
                    if len(data) > MAX_RESPONSE or over_budget:
                        raise WebError('Web response exceeds the 2 MiB file limit or remaining run allowance.')
                return {'url': clean_url, 'status': response.status,
                        'headers': {key.lower(): value for key, value in pairs},
                        'bytes': len(data), 'data': base64.b64encode(data).decode('ascii')}
            finally:
                connection.close()
