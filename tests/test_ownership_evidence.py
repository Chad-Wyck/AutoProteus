"""CPU-only tests: preserve ownership rejection and its triggering evidence."""
import ast,copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
import lora6k_supervisor as guard
from lora6k_state import atomic,read


class OwnershipEvidenceControls(unittest.TestCase):
    def observe(self,compute=(),raw='',owned=(),sink=None):
        processes=[{'ProcessId':18740,'Name':'python.exe','ParentProcessId':18404,'CreationDate':'saved-time'},
            {'ProcessId':11,'Name':'explorer.exe','ParentProcessId':1,'CreationDate':'desktop-time'}]
        value={'processes':processes,'compute':list(compute)}
        with patch.object(guard.subprocess,'check_output',side_effect=[raw,json.dumps(value)]):
            return guard.ownership(owned_pids=owned,evidence=sink,context={'token':'nonce','progress':{'pid':18740}})

    def engine(self,pid):
        return {'Name':f'pid_{pid}_luid_0_phys_0_eng_1_engtype_Compute_0','UtilizationPercentage':1}

    @unittest.skipUnless((Path(__file__).resolve().parents[1]/'.data/apwt-neuron-focus-20261104-003/code/lora6k_supervisor.py').is_file(), 'Private historical frozen source is not distributed; ancestry comparison unavailable')
    def test_original_decision_function_is_unchanged(self):
        original=Path(__file__).resolve().parents[1]/'.data/apwt-neuron-focus-20261104-003/code/lora6k_supervisor.py'
        def fn(path):return next(n for n in ast.parse(Path(path).read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='check_owners')
        self.assertEqual(ast.dump(fn(original)),ast.dump(fn(guard.__file__)))

    def test_rejection_is_durable_before_exception_escapes(self):
        parent=Path(__file__).resolve().parents[1]/'.data/test-ownership-evidence';parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=parent) as tmp:
            sink=lambda row:atomic(Path(tmp)/(row['stage']+'.json'),row)
            with self.assertRaisesRegex(ValueError,'Active GPU compute'):
                self.observe([self.engine(11)],'11,explorer.exe,[N/A]',sink=sink)
            row=read(Path(tmp)/'rejected_or_query_failed.json')
            self.assertEqual(row['compute_filtered'][0]['UtilizationPercentage'],1)
            self.assertEqual(row['compute_unfiltered'],row['compute_filtered'])
            self.assertEqual(row['context']['token'],'nonce')
            self.assertEqual(row['processes'][0]['CreationDate'],'saved-time')
            self.assertIn('Active GPU compute',row['error'])
            self.assertTrue((Path(tmp)/'before_decision.json').exists())

    def test_owned_compute_is_recorded_and_excluded(self):
        rows=[];result=self.observe([self.engine(18740)],'18740,python.exe,4000',owned={18740,18404},sink=lambda r:rows.append(copy.deepcopy(r)))
        self.assertEqual(result['active_compute'],[])
        self.assertEqual(rows[-1]['owned_pids'],[18404,18740])
        self.assertEqual(len(rows[-1]['compute_unfiltered']),1)
        self.assertEqual(rows[-1]['compute_filtered'],[])
        self.assertEqual(rows[-1]['stage'],'accepted')

    def test_similar_pid_is_still_rejected(self):
        rows=[]
        with self.assertRaisesRegex(ValueError,'Active GPU compute'):
            self.observe([self.engine(187400)],owned={18740},sink=lambda r:rows.append(copy.deepcopy(r)))
        self.assertEqual(rows[-1]['compute_filtered'][0]['Name'],self.engine(187400)['Name'])

    def test_desktop_accepted_unknown_owner_rejected(self):
        self.assertEqual(len(self.observe(raw='11,explorer.exe,[N/A]')['desktop_contexts']),1)
        rows=[]
        with self.assertRaisesRegex(ValueError,'unknown owner'):
            self.observe(raw='99,unrecognized.exe,[N/A]',sink=lambda r:rows.append(copy.deepcopy(r)))
        self.assertEqual(rows[-1]['nvidia_rows_filtered'][0][0],'99')

    def test_query_failure_retains_partial_evidence_and_fails_closed(self):
        rows=[]
        with patch.object(guard.subprocess,'check_output',side_effect=['11,explorer.exe,[N/A]',TimeoutError('CIM timeout')]):
            with self.assertRaises(TimeoutError):guard.ownership(evidence=lambda r:rows.append(copy.deepcopy(r)))
        self.assertEqual(rows[-1]['nvidia_raw'],'11,explorer.exe,[N/A]')
        self.assertIn('CIM timeout',rows[-1]['error'])

    def test_malformed_cim_is_retained(self):
        rows=[]
        with patch.object(guard.subprocess,'check_output',side_effect=['','not JSON']):
            with self.assertRaises(ValueError):guard.ownership(evidence=lambda r:rows.append(copy.deepcopy(r)))
        self.assertEqual(rows[-1]['cim_raw'],'not JSON')

    def test_evidence_write_failure_is_not_accepted(self):
        def broken(row):raise OSError('disk failure')
        with self.assertRaisesRegex(OSError,'disk failure'):self.observe(sink=broken)


if __name__=='__main__':unittest.main()
