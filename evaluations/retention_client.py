"""Host-owned opt-in native context estimation, composed with production transport."""
import copy

from controller.providers import ModelClient, ProviderError
from context_retention import RetentionBudget, neutral_identity
from run_budget import TokenBudgetMixin


class WireClient(ModelClient):
    def __init__(self, *args, budget, source, **kwargs):
        super().__init__(*args, **kwargs)
        self.budget, self.source, self.accepted_wire = budget, source, None

    def check_context(self, messages, tools):
        estimate = self.budget.estimate(messages, tools, self.config, self.source)
        allowance = max(0, self.config['context_tokens'] - self.config['response_tokens'] - 128)
        if estimate > allowance:
            raise ProviderError('Input exceeds experimental context estimate', category='context')
        return {'estimated_input_tokens': estimate, 'allowance_tokens': allowance}

    def prepare_messages(self, messages, tools, observe=None):
        wire, adjustment = super().prepare_messages(messages, tools, observe)
        self.accepted_wire = wire
        if observe:
            observe('context_estimate', dict(self.budget.last))
        return wire, adjustment


class RetentionClient(ModelClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.retention = RetentionBudget()

    def complete(self, messages, cancel, progress=None, tools=None):
        if self.config.get('protocol', 'native') != 'native' or self.config.get('api_format') == 'responses':
            raise ValueError('Context-retention comparison currently qualifies native chat only')
        try:
            context = self.observation_context(messages) if self.observation_context else {}
        except Exception:
            self.retention.anchor = None
            self.observation_failed = True
            context = {}
        source = context.get('seed_sha256')
        # Each transport gets a private estimator snapshot. A detached cancelled
        # worker cannot overwrite a later call's accepted input or usage anchor.
        wire_client = WireClient(self.config, key=self.key, observer=self.observer,
            native_instructions=self.native_instructions, budget=copy.deepcopy(self.retention), source=source)
        wire_client.observation_context = self.observation_context
        try:
            answer = wire_client.complete(messages, cancel, progress, tools)
        except BaseException:
            self.retention.anchor = None
            raise
        finally:
            self.observation_failed |= wire_client.observation_failed
        if answer.get('normalization_error') or answer.get('provider_error') or answer.get('incomplete'):
            self.retention.anchor = None
        else:
            self.retention.observe(wire_client.accepted_wire, tools or [], self.config, answer.get('usage'), source)
        return {**answer, 'context_retention': {'neutral_sha256': neutral_identity(messages),
            'wire_trimmed': bool(answer.get('context_adjustment')),
            'host_estimate': wire_client.budget.last,
            'scope': 'Reported usage for this exact neutral input only; not task verification.'}}


class RetentionModelClient(TokenBudgetMixin, RetentionClient):
    pass


def variant(source):
    """Construct inert guest bytes; never import or execute edited candidates."""
    import base64
    from pathlib import Path
    result = copy.deepcopy(source)
    name = 'autoproteus/context_retention.py'
    if any(item['path'] == name for item in result):
        raise ValueError('Context-retention helper already present')
    matches = [item for item in result if item['path'] == 'autoproteus/agent.py']
    if len(matches) != 1:
        raise ValueError('One seed agent is required')
    item = matches[0]
    text = base64.b64decode(item['data']).decode('utf-8')
    replacements = [
        ('        self.lock = threading.Lock()', '        self.lock = threading.Lock()\n        self.retention_budgets = {}'),
        ('        return build_messages(session, config, steps)',
         '        from .context_retention import RetentionBudget\n'
         '        budget = self.retention_budgets.setdefault(session["id"], RetentionBudget())\n'
         '        return build_messages(session, config, steps, measure=lambda items, schemas: '
         'budget.estimate(items, schemas, config, session.get("seed_sha256")) * 2)'),
        ('                self.store.event(session, "model_response", response)',
         '                self.retention_budgets[session["id"]].observe_response(messages, '
         'tool_definitions(config["terminal"]), config, response, session.get("seed_sha256"))\n'
         '                self.store.event(session, "model_response", response)')]
    for before, after in replacements:
        if text.count(before) != 1:
            raise ValueError('Retention variant source anchor changed; review before preparing')
        text = text.replace(before, after, 1)
    item['data'] = base64.b64encode(text.encode()).decode('ascii')
    helper = Path(__file__).with_name('context_retention.py')
    result.append({'path': name, 'data': base64.b64encode(helper.read_bytes()).decode('ascii')})
    return result
