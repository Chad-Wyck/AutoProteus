"""Independent guest-only feature checks. This file never imports candidates on the host."""
import json
from pathlib import Path
import subprocess
import sys
import threading

sys.path.insert(0, str(Path('harness').resolve()))
from autoproteus.tools import Workspace
from autoproteus.providers import tool_definitions, tool_instructions

# This is the task's fixed contract, independent of candidate-defined constants.
WRITE_LIMIT = 100000

feature = sys.argv[1]
root = Path('feature-probe').resolve()
root.mkdir(exist_ok=True)
w = Workspace(root, terminal=False)
checks, errors = {}, {}

def check(name, callback):
    try:
        checks[name] = bool(callback())
    except Exception as error:
        checks[name] = False
        errors[name] = type(error).__name__ + ': ' + str(error)[:500]

def rejects(callback):
    try:
        callback()
        return False
    except (ValueError, OSError, TypeError):
        return True

def data(name, text):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode('utf-8'))
    return path

data('sample.txt', 'café\r\n猫 and dog\n')
data('empty.txt', '')
data('no-newline.txt', 'one two')
data('large.txt', '猫' * WRITE_LIMIT)
data('too-large.txt', 'x' * (WRITE_LIMIT+1))
(root/'binary.txt').write_bytes(b'\xff\xfe\x00')
(root/'folder').mkdir(exist_ok=True)
outside = root.parent / 'probe-outside.txt'
outside.write_bytes(b'outside\r\n')
(root/'outside-link').symlink_to(outside)

functions = {t['function']['name']: t['function'] for t in tool_definitions(True)}
check('registered', lambda: feature in functions)
check('json_description', lambda: feature+':' in tool_instructions(True))
expected_arguments = {'path': 'string'} if feature=='file_summary' else {'path':'string','content':'string'}
check('schema', lambda: all(functions[feature]['parameters']['properties'][name]['type']==kind for name,kind in expected_arguments.items()) and set(functions[feature]['parameters']['required'])==set(expected_arguments))

def summary(name):
    result = w.execute('file_summary', {'path':name})
    raw = (root/name).read_bytes()
    text = raw.decode('utf-8')
    return all(result[key]==value for key,value in {'path':name,'bytes':len(raw),'characters':len(text),'lines':len(text.splitlines()),'words':len(text.split())}.items())

def append_case(name, content):
    path = root/name
    before = path.read_bytes() if path.exists() else b''
    result = w.execute('append_text', {'path':name,'content':content})
    expected = before+content.encode('utf-8')
    return path.read_bytes()==expected and result['path']==name and result['bytes']==len(expected)

def invalid_append(name, content):
    path = root/name
    before = path.read_bytes() if path.is_file() else None
    rejected = rejects(lambda:w.execute('append_text',{'path':name,'content':content}))
    after = path.read_bytes() if path.is_file() else None
    return rejected and before==after

if feature=='file_summary':
    for name in ('sample.txt','empty.txt','no-newline.txt','large.txt'):
        check('counts_'+name, lambda name=name:summary(name))
    for name in ('too-large.txt','binary.txt','folder','../probe-outside.txt',str(outside),'outside-link','missing.txt'):
        check('reject_'+name,lambda name=name:rejects(lambda:w.execute(feature,{'path':name})))
    check('does_not_modify',lambda:(root/'sample.txt').read_bytes()=='café\r\n猫 and dog\n'.encode())
elif feature=='append_text':
    for name,content in [('sample.txt','élan\r\n'),('empty.txt','猫'),('new/deep.txt','made\n'),('sample.txt',''),('large.txt','')]:
        check('append_'+name+('_empty' if content=='' else ''),lambda name=name,content=content:append_case(name,content))
    data('near-limit.txt','x'*(WRITE_LIMIT-1))
    check('limit_exact',lambda:append_case('near-limit.txt','猫'))
    for name,content in [('large.txt','x'),('too-large.txt',''),('binary.txt','ok'),('folder','x'),('sample.txt',7),('sample.txt',None),('sample.txt','x'*(WRITE_LIMIT+1)),('../probe-outside.txt','x'),(str(outside),'x'),('outside-link','x')]:
        check('reject_'+name+'_'+type(content).__name__+('_long' if isinstance(content,str) and len(content)>WRITE_LIMIT else ''),lambda name=name,content=content:invalid_append(name,content))
    check('outside_unchanged',lambda:outside.read_bytes()==b'outside\r\n')

cancelled=threading.Event()
cancelled.set()
stopped=Workspace(root,terminal=False,cancel=cancelled)
try:
    stopped.execute(feature,{'path':'sample.txt','content':'x'} if feature=='append_text' else {'path':'sample.txt'})
    checks['cancelled']=False
except Exception as error:
    checks['cancelled']=type(error).__name__=='Cancelled'

suite=subprocess.run([sys.executable,'-m','unittest','discover','-s','tests','-v'],cwd='harness',stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=60)
result={'feature':feature,'checks':checks,'errors':errors,'suite':{'exit_code':suite.returncode,'output':suite.stdout.decode(errors='replace')[:30000]}}
Path('benchmark-probe.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
print(json.dumps({'checks':checks,'suite_exit':suite.returncode},ensure_ascii=False))
