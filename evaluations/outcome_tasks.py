"""Outcome-only cases: public goals have no required tool name or seed edit."""
import csv
import io
import json

from activation_use import same_json


def _task(name,instruction,fixtures,outputs):
    return {'name':name,'task':instruction+' Preserve every input file byte for byte. Verify the saved outputs and finish completed.',
        'fixtures':fixtures,'checks':[{'path':path,'kind':kind,'expected':value} for path,(kind,value) in outputs.items()]
            +[{'path':path,'kind':'text','expected':text} for path,text in fixtures.items()]}


def _copy(suffix):
    path='incoming/'+suffix+'.txt';output='delivery/'+suffix+'.txt';text='Notes '+suffix+' café 猫\r\nKeep the blank line.\r\n\r\n'
    return _task('copy-'+suffix,'Copy '+path+' exactly to '+output+'.',{path:text},{output:('text',text)})


def _settings(suffix):
    path='incoming/'+suffix+'.json';output='delivery/'+suffix+'.json'
    value={'theme':'light','count':3,'owner':'猫','enabled':False}
    if suffix=='later':value.update(count=7,owner='café',enabled=True)
    return _task('settings-'+suffix,'Save a copy of '+path+' in '+output+' with theme changed to dark. Keep all other keys, values and JSON types exactly as supplied, including integer count and boolean enabled.',
        {path:json.dumps(value,ensure_ascii=False)},{output:('json',{**value,'theme':'dark'})})


def _csv(suffix):
    fixtures={f'incoming/{suffix}-a.csv':'name,value\r\n"café, 猫",1\r\n"two\r\nlines",2\r\nlast,3\r\n',
        f'incoming/{suffix}-b.csv':'id,label\n1,blue\n2,green\n3,red\n4,white\n',f'incoming/{suffix}-empty.csv':''}
    if suffix=='later':
        fixtures={f'incoming/{suffix}-a.csv':'name,value\r\n"猫, café",9\r\n"new\r\nrecord",8\r\n',
            f'incoming/{suffix}-b.csv':'id,label\n5,yellow\n6,"red, blue"\n',f'incoming/{suffix}-empty.csv':'name,value\r\n'}
    files=[]
    for path,text in sorted(fixtures.items()):
        rows=list(csv.reader(io.StringIO(text,newline='')))
        files.append({'path':path,'columns':rows[0] if rows else [],'rows':max(0,len(rows)-1),'preview':rows[1:3]})
    output='delivery/'+suffix+'-index.json'
    return _task('csv-'+suffix,'Several batches of CSV files need indexing. Read '+', '.join(sorted(fixtures))+'. Save '+output+
        ' as a JSON object with files (an array in path order) and total_data_rows. Each files entry must have path, columns (the header fields, or [] for an empty file), '
        'rows (number of data records excluding the header) and preview (the first two data records, without the header). Use JSON integers for counts. Respect quoted commas and embedded newlines. Another batch will arrive later.',
        fixtures,{output:('json',{'files':files,'total_data_rows':sum(f['rows'] for f in files)})})


def _logs(suffix):
    fixtures={f'incoming/{suffix}-a.jsonl':'{"level":"info","message":"café"}\r\n\r\nnot-json\r\n{"level":"warn"}\r\n',
        f'incoming/{suffix}-b.jsonl':'{"level":"error"}\n{"level":7}\n{"level":"info","message":"猫"}\n[]\n'}
    if suffix=='later':
        fixtures={f'incoming/{suffix}-a.jsonl':'{"level":"warn"}\r\n{"level":"warn","message":"猫"}\r\n\r\nfalse\r\n',
            f'incoming/{suffix}-b.jsonl':'bad-json\n{"level":"debug"}\n{"level":"info","message":"café"}\n'}
    files=[];problems=[]
    for path,text in sorted(fixtures.items()):
        levels={};count=0
        for line,content in enumerate(text.splitlines(),1):
            if not content.strip():continue
            try:value=json.loads(content)
            except ValueError:problems.append({'path':path,'line':line,'reason':'invalid_json'});continue
            if not isinstance(value,dict) or not isinstance(value.get('level'),str):
                problems.append({'path':path,'line':line,'reason':'invalid_record'});continue
            count+=1;level=value['level'];levels[level]=levels.get(level,0)+1
        files.append({'path':path,'records':count,'levels':levels})
    prefix='delivery/'+suffix
    return _task('logs-'+suffix,'Summarize '+', '.join(sorted(fixtures))+'. Blank lines are ignored. A valid record is a JSON object whose level is a string; count levels exactly as written. '
        'Save '+prefix+'-summary.json as {"files":[{"path":...,"records":...,"levels":{...}}]} in path order. '
        'Save '+prefix+'-problems.json as an array of {"path":...,"line":...,"reason":...}, ordered by path and original one-based line number. '
        'Use reason invalid_json for malformed JSON and invalid_record for other invalid records. Use JSON integers for all counts and line numbers. Another batch will arrive later.',
        fixtures,{prefix+'-summary.json':('json',{'files':files}),prefix+'-problems.json':('json',problems)})


def task_pack():
    return [{'name':name,'starter_solvable':True,'case_kind':'simple' if simple else 'repeated_processing',
        'first':make('first'),'reuse':make('later')}
        for name,simple,make in [('copy',True,_copy),('settings',True,_settings),('csv-index',False,_csv),('log-summary',False,_logs)]]


def grade_outputs(files,task):
    checks=[]
    for rule in task['checks']:
        try:
            data=files.read(rule['path'])
            passed=(data==rule['expected'].encode('utf-8') if rule['kind']=='text' else same_json(json.loads(data),rule['expected']))
        except (OSError,ValueError,UnicodeError,RecursionError):passed=False
        checks.append({'path':rule['path'],'passed':passed})
    return {'passed':all(r['passed'] for r in checks),'checks':checks}


def oracle_controls(cases):
    class Files:
        def __init__(self,values):self.values=values
        def read(self,path):
            if path not in self.values:raise ValueError('Missing file')
            return self.values[path]
    result=[]
    for case in cases:
        for stage in ('first','reuse'):
            task=case[stage];values={r['path']:(r['expected'].encode('utf-8') if r['kind']=='text' else json.dumps(r['expected'],ensure_ascii=False).encode()) for r in task['checks']}
            good=grade_outputs(Files(values),task)['passed']
            bad=dict(values);bad.pop(task['checks'][0]['path'])
            missing=grade_outputs(Files(bad),task)['passed']
            bad=dict(values);bad[next(iter(task['fixtures']))]=b'changed input'
            changed=grade_outputs(Files(bad),task)['passed']
            result.append({'case':case['name'],'stage':stage,'positive':good,'missing_output_rejected':not missing,
                'changed_input_rejected':not changed,'passed':good and not missing and not changed})
    if not all(r['passed'] for r in result):raise ValueError('Outcome artifact oracle failed')
    return {'passed':True,'cases':result,'scope':'Artifact oracles only; extension is never a prerequisite for correct task completion.'}
