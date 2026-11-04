"""CPU-only resource-policy controls; no GPU or host queries."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
import memory_availability_policy as policy
from lora6k_state import atomic,read
from weight_editor_owned import admission
from weight_editor_runtime import Deadline


class MemoryAvailabilityControls(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'.data/test-memory-policy';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.temp.name)
        atomic(self.root/'manifest.json',{'resource_policy':{'name':policy.NAME,'floors':policy.FLOORS,
            'background_utilization_is_advisory':True,'gpu_uuid':'GPU-test','gpu_pci_bus_id':'bus'}})
        self.sample={'total_vram_mib':11264,'free_vram_mib':9000,'free_ram_kib':10*2**20,'free_commit_bytes':8*2**30,
            'disk_bytes':30*2**30,'gpu':[],'utilization':100}
        self.host={k:self.sample[k] for k in ('free_ram_kib','free_commit_bytes','gpu')}
        self.bg={'processes':[{'ProcessId':999,'Name':'unknown-background.exe'}],
            'engines':[{'Name':'pid_999_luid_0_phys_0_eng_1_engtype_Compute_0','UtilizationPercentage':100}]}

    def tearDown(self):self.temp.cleanup()

    def observe(self,host=None,bg=None,gpu='GPU-test,bus,11264,9000,100'):
        values=[gpu,json.dumps(self.host if host is None else host),json.dumps(self.bg if bg is None else bg)]
        with patch.object(policy.subprocess,'check_output',side_effect=values):
            return policy.observe(self.root,self.root,lambda:100,stage='admission')

    def test_high_background_load_and_unknown_name_do_not_block(self):
        self.assertEqual(self.observe()['advisory_status'],'available')

    def test_high_utilization_does_not_delay_memory_admission(self):
        calls=[]
        def observe(timeout):calls.append(timeout);return self.sample
        admission(observe,Deadline(100),sleep=lambda _:None,availability_only=True)
        self.assertEqual(len(calls),3)

    def test_invalid_policy_cannot_enable_route(self):
        p=read(self.root/'manifest.json');p['resource_policy']['floors']['running_free_vram_mib']=1;atomic(self.root/'manifest.json',p)
        with self.assertRaisesRegex(ValueError,'Unreviewed'):policy.config(self.root)

    def test_no_optin_keeps_legacy_route(self):
        atomic(self.root/'manifest.json',{});self.assertIsNone(policy.config(self.root))

    def test_each_admission_memory_floor(self):
        for key,value in [('free_vram_mib',8191),('free_ram_kib',8192*1024-1),('free_commit_bytes',4*2**30-1),('disk_bytes',20*2**30-1)]:
            s=copy.deepcopy(self.sample);s[key]=value
            with self.assertRaisesRegex(ValueError,'floor'):policy.validate_memory(s,'admission')

    def test_each_running_memory_floor(self):
        for key,value in [('free_vram_mib',2047),('free_ram_kib',6144*1024-1),('free_commit_bytes',4*2**30-1),('disk_bytes',5*2**30-1)]:
            s=copy.deepcopy(self.sample);s[key]=value
            with self.assertRaisesRegex(ValueError,'floor'):policy.validate_memory(s,'running')

    def test_exact_running_boundaries_pass(self):
        s=copy.deepcopy(self.sample);s.update(free_vram_mib=2048,free_ram_kib=6144*1024,free_commit_bytes=4*2**30,disk_bytes=5*2**30)
        policy.validate_memory(s,'running')

    def test_owned_shared_memory_bound(self):
        s=copy.deepcopy(self.sample);s['gpu']=[{'Name':'pid_1','SharedUsage':512*2**20+1,'DedicatedUsage':1}]
        with self.assertRaisesRegex(ValueError,'shared GPU'):policy.validate_memory(s,'running')

    def test_invalid_critical_values_stop(self):
        for value in (float('nan'),float('inf'),None,-1,True):
            s=copy.deepcopy(self.sample);s['free_ram_kib']=value
            with self.assertRaises(ValueError):policy.validate_memory(s,'running')

    def test_selected_GPU_identity_must_match(self):
        with self.assertRaisesRegex(ValueError,'identity changed'):self.observe(gpu='GPU-other,bus,11264,9000,0')

    def test_critical_query_failure_is_durable_stop(self):
        with patch.object(policy.subprocess,'check_output',side_effect=TimeoutError('memory timeout')):
            with self.assertRaises(TimeoutError):policy.observe(self.root,self.root,lambda:100,stage='running')
        rows=list((self.root/'resources').glob('*critical_failure.json'));self.assertEqual(len(rows),1)
        self.assertIn('memory timeout',read(rows[0])['error'])

    def test_advisory_failure_is_logged_without_utilization_stop(self):
        with patch.object(policy.subprocess,'check_output',side_effect=['GPU-test,bus,11264,9000,100',json.dumps(self.host),TimeoutError('background unavailable')]):
            sample=policy.observe(self.root,self.root,lambda:100,stage='admission')
        self.assertEqual(sample['advisory_status'],'unavailable')
        row=read(next((self.root/'resources').glob('*accepted.json')))
        self.assertIn('background unavailable',row['advisory_error'])

    def test_evidence_write_failure_stops(self):
        with patch.object(policy,'atomic',side_effect=OSError('disk error')):
            with self.assertRaises(OSError):self.observe()

    def test_unavailable_utilization_does_not_hide_valid_memory(self):
        self.assertIsNone(self.observe(gpu='GPU-test,bus,11264,9000,not-supported')['utilization'])

    def test_unbound_owned_memory_row_stops(self):
        h=copy.deepcopy(self.host);h['gpu']=[{'Name':'pid_999_luid_other','SharedUsage':1,'DedicatedUsage':1}]
        with self.assertRaisesRegex(ValueError,'Unbound'):self.observe(host=h)


if __name__=='__main__':unittest.main()
