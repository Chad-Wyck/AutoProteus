import base64
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from controller.evaluation import source_identity
from controller.storage import atomic_json
from test_seed import temporary_directory

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from activation_replay import MARKER, broker_type, read_parent
from activation_use import contract


class ActivationReplayTests(unittest.TestCase):
    def test_full_study_reminder_is_activation_only_and_copies_each_stage_contract(self):
        import model_study as ms
        import controller.isolation as isolation
        from controller.config import DEFAULTS
        with temporary_directory() as directory:
            folder=Path(directory)
            for earlier in (None,'sha256_file'):
                instruction='Use the requested active tools and inspect the saved result.'
                task={'task':'Development contract. '+instruction,
                      **({'first_use':{'instruction':instruction}} if earlier is None else {'final_task':instruction})}
                def run(*args,**kwargs):
                    # The host broker applies the same reminder only when the
                    # controller has supplied a nonempty activation state.
                    with patch('activation_replay.Broker.__init__',lambda self,*a,**kw:setattr(self,'activation_context',kw['activation_context'])):
                        before=isolation.Broker(activation_context='')
                        after=isolation.Broker(activation_context='CURRENT ACTIVATION STATE')
                    self.assertEqual(before.activation_context,'')
                    self.assertEqual(after.activation_context,'CURRENT ACTIVATION STATE\n'+MARKER+instruction)
                    return {'run':{'status':'completed'}}
                with patch.object(ms,'_trial',side_effect=run):
                    result=ms.trial(folder,task,[],DEFAULTS,{'activation_reminder':True},'format_json',earlier)
                self.assertEqual(result['activation_reminder']['instruction'],instruction)
                self.assertFalse(result['activation_reminder']['observed'])  # No provider call in this fixture.
            with patch.object(ms,'_trial',return_value={'ordinary':True}):
                self.assertEqual(ms.trial(folder,{},[],DEFAULTS,{'activation_reminder':True}),{'ordinary':True})
            with self.assertRaisesRegex(ValueError,'verbatim'):
                ms.trial(folder,{'task':'No existing final clause'},[],DEFAULTS,{'activation_reminder':True},'format_json')
    @unittest.skipUnless(os.environ.get('AUTOPROTEUS_VM_TESTS')=='1','Real VM checks require explicit opt in')
    def test_real_vm_preserves_source_and_delivers_only_the_selected_reminder(self):
        from activation_replay import trial
        from activation_use import expected
        from activation_comparison import add_hash_reference
        from controller.artifacts import seed_files
        from controller.config import DEFAULTS
        root=Path(__file__).resolve().parents[1]
        source=add_hash_reference(seed_files(root))
        spec=contract('sha256_file','scripted-replay')
        _,receipt=expected(spec)
        parent={'source':source,'source_sha256':source_identity(source),
                'task':'Original request. '+spec['instruction'],'feature':'sha256_file','spec':spec}
        config={**DEFAULTS,'configured':True,'provider':'demo','terminal':True,
                'action_limit':True,'max_steps':12,'context_tokens':131072,'response_tokens':4096}
        actions=[{'action':{'tool':'sha256_file','arguments':{'path':spec['input']}}},
                 {'action':{'tool':'write_file','arguments':{'path':spec['output'],'content':json.dumps(receipt)}}},
                 {'action':{'tool':'read_file','arguments':{'path':spec['output']}}},
                 {'status':'completed','summary':'Verified the saved receipt.'}]
        with temporary_directory() as directory:
            for arm in ('baseline','task-reminder'):
                seen=[]
                class Scripted:
                    observation_failed=False
                    def __init__(self,*args,**kwargs): self.index=0
                    def complete(self,messages,cancel):
                        seen.append(json.loads(json.dumps(messages)))
                        action=actions[self.index];self.index+=1
                        return {'content':json.dumps(action),'usage':{}}
                folder=Path(directory)/arm;folder.mkdir()
                with patch('activation_replay.BudgetModelClient',Scripted):
                    result=trial(folder,parent,config,{'deadline':90,'generated_tokens':4096},arm)
                self.assertTrue(result['grade']['passed'],result['grade'])
                self.assertEqual(result['source_sha256'],source_identity(source))
                self.assertTrue(seen)
                self.assertEqual(any(MARKER in m['content'] for m in seen[0]),arm=='task-reminder')
                self.assertTrue(any(parent['task']==m['content'] for m in seen[0]))

    def test_reminder_is_host_selected_and_baseline_context_is_identical(self):
        instruction='Use csv_preview with its default limit.'
        def original(instance,*args,**kwargs): instance.activation_context='CURRENT ACTIVATION STATE\nActive.'
        with patch('activation_replay.Broker.__init__',original):
            baseline=broker_type('baseline',instruction)()
            reminder=broker_type('task-reminder',instruction)()
        self.assertEqual(baseline.activation_context,'CURRENT ACTIVATION STATE\nActive.')
        self.assertEqual(reminder.activation_context,baseline.activation_context+'\n'+MARKER+instruction)
        with self.assertRaises(ValueError): broker_type('guest-selected',instruction)

    def test_parent_requires_accepted_evidence_matching_source_and_original_instruction(self):
        with temporary_directory() as directory, patch('activation_replay.private',side_effect=Path):
            root=Path(directory)
            # This would fail if the preparer executed a candidate on the host.
            source=[{'path':'seed.py','data':base64.b64encode(b'raise AssertionError("Never import")').decode()}]
            spec=contract('sha256_file','frozen')
            result={'first_package_accepted':True,'first_use':{'source_sha256':source_identity(source)}}
            atomic_json(root/'result.json',result)
            atomic_json(root/'review/candidate-source.json',source)
            atomic_json(root/'original-task.json',{'task':'Original task. '+spec['instruction'],'first_use':spec})
            parent=read_parent(root)
            self.assertEqual(parent['source'],source)
            result['first_use']['source_sha256']='wrong';atomic_json(root/'result.json',result)
            with self.assertRaisesRegex(ValueError,'identity'): read_parent(root)
            result['first_use']['source_sha256']=source_identity(source);atomic_json(root/'result.json',result)
            atomic_json(root/'original-task.json',{'task':'No use instruction supplied','first_use':spec})
            with self.assertRaisesRegex(ValueError,'verbatim'): read_parent(root)
            result['first_package_accepted']=False;atomic_json(root/'result.json',result)
            with self.assertRaisesRegex(ValueError,'accepted'): read_parent(root)
