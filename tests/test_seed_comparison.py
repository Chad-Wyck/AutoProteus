import base64
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from controller.artifacts import seed_files
from controller.evaluation import source_identity
from controller.storage import atomic_json
from test_seed import temporary_directory

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'evaluations'))
import model_plan
import seed_comparison as comparison


class SeedComparisonTests(unittest.TestCase):
    def freeze(self, output, old_version=False, unrelated_init=False):
        # CI may use a shallow checkout. Supply inert historical bytes rather
        # than depending on HEAD being the user's uncommitted baseline.
        files={('SEED.md' if item['path']=='README.md' else item['path']):base64.b64decode(item['data'])
               for item in seed_files(ROOT)}
        for path in comparison.EDIT_FILES | comparison.FINISH_FILES:
            files[path] += b'\n# historical fixture\n'
        if old_version:
            import re
            files['autoproteus/__init__.py'] = re.sub(rb'(__version__ = ")[0-9.]+(")', rb'\g<1>0.0.1\2', files['autoproteus/__init__.py'])
        if unrelated_init:
            files['autoproteus/__init__.py'] += b'\n# unrelated code change\n'
        files['controller/action_protocol.py'] = b'NATIVE = "FROZEN HISTORICAL FORMAT"\n'
        def git(*args):
            if args[0]=='rev-parse':return b'a'*40+b'\n'
            return files[args[1].split(':',1)[1]]
        with patch.object(comparison,'git',side_effect=git):
            return comparison.prepare(output)

    def test_version_only_metadata_is_shared_but_other_module_changes_are_rejected(self):
        with temporary_directory() as directory:
            root=Path(directory)
            manifest=self.freeze(root/'aligned',old_version=True)
            self.assertEqual(manifest['release_metadata_normalized'][0]['before'],'0.0.1')
            self.assertNotEqual(manifest['git_source_sha256'],manifest['arms']['baseline']['source_sha256'])
            with self.assertRaisesRegex(ValueError,'targeted seed files'):
                self.freeze(root/'rejected',old_version=True,unrelated_init=True)
            self.assertFalse((root/'rejected').exists())

    def test_preparation_freezes_isolated_sources_common_checks_and_balanced_schedule(self):
        with temporary_directory() as directory:
            output=Path(directory)/'comparison'
            before=source_identity(seed_files(ROOT))
            manifest=self.freeze(output)
            packs={name:json.loads((output/arm['source']).read_text()) for name,arm in manifest['arms'].items()}
            original={item['path']:item['data'] for item in packs['baseline']}
            for name,changed in (('edit-result-only',comparison.EDIT_FILES),('finish-only',comparison.FINISH_FILES)):
                after={item['path']:item['data'] for item in packs[name]}
                self.assertEqual({path for path in original if original[path]!=after[path]},changed)
                self.assertTrue(all(original[path]==after[path] for path in original if path.startswith('tests/')))
                self.assertEqual(source_identity(packs[name]),manifest['arms'][name]['source_sha256'])
            self.assertEqual(source_identity(packs['combined']),before)
            self.assertEqual(source_identity(seed_files(ROOT)),before)
            self.assertEqual((output/'baseline-native.txt').read_text(),(output/'edit-result-only-native.txt').read_text())
            self.assertNotEqual((output/'baseline-native.txt').read_text(),(output/'finish-only-native.txt').read_text())
            csv=[row for row in manifest['schedule'] if row['comparison']=='unchanged-edit']
            self.assertEqual([row['arm'] for row in csv],['baseline','edit-result-only','edit-result-only','baseline','baseline','edit-result-only'])
            self.assertEqual(comparison.load(output),manifest)
            with self.assertRaises(ValueError):self.freeze(output)
            (output/'finish-only-native.txt').write_text('tampered')
            with self.assertRaisesRegex(ValueError,'arm changed'):comparison.load(output)

    def test_source_and_native_format_prepare_into_an_inert_plan_and_keep_current_checkout_pinned(self):
        with temporary_directory() as directory:
            root=Path(directory);output=root/'comparison';manifest=self.freeze(output)
            profiles=root/'profiles.json'
            atomic_json(profiles,[{'id':'fixture','config':{'provider':'hosted','base_url':'http://127.0.0.1:8080/v1','model':'fixture'}}])
            args=SimpleNamespace(mode='basic',output=str(root/'study'),profiles=str(profiles),repeats=1,
                timeout=3600,output_token_budget=65536,source_pack=str(output/'baseline-source.json'),
                native_instructions_file=str(output/'baseline-native.txt'))
            with patch('builtins.print'):model_plan.prepare(args)
            plan=json.loads((root/'study/plan.json').read_text())
            self.assertEqual(plan['source_sha256'],manifest['arms']['baseline']['source_sha256'])
            self.assertEqual(plan['starter_sha256'],manifest['current_source_sha256'])
            self.assertEqual(plan['upgrade_tasks'],[])
            model_plan.check(plan)
            pack=json.loads((output/'baseline-source.json').read_text())
            next(item for item in pack if item['path']=='tests/test_seed.py')['data']=base64.b64encode(b'changed protected tests').decode()
            atomic_json(output/'bad-source.json',pack);args.source_pack=str(output/'bad-source.json');args.output=str(root/'bad-study')
            with self.assertRaisesRegex(ValueError,'common starter tests'):model_plan.prepare(args)
            self.assertFalse((root/'bad-study').exists())
