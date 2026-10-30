"""Trusted guest-only probe; candidate imports occur only inside main.

The pure byte oracles can be checked on the host. Never call main on the host.
VM calibration is mandatory before using this probe for model scores.
"""
import configparser
import json
from pathlib import Path
import sys

FEATURES=('ini_sections','normalize_newlines')


def oracle_ini(raw):
    text=raw.decode('utf-8')
    if len(text)>100000:raise ValueError('Too many characters')
    parser=configparser.ConfigParser(interpolation=None,strict=True)
    parser.read_string(text)
    return parser.sections()


def oracle_newlines(raw,newline='lf'):
    if newline not in ('lf','crlf'):raise ValueError('Bad newline')
    text=raw.decode('utf-8')
    if len(text)>100000:raise ValueError('Too many input characters')
    text=text.replace('\r\n','\n').replace('\r','\n')
    if newline=='crlf':text=text.replace('\n','\r\n')
    if len(text)>100000:raise ValueError('Too many output characters')
    result=text.encode('utf-8')
    return result,{'bytes':len(result),'changed':result!=raw}


def same(a,b):
    if type(a) is not type(b):return False
    if isinstance(a,dict):return a.keys()==b.keys() and all(same(a[k],b[k]) for k in a)
    if isinstance(a,list):return len(a)==len(b) and all(same(x,y) for x,y in zip(a,b))
    return a==b


def main():
    import os
    if os.name!='posix' or Path.cwd().as_posix()!='/work/task':raise RuntimeError('Independent VM guest only')
    feature=sys.argv[1]
    if feature not in FEATURES:raise ValueError('Unknown feature')
    sys.path.insert(0,str(Path('harness').resolve()))
    from autoproteus.tools import Workspace
    from autoproteus.providers import tool_definitions,tool_instructions
    root=Path('novel-probe-work').resolve();root.mkdir()
    workspace=Workspace(root);checks={};errors={}
    def check(name,callback):
        try:checks[name]=callback() is True
        except Exception as error:checks[name]=False;errors[name]=type(error).__name__+': '+str(error)[:300]
    def rejects(callback):
        try:callback()
        except (ValueError,OSError,configparser.Error):return True
        return False
    def call(path,**args):return workspace.execute(feature,{'path':path,**args})
    definitions={x['function']['name']:x['function'] for x in tool_definitions(False)}
    check('registered',lambda:feature in definitions and feature+':' in tool_instructions(False))
    check('schema',lambda: definitions[feature]['parameters']['properties']['path']['type']=='string'
          and set(definitions[feature]['parameters']['required'])=={'path'}
          and (feature=='ini_sections' or set(definitions[feature]['parameters']['properties']['newline']['enum'])=={'lf','crlf'}))
    if feature=='ini_sections':
        cases={'empty':b'','order':'[DEFAULT]\nx=1\n[猫]\na=café\n[API]\nb=2\n'.encode(),
               'exact':('[猫]\nx='+('é'*(100000-len('[猫]\nx=')))).encode()}
        for name,raw in cases.items():
            (root/name).write_bytes(raw)
            def verify(name=name,raw=raw):
                return same(call(name),{'path':name,'sections':oracle_ini(raw)}) and (root/name).read_bytes()==raw
            check(name,verify)
        bad={'over':('[猫]\nx='+('é'*(100001-len('[猫]\nx=')))).encode(), 'invalid':b'not a section',
             'duplicate-section':b'[A]\nx=1\n[A]\ny=2\n', 'bad-utf8':b'\xff'}
    else:
        cases=[('empty',b'',{}),('default','café\r\n猫\rthird\n'.encode(),{}),
               ('crlf','café\n猫\rend\r\n'.encode(),{'newline':'crlf'}),
               ('unchanged','café\n猫\n'.encode(),{}),('exact',('é'*99999+'\n').encode(),{}),
               ('crlf-exact',('é'*99998+'\n').encode(),{'newline':'crlf'})]
        for name,raw,args in cases:
            (root/name).write_bytes(raw)
            def verify(name=name,raw=raw,args=args):
                final,expected=oracle_newlines(raw,**args)
                return same(call(name,**args),{'path':name,**expected}) and (root/name).read_bytes()==final
            check(name,verify)
        bad={'over':('é'*100001).encode(),'bad-utf8':b'\xff'}
        for name,raw,args in [('overflow',('é'*99999+'\n').encode(),{'newline':'crlf'}),('bad-option',b'a\r\n',{'newline':'invalid'})]:
            (root/name).write_bytes(raw)
            check(name,lambda name=name,raw=raw,args=args:rejects(lambda:call(name,**args)) and (root/name).read_bytes()==raw)
    for name,raw in bad.items():
        (root/name).write_bytes(raw)
        check(name,lambda name=name,raw=raw:rejects(lambda:call(name)) and (root/name).read_bytes()==raw)
    external=Path('novel-valid-external.ini').resolve();raw=b'[External]\nx=1\r\n';external.write_bytes(raw)
    check('traversal-valid-input',lambda:rejects(lambda:call('../'+external.name)) and external.read_bytes()==raw)
    (root/'escape').symlink_to(external)
    check('escaping-symlink-valid-input',lambda:rejects(lambda:call('escape')) and external.read_bytes()==raw)
    (root/'folder').mkdir()
    check('directory',lambda:rejects(lambda:call('folder')))
    check('missing',lambda:rejects(lambda:call('missing')))
    result={'feature':feature,'passed':bool(checks) and all(checks.values()),'checks':checks,'errors':errors}
    Path('novel-result.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
