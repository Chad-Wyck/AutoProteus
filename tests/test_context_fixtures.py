"""Controls for the protected retention fixtures; trusted code only."""
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_seed as seed_tests


RETENTION = (
    'test_large_history_keeps_tool_messages_valid',
    'test_trimming_retains_request_and_recent_tool_pair_without_changing_journal',
    'test_shortened_read_context_preserves_usable_continuation',
    'test_whole_file_context_omission_never_pretends_to_be_a_full_read',
)


def run_retention():
    result = unittest.TestResult()
    unittest.TestSuite(seed_tests.AgentTests(name) for name in RETENTION).run(result)
    return result


class ContextFixtureTests(unittest.TestCase):
    def test_large_advertised_catalog_retains_valid_bounded_observations(self):
        additions = {f'fixture_capability_{index}': ('Long Unicode description 猫. ' * 100,
                     {'path': {'type': 'string'}}, ['path']) for index in range(8)}
        with patch.dict(seed_tests.TOOL_SPECS, additions):
            result = run_retention()
        self.assertEqual(result.testsRun, len(RETENTION))
        self.assertTrue(result.wasSuccessful(), str(result.errors + result.failures))

    def test_fixtures_still_reject_messages_exceeding_their_context_budget(self):
        original = seed_tests.Agent.messages
        def unbounded(agent, session, config, *args, **kwargs):
            messages = original(agent, session, config, *args, **kwargs)
            if session['messages']:
                messages.append({'role': 'user', 'content': 'untrimmed ' * 20000})
            return messages
        with patch.object(seed_tests.Agent, 'messages', unbounded):
            result = run_retention()
        self.assertEqual(result.testsRun, len(RETENTION))
        self.assertEqual(len(result.failures), len(RETENTION))
        self.assertEqual(result.errors, [])

    def test_irreducible_catalog_still_refuses_instead_of_losing_human_text(self):
        case = seed_tests.AgentTests(RETENTION[0])
        case.setUp()
        agent = seed_tests.Agent(seed_tests.ROOT, case.store, case.settings, lambda _: None)
        try:
            session = case.store.create('Preserve this complete human contract 猫.', 'ollama', 'fixture')
            session['messages'] = [{'role': 'user', 'origin': 'human', 'content': 'Keep this correction too.'}]
            original = json.dumps(session['messages'], ensure_ascii=False)
            config = {**case.settings.values, 'provider': 'ollama', 'protocol': 'native',
                      'context_tokens': 4096, 'response_tokens': 512}
            with patch.dict(seed_tests.TOOL_SPECS, {'huge_fixture_tool': ('x' * 100000, {}, [])}):
                with self.assertRaisesRegex(ValueError, 'context'):
                    agent.messages(session, config)
            self.assertEqual(json.dumps(session['messages'], ensure_ascii=False), original)
            self.assertEqual(session['task'], 'Preserve this complete human contract 猫.')
        finally:
            agent.close()
            case.tearDown()
