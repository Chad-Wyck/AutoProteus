"""Browser leases: navigation hints are advisory, heartbeat expiry is the fallback."""
import re
import secrets
import threading
import time


class BrowserPresence:
    grace = 5
    expiry = 300

    def __init__(self, release, maintain, clock=time.monotonic):
        self.release, self.maintain, self.clock = release, maintain, clock
        self.lock = threading.RLock()
        self.tabs = {}
        self.seen = False
        self.absent_since = None
        self.released = False
        self.closed = threading.Event()
        self.thread = None
        self.legacy_seen = None

    def legacy_pulse(self):
        # An already-open older UI does not send explicit heartbeats yet. Its
        # authenticated browser polling still counts until that tab is refreshed.
        with self.lock:
            self.legacy_seen = self.clock()
            self.seen = True
            self.absent_since = None
            self.released = False

    def _legacy_present(self, now):
        return self.legacy_seen is not None and now-self.legacy_seen < self.expiry

    def pulse(self, identifier, sequence, closing=False):
        if (not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9-]{16,64}', identifier)
                or type(sequence) is not int or not 0 <= sequence < 2**53 or type(closing) is not bool):
            raise ValueError('Invalid browser heartbeat')
        with self.lock:
            previous = self.tabs.get(identifier)
            if previous and sequence <= previous['sequence']:
                return previous['watch']
            now = self.clock()
            self.tabs = {key:value for key,value in self.tabs.items() if now-value['seen'] < self.expiry*2}
            if previous is None and len(self.tabs) >= 128:
                raise ValueError('Too many open AutoProteus pages')
            self.seen = True
            entry = previous or {'watch':secrets.token_urlsafe(24), 'connection':None}
            entry.update(sequence=sequence, seen=now, closing=closing)
            self.tabs[identifier] = entry
            if not closing:
                self.absent_since = None
                self.released = False
            else:
                self._note_absence(now)
            # Keep tombstones briefly so a delayed heartbeat cannot undo close.
            self.tabs = {key:value for key,value in self.tabs.items() if now-value['seen'] < self.expiry*2}
            return entry['watch']

    def open_watch(self, identifier, token):
        with self.lock:
            entry = self.tabs.get(identifier)
            if (not isinstance(token, str) or not entry or self.clock()-entry['seen'] >= self.expiry
                    or not secrets.compare_digest(entry['watch'], token)):
                raise ValueError('Reconnect this browser page')
            connection = object()
            entry.update(connection=connection, seen=self.clock(), closing=False)
            self.absent_since = None
            self.released = False
            return connection

    def watch_alive(self, identifier, connection):
        with self.lock:
            entry = self.tabs.get(identifier)
            if not entry or entry['connection'] is not connection or entry['closing']:
                return False
            entry['seen'] = self.clock()
            return True

    def close_watch(self, identifier, connection):
        with self.lock:
            entry = self.tabs.get(identifier)
            if entry and entry['connection'] is connection:
                entry.update(connection=None, closing=True, seen=self.clock())
                self._note_absence(self.clock())

    def _note_absence(self, now):
        if (self.absent_since is None and not self._legacy_present(now)
                and not any(not item['closing'] and now-item['seen'] < self.expiry for item in self.tabs.values())):
            self.absent_since = now

    def tick(self):
        with self.lock:
            now = self.clock()
            self.tabs = {key:value for key,value in self.tabs.items() if now-value['seen'] < self.expiry*2}
            present = self._legacy_present(now) or any(not item['closing'] and now-item['seen'] < self.expiry for item in self.tabs.values())
            if present:
                self.absent_since = None
            elif self.seen:
                if self.absent_since is None:
                    self.absent_since = now
                if now-self.absent_since >= self.grace and not self.released:
                    # Serialize a returning page with cleanup. Once it receives
                    # its next pulse reply it can safely start another run.
                    self.release()
                    self.released = True
        self.maintain()

    def public(self):
        with self.lock:
            now = self.clock()
            return {'tabs':int(self._legacy_present(now)) + sum(not item['closing'] and now-item['seen'] < self.expiry for item in self.tabs.values()),
                    'release_pending':self.absent_since is not None and not self.released,
                    'released':self.released}

    def start(self):
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while not self.closed.wait(1):
            try:
                self.tick()
            except Exception:
                # Retry on the next tick; a temporarily unreachable engine must
                # not kill the app's resource monitor.
                pass

    def close(self):
        self.closed.set()
        if self.thread:
            self.thread.join(timeout=10)
