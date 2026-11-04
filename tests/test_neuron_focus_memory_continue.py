"""CPU-only controls for the memory-policy continuation's inherited charges."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from neuron_focus_memory_continue import carry_state


class MemoryContinuationControls(unittest.TestCase):
    def setUp(self):
        phases={n:{'observed_tokens':0,'charged_tokens':64,'uncertain_tokens_upper_bound':64,'measurement_complete':False} for n in ('call-001','call-002')}
        self.carry={'original_start':{'began_unix':100.,'end_unix':10900.},'attempted_calls':2,'completed_responses':0,
            'usage':{'charged_tokens':128,'phases':phases},'budget':{'phase_categories':{n:'development_untouched' for n in phases}}}

    def test_carries_both_calls_and_128_charge(self):
        r=carry_state(self.carry,1000)
        self.assertEqual(r['remaining_seconds'],9900);self.assertEqual(r['initial_calls'],2)
        self.assertEqual(r['initial_charged_tokens'],128);self.assertEqual(r['historical_interrupted_calls'],2)
        self.assertEqual(r['maximum_completed_scheduled_responses'],18);self.assertEqual(r['total_token_ceiling'],155648)

    def test_expired_or_extended_clock_rejected(self):
        with self.assertRaisesRegex(ValueError,'expired'):carry_state(self.carry,10900)
        self.carry['original_start']['end_unix']+=1
        with self.assertRaisesRegex(ValueError,'clock changed'):carry_state(self.carry,1000)

    def test_either_charge_cannot_be_erased(self):
        for n in ('call-001','call-002'):
            c=copy.deepcopy(self.carry);c['usage']['phases'][n]['charged_tokens']=0
            with self.assertRaisesRegex(ValueError,'usage changed'):carry_state(c,1000)

    def test_missing_phase_or_extra_attempt_rejected(self):
        c=copy.deepcopy(self.carry);del c['usage']['phases']['call-001']
        with self.assertRaisesRegex(ValueError,'phase mismatch'):carry_state(c,1000)
        self.carry['attempted_calls']=3
        with self.assertRaisesRegex(ValueError,'two interruptions'):carry_state(self.carry,1000)


if __name__=='__main__':unittest.main()
