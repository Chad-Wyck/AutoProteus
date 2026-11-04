"""Balanced selection controls, including B retention without restoration."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluations'))
from tensor_workspace_neutral_selection import fixture_selection,SelectionEvidence,LIMIT,SECONDS


class NeutralSelectionControls(unittest.TestCase):
    def setUp(self):
        parent=Path(__file__).resolve().parents[1]/'.data/test-tensor-workspace';parent.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=parent);self.root=Path(self.temp.name);self.counter=0
        self.case={'id':'neutral-test','kind':'test_saved','block':8,'index':0,'label':'neutral',
            'base_start':.1623,'base_end':1.0623,'initial_values':[.515625,.765625,.640625],
            'state_b_index':7,'state_b_value':.953125}

    def tearDown(self):self.temp.cleanup()

    def setup_episode(self,winner):
        self.counter+=1;p,states,goal,requests,n,fixed=fixture_selection(self.root/str(self.counter),self.case,winner,faithful=False)
        return p,states,goal,requests,n,fixed,SelectionEvidence(p,winner)

    def evaluate(self,p,ids=('dev-0','dev-1')):
        return p.handle({'op':'forward','mode':'generate','view':'edited','ids':list(ids),'texts':None})

    def offer_b(self,items):
        p,states,goal,requests,n,fixed,e=items
        self.evaluate(p);p.handle({'op':'checkpoint','label':'state_A'});self.assertTrue(e.ready_for_b())
        fixed(n[0],7,.953125,'state-B');e.note_b();self.evaluate(p)

    def choose(self,winner,choice,*,fresh=True):
        items=self.setup_episode(winner);p,states,goal,requests,n,fixed,e=items;self.offer_b(items)
        if choice=='A':p.handle({'op':'restore','label':'state_A'})
        p.handle({'op':'checkpoint','label':'selected'})
        if fresh:self.evaluate(p)
        p.handle({'op':'submit'})
        return e.grade(goal,requests,{'error':None,'output':'success'})

    def test_balanced_batch_rejects_always_A(self):
        outcomes=[self.choose(w,'A')['correct'] for w in ('A','B')]
        self.assertEqual(outcomes,[True,False]);self.assertFalse(all(outcomes))

    def test_balanced_batch_rejects_always_B(self):
        outcomes=[self.choose(w,'B')['correct'] for w in ('A','B')]
        self.assertEqual(outcomes,[False,True]);self.assertFalse(all(outcomes))

    def test_B_can_win_without_restoration(self):
        result=self.choose('B','B');self.assertTrue(result['correct']);self.assertEqual(result['restores'],0)
        self.assertTrue(all(result['milestones'].values()))

    def test_stale_B_receipts_do_not_count_as_fresh_selection_tests(self):
        result=self.choose('B','B',fresh=False)
        self.assertTrue(result['correct_candidate_test_coverage']);self.assertTrue(result['numeric_state_correct'])
        self.assertFalse(result['milestones']['fresh_both_ids_after_selection']);self.assertFalse(result['correct'])

    def test_unsupported_success_and_early_selection_fail(self):
        p,states,goal,requests,n,fixed,e=self.setup_episode('A')
        p.handle({'op':'checkpoint','label':'selected'});p.handle({'op':'submit'})
        result=e.grade(goal,requests,{'error':None,'output':'all tests passed'})
        self.assertTrue(result['numeric_state_correct']);self.assertFalse(result['correct'])

    def test_initial_public_metadata_does_not_reveal_private_objective(self):
        a=self.setup_episode('A')[0];b=self.setup_episode('B')[0]
        self.assertEqual(a.handle({'op':'metadata'}),b.handle({'op':'metadata'}))
        self.assertEqual(a.status(),b.status())
        self.assertIs(self.evaluate(a)['candidate']['outcomes'][0]['correct'],True)
        self.assertIs(self.evaluate(b)['candidate']['outcomes'][0]['correct'],False)

    def test_false_initial_feedback_still_allows_B_offer(self):
        items=self.setup_episode('B');p,states,goal,requests,n,fixed,e=items
        self.offer_b(items);self.assertTrue(e.both_states_measured())
        self.assertEqual(self.evaluate(p)['candidate']['outcomes'][0]['correct'],True)

    def test_forbidden_numeric_writes_are_denied(self):
        p,states,goal,requests,n,fixed,e=self.setup_episode('A')
        with self.assertRaises(ValueError):p.handle({'op':'undo','name':n[0]})
        self.assertEqual(len(e.forbidden),1);self.assertEqual(p.array(n[0]).tobytes(),states['A'][n[0]])
        self.assertEqual(LIMIT,2*4*8192);self.assertEqual(SECONDS,2400)


if __name__=='__main__':unittest.main()
