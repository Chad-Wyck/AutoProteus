"""Static evidence only: these guest programs are never executed by this test."""
import copy
import json
import shlex
import unittest

from controller.tool_evidence import python_results


class ToolEvidenceTests(unittest.TestCase):
    def event(self,imports='import json',expression='json.dumps(result, indent=2, ensure_ascii=False)'):
        program=(imports+'\nfrom autoproteus.tools import Workspace\nfrom pathlib import Path\n'
                 "ws=Workspace(Path.cwd())\nresult=ws.execute('csv_preview', {'path':'activation/fresh.csv'})\n"
                 "print('Result:', "+expression+")\n")
        receipt={'path':'activation/fresh.csv','rows':[['café','猫'],['line\r\nbreak','2']],'truncated':False}
        return {'ok':True,'action':{'tool':'run_command','arguments':{'command':
            'cd /work/task && PYTHONPATH=/work/task/harness python3 -c '+shlex.quote(program)}},
            'result':{'exit_code':0,'output':'Result: '+json.dumps(receipt,indent=2,ensure_ascii=False)+'\nNext notice.\n'}},receipt

    def test_labelled_multiline_json_result_and_import_aliases(self):
        for imports,expression in [('import json','json.dumps(result, indent=2, ensure_ascii=False)'),
                ('import json as j','j.dumps(result, indent=2)'),
                ('from json import dumps as encode','encode(result, indent=2)'),
                ('import json','json.dumps(ws.execute("csv_preview", {"path":"activation/fresh.csv"}), indent=2)')]:
            event,receipt=self.event(imports,expression)
            self.assertEqual(python_results(event,'csv_preview',receipt['path']),[receipt])

    def test_failed_wrong_input_forged_and_shadowed_results_are_not_proof(self):
        event,receipt=self.event()
        for alteration in ('failed','wrong-input','unrelated-print','shadow-json','shadow-dumps','unsupported-encoder'):
            bad=copy.deepcopy(event);args=bad['action']['arguments']
            if alteration=='failed': bad['result']['exit_code']=1
            else:
                command=args['command']
                if alteration=='wrong-input': command=command.replace('activation/fresh.csv','elsewhere.csv')
                elif alteration=='unrelated-print': command=command.replace('json.dumps(result,','json.dumps({},')
                elif alteration=='shadow-json': command=command.replace('import json','import other as json')
                elif alteration=='shadow-dumps':
                    command=command.replace("print(","json.dumps = replacement\nprint(")
                else: command=command.replace('indent=2','default=custom')
                args['command']=command
            with self.subTest(alteration=alteration):
                self.assertEqual(python_results(bad,'csv_preview',receipt['path']),[])

    def test_output_requires_the_observed_prefix_complete_object_and_clean_line_end(self):
        event,receipt=self.event()
        for output in ('Other: '+json.dumps(receipt), 'Result: '+json.dumps(receipt)[:-2],
                       'Result: '+json.dumps(receipt)+'garbage', 'Result: not JSON\n'+json.dumps(receipt)):
            event['result']['output']=output
            self.assertEqual(python_results(event,'csv_preview',receipt['path']),[])
