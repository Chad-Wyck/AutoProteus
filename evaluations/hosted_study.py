"""Explicit paid-study opt-in, host-only credentials and a conservative spend cap."""
from contextlib import contextmanager
import json
import math
from pathlib import Path
import threading

from controller.config import protect
from controller.providers import ProviderError
from controller.storage import atomic_json
from run_budget import BudgetModelClient

_key = ''
_spend = None


def permitted(config):
    return (config.get('provider') == 'hosted' and
        config.get('base_url', '').rstrip('/') == 'https://api.openai.com/v1' and
        config.get('api_format') == 'responses')


class Spend:
    # Conservative estimate: all input is charged at the documented cache-write
    # rate, even cached reads. Output totals already include reasoning tokens.
    def __init__(self, path, limit):
        if not math.isfinite(limit) or limit <= 0:
            raise ValueError('API spend cap must be a positive finite amount')
        self.path, self.limit = Path(path), limit
        previous = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.charged = previous.get('conservative_usd', 0)
        self.calls = previous.get('calls', [])
        self.reserved, self.lock = 0, threading.Lock()

    def reserve(self, config):
        if config['model'] != 'gpt-6.1-sol' or config['context_tokens'] > 131072:
            raise ValueError('Paid-study pricing guard currently qualifies GPT-6.1 Sol up to 128K only')
        value = (config['context_tokens'] * 2.5 + config['response_tokens'] * 10) / 1000000
        with self.lock:
            if self.charged + self.reserved + value > self.limit:
                raise ProviderError('The study reached its conservative API spend cap; no further request was sent.', category='budget')
            self.reserved += value
        return value

    def close(self, reservation, sent, usage):
        complete = (isinstance(usage, dict) and all(type(usage.get(key)) is int and usage[key] >= 0
                    for key in ('input_tokens', 'output_tokens')))
        sent = bool(sent or complete)
        cost = ((usage['input_tokens'] * 2.5 + usage['output_tokens'] * 10) / 1000000
                if sent and complete else reservation if sent else 0)
        with self.lock:
            self.reserved -= reservation
            self.charged += cost
            self.calls.append({'sent': sent, 'usage': usage if complete else None,
                'usage_complete': complete, 'conservative_usd': cost})
            atomic_json(self.path, {'limit_usd': self.limit, 'conservative_usd': self.charged,
                'scope': 'Upper cost estimate, not a billing receipt; cache discounts not subtracted. '
                         'Unknown sent calls charged the full reserved amount. Input $2.50/M, output $10/M.',
                'calls': self.calls})


class PaidClient(BudgetModelClient):
    def complete(self, *args, **kwargs):
        reservation = _spend.reserve(self.config)
        observed = {'sent': False, 'usage': {}}
        downstream = self._budget_observer
        def record(event):
            if event['type'] in ('provider_request', 'provider_response'): observed['sent'] = True
            if event['type'] == 'call_end': observed['usage'] = event['data'].get('usage', {})
            if downstream: downstream(event)
        self._budget_observer = record
        try:
            return super().complete(*args, **kwargs)
        finally:
            self._budget_observer = downstream
            _spend.close(reservation, observed['sent'], observed['usage'])


def client(config, **kwargs):
    if permitted(config):
        if not _key or _spend is None:
            raise ValueError('Hosted studies require explicit authorization and an unlocked host credential')
        return PaidClient(config, key=_key, **kwargs)
    return BudgetModelClient(config, **kwargs)


@contextmanager
def connection(plan, args, output):
    global _key, _spend
    remote = [profile['config'] for profile in plan['profiles'] if
              profile['config'].get('base_url', '').startswith('https://api.openai.com/')]
    if not remote or getattr(args, 'check_only', False):
        yield
        return
    if not plan.get('allow_hosted') or not getattr(args, 'allow_hosted', False) or not all(permitted(c) for c in remote):
        raise ValueError('Paid API runs require --allow-hosted at both preparation and execution')
    key_file = getattr(args, 'api_key_file', None)
    if not key_file:
        raise ValueError('Supply a Windows-encrypted --api-key-file; never put a key in a plan or argument')
    try:
        _key = protect(Path(key_file).read_bytes(), decrypt=True).decode()
        if not _key.strip():
            raise ValueError('Empty encrypted key')
        _spend = Spend(Path(output) / 'api-spend.json', args.max_api_cost_usd)
        yield
    finally:
        _key, _spend = '', None
