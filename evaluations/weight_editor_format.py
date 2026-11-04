"""Render editor evidence as data, keeping chat-control tokens out of the body."""
import json

from weight_editor_runtime import require
from weight_repair_protocol import PROTOCOL


EDITOR_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


def render_feedback(system, feedback, golds):
    prefix = '<|im_start|>user\n'
    suffix = '<|im_end|>\n<|im_start|>assistant\n<think>\n'
    visible = dict(feedback)
    examples = []
    for case in feedback['development_cases']:
        text = case['rendered_prompt']
        require(text.startswith(prefix) and text.endswith(suffix), 'Unexpected target prompt framing')
        question = text[len(prefix):-len(suffix)].removesuffix('\n'+PROTOCOL['instruction'])
        examples.append({'id': case['id'], 'problem': question})
    visible['development_cases'] = examples
    visible['development_gold_answers'] = {case['id']: golds[case['id']] for case in examples}
    visible['reference_strengths'] = {'baseline': [1., 1.], 'fixed_control': [1.1, 1.1]}
    # A JSON string can still contain literal special-token spellings. Escaping
    # '<' preserves the decoded data without creating tokenizer control IDs.
    body = json.dumps(visible, ensure_ascii=True, allow_nan=False).replace('<', r'\u003c')
    return '<|im_start|>system\n' + system + '<|im_end|>\n' + prefix + body + EDITOR_SUFFIX
