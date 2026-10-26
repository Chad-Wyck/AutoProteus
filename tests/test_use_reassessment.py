import base64
import hashlib
import json
from pathlib import Path
import shlex
import sys
import unittest

from controller.evaluation import source_identity
from controller.storage import atomic_json
from test_seed import temporary_directory

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from activation_use import PROTOCOL, contract, expected
from use_reassessment import reassess, EvidenceError


class UseReassessmentTests(unittest.TestCase):
    def fixture(self,root,completed=True):
        cell='fixture_first_01_sha256_file';sid='a'*32
        folder=root/'trials'/cell/'attempt-001';session_dir=folder/'sessions'/sid
        quarantine=session_dir/'quarantine';quarantine.mkdir(parents=True)
        spec=contract('sha256_file','fresh');final,receipt=expected(spec)
        seed=[{'path':name,'data':base64.b64encode(b'# inert source; never import\n').decode()}
            for name in ('seed.py','autoproteus/agent.py')]
        artifacts={}
        contents={spec['input']:final,spec['output']:json.dumps(receipt).encode(),
            **{'harness/'+r['path']:base64.b64decode(r['data']) for r in seed}}
        for name,data in contents.items():
            digest=hashlib.sha256(data).hexdigest();(quarantine/(digest+'.blob')).write_bytes(data)
            artifacts[name]={'sha256':digest,'bytes':len(data)}
        atomic_json(root/'plan.json',{'protocol':PROTOCOL,'profiles':[{'id':'fixture','config':{'max_steps':128}}]})
        row={'added':'sha256_file','first_package_accepted':True,'treatment':'baseline','run':{'session':sid},
            'first_use':{'activated':True,'passed':False,'source_sha256':source_identity(seed),'shared_actions_used':1,
                'run':{'status':'completed' if completed else 'waiting','timed_out':False}},
            'wall_budget':{'deadline_reached':False},'token_budget':{'charged_output_tokens':1,'limit':100}}
        atomic_json(folder/'result.json',row);atomic_json(folder/'task.json',{'first_use':spec})
        atomic_json(session_dir/'session.json',{'id':sid,'artifacts':artifacts})
        program=("from harness.autoproteus.tools import Workspace\nfrom pathlib import Path\n"
            "w=Workspace(Path('.'))\nr=w.execute('sha256_file', "+repr({'path':spec['input']})+")\nprint('Result:', r)\n"
            +"open("+repr(str(root/'MUST_NOT_EXECUTE'))+", 'w').write('bad')\n")
        events=[{'type':'run_started'},{'type':'run_started'},
            {'type':'action_result','data':{'ok':True,'action':{'tool':'run_command',
                'arguments':{'command':'python3 -c '+shlex.quote(program)}},
                'result':{'exit_code':0,'output':'Result: '+repr(receipt)}}}]
        (session_dir/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
        atomic_json(root/'queue.json',{'cells':{cell:[{'attempt':1,'state':'completed','result':row}]}})
        return quarantine,artifacts,spec

    def test_reassessment_uses_checked_blobs_and_saved_status_without_modifying_or_executing(self):
        for completed in (False,True):
            with self.subTest(completed=completed),temporary_directory() as directory:
                root=Path(directory);self.fixture(root,completed)
                before={p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()}
                value=reassess(root);entry=value['first'][0]
                self.assertFalse(entry['raw_first_use_passed'])
                self.assertEqual(entry['reassessed_first_use_passed'],completed)
                self.assertTrue(entry['checks']['capability_used'])
                self.assertEqual(before,{p.relative_to(root):p.read_bytes() for p in root.rglob('*') if p.is_file()})
                self.assertFalse((root/'MUST_NOT_EXECUTE').exists())

    def test_tampered_artifact_and_active_queue_are_rejected(self):
        with temporary_directory() as directory:
            root=Path(directory);quarantine,artifacts,spec=self.fixture(root)
            (quarantine/(artifacts[spec['input']]['sha256']+'.blob')).write_bytes(b'tampered')
            with self.assertRaisesRegex(EvidenceError,'identity mismatch'):reassess(root)
            queue=json.loads((root/'queue.json').read_text());next(iter(queue['cells'].values()))[0]['state']='running'
            atomic_json(root/'queue.json',queue)
            with self.assertRaisesRegex(ValueError,'running'):reassess(root)
