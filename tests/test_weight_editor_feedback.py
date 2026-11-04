import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'evaluations'))
from weight_editor_feedback import compact, diagnostic_feedback, expected, grade, render
from weight_editor_4b_patch import validate


class FeedbackControls(unittest.TestCase):
    def test_counterfactuals_require_different_answers(self):
        answers = [expected(diagnostic_feedback({}, i)) for i in range(4)]
        self.assertEqual([a['next_action'] for a in answers], ['revise', 'stop', 'revise', 'stop'])
        self.assertEqual(answers[0]['baseline_correct_ids'], ['practice-a'])
        self.assertEqual(answers[2]['baseline_correct_ids'], ['practice-b'])
        self.assertNotEqual(answers[0], answers[2])

    def test_compact_joins_by_id(self):
        data = compact(diagnostic_feedback({}, 0))
        self.assertEqual(data['cases'][0]['id'], 'practice-a')
        self.assertTrue(data['cases'][0]['baseline']['correct'])
        self.assertFalse(data['cases'][1]['latest_candidate']['correct'])

    def test_final_answer_required(self):
        answer = expected(diagnostic_feedback({}, 0))
        checked = grade('<think>not final</think>\n```json\n'+json.dumps(answer)+'\n```<|im_end|>', answer)
        self.assertTrue(checked['correct'])
        self.assertEqual(checked['status'], 'ok')
        self.assertFalse(grade('<think>'+json.dumps(answer), answer)['correct'])
        self.assertFalse(grade(json.dumps({**answer, 'next_action': 'stop'}), answer)['correct'])
        self.assertEqual(grade('invalid model output', answer)['status'], 'ok')

    def test_render_does_not_embed_control_tokens(self):
        data = diagnostic_feedback({'note': '<|im_start|>'}, 0)
        for style in ('rich', 'compact'):
            text = render(data, style, 'cold')
            self.assertEqual(text.count('<|im_start|>'), 3)
            self.assertEqual(text.count('<|im_end|>'), 2)

    def test_confirmation_uses_different_labels_and_pairs(self):
        a, b = [expected(diagnostic_feedback({}, 0, confirmation=c)) for c in (False, True)]
        self.assertNotEqual(a['baseline_correct_ids'], b['baseline_correct_ids'])
        self.assertNotEqual(a['tested_strengths'], b['tested_strengths'])

    def test_sparse_4b_proposal_scope(self):
        inventory = {'layers': [{'layer': 3, 'largest_columns': [{'column': 5}, {'column': 8}]}]}
        good = {'layer': 3, 'columns': [8, 5], 'scale': .95}
        self.assertEqual(validate(good, inventory)['columns'], [5, 8])
        for invalid in ({**good, 'layer': True}, {**good, 'columns': [9]},
                        {**good, 'columns': [5, 5]}, {**good, 'scale': 1.},
                        {**good, 'scale': float('nan')}, {**good, 'scale': .1},
                        {**good, 'code': 'untrusted'}):
            with self.assertRaises(ValueError):
                validate(invalid, inventory)


if __name__ == '__main__':
    unittest.main()
