"""Host-only experiment budgets; normal app limits and editable seed stay unchanged."""
import threading

from controller.providers import ModelClient, ProviderError

DEFAULT_OUTPUT_TOKENS = 65536
DEFAULT_TASK_SECONDS = 1800


def output_tokens(usage):
    # These provider totals include reasoning. Detail fields are subsets, so
    # adding reasoning_tokens again would double-charge it.
    if isinstance(usage, dict):
        for key in ('eval_count', 'completion_tokens', 'output_tokens'):
            if type(usage.get(key)) is int and usage[key] >= 0:
                return usage[key]
    return None


class GeneratedTokenBudget:
    def __init__(self, limit=DEFAULT_OUTPUT_TOKENS):
        if type(limit) is not int or limit < 1:
            raise ValueError('The generated-token budget must be a positive integer')
        self.limit, self.charged, self.reported, self.fallback_calls = limit, 0, 0, 0
        self.pending_calls = 0
        self._charges = {}
        self.lock = threading.Lock()

    def allowance(self, requested):
        with self.lock:
            left = self.limit - self.charged
            if left <= 0:
                raise ProviderError('Experiment generated-token budget exhausted; saved candidate remains available.', category='budget')
            return min(requested, left)

    def charge(self, usage, sent, allowance, *, call_id=None, pending=False):
        value = output_tokens(usage)
        with self.lock:
            # Updating the same cancelled call must not charge twice. A worker
            # still preparing a request may dispatch after its caller stopped;
            # reserve its whole allowance until dispatch/no-dispatch is known.
            key = call_id if call_id is not None else object()
            old = self._charges.get(key, (0, 0, 0, 0))
            new = (value if value is not None else allowance if sent or pending else 0,
                   value if value is not None else 0,
                   int(value is None and sent), int(value is None and pending and not sent))
            self.charged += new[0] - old[0]
            self.reported += new[1] - old[1]
            self.fallback_calls += new[2] - old[2]
            self.pending_calls += new[3] - old[3]
            self._charges[key] = new

    def summary(self):
        with self.lock:
            return {'limit': self.limit, 'charged_output_tokens': self.charged,
                    'reported_output_tokens': self.reported, 'unmeasured_sent_calls': self.fallback_calls,
                    'reserved_output_tokens': self.charged - self.reported,
                    'pending_dispatch_calls': self.pending_calls,
                    'usage_complete': self.fallback_calls == self.pending_calls == 0,
                    'exhausted': self.charged >= self.limit}


class TokenBudgetMixin:
    """Compose with the production client, including its normal wire adapter."""
    def __init__(self, *args, token_budget=None, observer=None, **kwargs):
        self.token_budget = token_budget or GeneratedTokenBudget()
        self._budget_observer = observer
        self._budget_calls = {}
        self._current_budget_call = None
        self._budget_lock = threading.Lock()
        super().__init__(*args, observer=self._observe_budget, **kwargs)

    def _charge_call(self, call):
        self.token_budget.charge(call['usage'], call['sent'], call['allowance'],
            call_id=call['identity'], pending=call['started'] and not call['transport_finished'])

    def _observe_budget(self, event):
        identity = event['call_id']
        with self._budget_lock:
            if event['type'] == 'call_start':
                self._budget_calls[identity] = self._current_budget_call
            call = self._budget_calls.get(identity)
            observer = call['observer'] if call is not None else self._budget_observer
            if call is not None:
                if event['type'] == 'call_start': call['started'] = True
                if event['type'] == 'provider_request': call['sent'] = True
                if event['type'] == 'transport_end': call['transport_finished'] = True
                if event['type'] == 'call_end': call['usage'] = event['data'].get('usage', {})
                if call['closed']:
                    self._charge_call(call)
                if call['closed'] and call['transport_finished']:
                    self._budget_calls.pop(identity, None)
        if observer:
            observer(event)

    def complete(self, *args, **kwargs):
        original = self.config
        allowance = self.token_budget.allowance(original['response_tokens'])
        call = {'sent': False, 'usage': {}, 'closed': False, 'started': False,
                'transport_finished': False, 'allowance': allowance, 'identity': object(),
                'observer': self._budget_observer}
        with self._budget_lock:
            self._current_budget_call = call
        self.config = {**original, 'response_tokens': allowance}
        try:
            answer = super().complete(*args, **kwargs)
        finally:
            self.config = original
            with self._budget_lock:
                call['closed'] = True
                self._current_budget_call = None
                self._charge_call(call)
                # Finished calls need no callback ownership; cancelled workers
                # retain their ID until their transport actually settles.
                self._budget_calls = {key: value for key, value in self._budget_calls.items()
                                      if value is not call or not call['transport_finished']}
        if self.token_budget.summary()['charged_output_tokens'] > self.token_budget.limit:
            raise ProviderError('Provider exceeded the experiment token allowance; no returned action may run.', category='budget')
        return answer


class BudgetModelClient(TokenBudgetMixin, ModelClient):
    pass
