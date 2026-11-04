"""CPU-only controls for preserving the interrupted study's original limits."""
import copy,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from neuron_focus_continue import carry_state


class ContinuationControls(unittest.TestCase):
    def setUp(self):
        self.carry={'original_start':{'began_unix':100.,'end_unix':10900.},'attempted_calls':1,'completed_responses':0,
            'usage':{'charged_tokens':64,'phases':{'call-001':{'observed_tokens':0,'charged_tokens':64,'uncertain_tokens_upper_bound':64,'measurement_complete':False}}},
            'budget':{'phase_categories':{'call-001':'development_untouched'}}}

    def test_original_clock_and_charge_are_retained(self):
        state=carry_state(self.carry,1000)
        self.assertEqual(state['remaining_seconds'],9900)
        self.assertEqual(state['initial_calls'],1)
        self.assertEqual(state['initial_charged_tokens'],64)
        self.assertEqual(state['total_token_ceiling'],155648)
        self.assertEqual(state['maximum_completed_scheduled_responses'],18)
        self.assertEqual(state['additional_interrupted_calls_allowed'],0)

    def test_expired_deadline_cannot_continue(self):
        with self.assertRaisesRegex(ValueError,'expired'):carry_state(self.carry,10900)

    def test_clock_extension_rejected(self):
        self.carry['original_start']['end_unix']+=1
        with self.assertRaisesRegex(ValueError,'clock changed'):carry_state(self.carry,1000)

    def test_reset_charge_or_uncertainty_rejected(self):
        for key in ('charged_tokens','uncertain_tokens_upper_bound'):
            c=copy.deepcopy(self.carry);c['usage']['phases']['call-001'][key]=0
            with self.assertRaisesRegex(ValueError,'usage changed'):carry_state(c,1000)

    def test_prior_completed_response_or_second_interruption_rejected(self):
        for key in ('attempted_calls','completed_responses'):
            c=copy.deepcopy(self.carry);c[key]+=1
            with self.assertRaisesRegex(ValueError,'first-call interruption'):carry_state(c,1000)

    def test_missing_category_or_phase_rejected(self):
        for key in ('budget','usage'):
            c=copy.deepcopy(self.carry)
            c[key]['phase_categories' if key=='budget' else 'phases']={}
            with self.assertRaisesRegex(ValueError,'phase mismatch'):carry_state(c,1000)


if __name__=='__main__':unittest.main()
