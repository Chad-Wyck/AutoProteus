import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from controller.config import Settings
from controller.evaluation import source_identity
from controller.isolation import seed_files
from controller.practical import PracticalCheck, selection
from test_seed import temporary_directory

ROOT = Path(__file__).resolve().parents[1]


class PracticalCheckTests(unittest.TestCase):
    def test_check_is_optional_preserves_preferences_and_has_explicit_limits(self):
        with temporary_directory() as directory:
            settings = Settings(Path(directory))
            agent = Mock(); agent.execution.mode='vm'; agent.workers={}
            service = PracticalCheck(ROOT,Path(directory)/'checks',settings,agent,threading.RLock())
            self.assertEqual(service.public()['status'],'idle')
            with self.assertRaises(ValueError): service.start()
            settings.values.update(configured=True,provider='hosted',model='fixture')
            before = dict(settings.values)
            with patch.object(service,'_run') as run:
                report = service.start(); service.thread.join(2)
            run.assert_called_once()
            self.assertEqual(settings.values,before)
            self.assertTrue(report['selection_matches'])
            self.assertTrue(report['source_matches'])
            self.assertEqual(report['limits']['shared_actions_per_case'],24)
            self.assertNotIn('base_url',report['selection'])
            self.assertNotIn('api_key',report['selection'])
            service.close()

    def test_restart_marks_incomplete_check_interrupted_and_labels_stale_source(self):
        with temporary_directory() as directory:
            root=Path(directory);settings=Settings(root)
            (root/'latest.json').write_text(json.dumps({'status':'running','results':[],
                'selection':selection(settings.values),'source_sha256':'old'}))
            check=PracticalCheck(ROOT,root,settings,Mock(),threading.RLock())
            report=check.public()
            self.assertEqual(report['status'],'interrupted')
            self.assertFalse(report['source_matches'])
            self.assertTrue(report['selection_matches'])
            settings.values['temperature']=.9
            self.assertFalse(check.public()['selection_matches'])

    def test_internet_permission_is_part_of_practical_profile(self):
        with temporary_directory() as directory:
            values=Settings(Path(directory)).values
            self.assertNotEqual(selection(values),selection({**values,'internet':not values['internet']}))
