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
        self.lock = threading.Lock()

    def allowance(self, requested):
        with self.lock:
            left = self.limit - self.charged
            if left <= 0:
                raise ProviderError('Experiment generated-token budget exhausted; saved candidate remains available.', category='budget')
            return min(requested, left)

    def charge(self, usage, sent, allowance):
        value = output_tokens(usage)
        with self.lock:
            if value is not None:
                self.reported += value
                self.charged += value
            elif sent:
                # Unknown usage is never free. This is an enforcement charge,
                # not a claim that the provider actually generated this amount.
                self.charged += allowance
                self.fallback_calls += 1

    def summary(self):
        with self.lock:
            return {'limit': self.limit, 'charged_output_tokens': self.charged,
                    'reported_output_tokens': self.reported, 'unmeasured_sent_calls': self.fallback_calls,
                    'usage_complete': self.fallback_calls == 0, 'exhausted': self.charged >= self.limit}


class TokenBudgetMixin:
    """Compose with the production client, including its normal wire adapter."""
    def __init__(self, *args, token_budget=None, observer=None, **kwargs):
        self.token_budget = token_budget or GeneratedTokenBudget()
        self._budget_observer = observer
        self._budget_calls = {}
        self._current_budget_call = None
        super().__init__(*args, observer=self._observe_budget, **kwargs)

    def _observe_budget(self, event):
        identity = event['call_id']
        if event['type'] == 'call_start':
            self._budget_calls[identity] = self._current_budget_call
        call = self._budget_calls.get(identity)
        if call is not None and not call['closed']:
            if event['type'] == 'provider_request':
                call['sent'] = True
            if event['type'] == 'call_end':
                call['usage'] = event['data'].get('usage', {})
        if self._budget_observer:
            self._budget_observer(event)

    def complete(self, *args, **kwargs):
        original = self.config
        allowance = self.token_budget.allowance(original['response_tokens'])
        call = {'sent': False, 'usage': {}, 'closed': False}
        self._current_budget_call = call
        self.config = {**original, 'response_tokens': allowance}
        try:
            answer = super().complete(*args, **kwargs)
        finally:
            self.config = original
            call['closed'] = True
            self._current_budget_call = None
            self.token_budget.charge(call['usage'], call['sent'], allowance)
        if self.token_budget.summary()['charged_output_tokens'] > self.token_budget.limit:
            raise ProviderError('Provider exceeded the experiment token allowance; no returned action may run.', category='budget')
        return answer


class BudgetModelClient(TokenBudgetMixin, ModelClient):
    pass
