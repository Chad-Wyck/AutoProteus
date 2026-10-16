import base64
import importlib.util
from pathlib import Path
import unittest

from controller.config import DEFAULTS
from controller.isolation import Artifacts
from controller.storage import Store
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('generalization', ROOT / 'evaluations/generalization.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


class GeneralizationTests(unittest.TestCase):
    def test_growth_usage_excludes_development_before_the_last_activation(self):
        events = [{'type': 'run_started'}, {'type': 'action_result', 'data': {'ok': True,
                   'action': {'tool': 'old_tool'}}}, {'type': 'run_started'},
                  {'type': 'action_result', 'data': {'ok': True, 'action': {'tool': 'new_tool'}}}]
        self.assertEqual(study.tool_use(study.latest_run(events))['direct'], ['new_tool'])

    def test_profiles_preserve_saved_defaults_and_explicitly_enable_terminal(self):
        before = dict(DEFAULTS)
        profiles = study.profile_configs()
        self.assertEqual(profiles['default']['model'], DEFAULTS['model'])
        self.assertEqual(profiles['default']['thinking'], DEFAULTS['thinking'])
        self.assertEqual(profiles['qwen9b']['context_tokens'], 65536)
        self.assertTrue(all(value['terminal'] for value in profiles.values()))
        self.assertEqual(DEFAULTS, before)

    def test_fork_preserves_inert_files_human_instructions_and_complete_parent_journal(self):
        with temporary_directory() as directory:
            store = Store(Path(directory) / 'sessions')
            original = store.create('Keep the original instructions.', 'demo', 'fixture')
            original['messages'] = [{'role': 'user', 'content': original['task'], 'origin': 'human'},
                                    {'role': 'assistant', 'content': 'Development history'}]
            store.feed(original, 'user', original['task'])
            files = Artifacts(store, original)
            for name, raw in [('harness/seed.py', b'raise RuntimeError("never execute on host")'), ('input.txt', b'keep')]:
                files.put(name, base64.b64encode(raw).decode())
            files.checkpoint(['harness/seed.py', 'input.txt'])
            branch = study.clone_checkpoint(store, original, 'concise')
            self.assertNotEqual(branch['id'], original['id'])
            self.assertEqual(branch['messages'], original['messages'])
            self.assertEqual(Artifacts(store, branch).read('input.txt'), b'keep')
            self.assertFalse((Path(branch['workspace']) / 'harness/seed.py').exists())
            self.assertEqual((store.directory(branch['id']) / 'parent-events.jsonl').read_bytes(),
                             (store.directory(original['id']) / 'events.jsonl').read_bytes())
            branch['messages'][0]['content'] = 'branch-only'
            self.assertEqual(original['messages'][0]['content'], original['task'])


if __name__ == '__main__':
    unittest.main()
