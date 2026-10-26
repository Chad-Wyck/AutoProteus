"""Bounded static evidence for guest Python calls; never imports or runs a program.

This recognizes ordinary observed routes, not a security proof against a hostile
program. Dynamic calls and control flow remain unmeasured rather than guessed.
"""
import ast
import json
import shlex


def python_invocations(command):
    if not isinstance(command,str) or len(command)>65536:
        return []
    try:
        args=shlex.split(command)
        if args[:1]==['cd']:
            if len(args)<4 or args[1] not in ('.','harness','/work/task','/work/task/harness') or args[2]!='&&':return []
            args=args[3:]
        if args and args[0] in ('PYTHONPATH=harness','PYTHONPATH=/work/task/harness'):
            args=args[1:]
        if len(args)!=3 or args[:2]!=['python3','-c']:return []
        tree=ast.parse(args[2])
        constructors=set();instances=set();results={};records=[]
        def invocation(value):
            if not (isinstance(value,ast.Call) and isinstance(value.func,ast.Attribute) and value.func.attr=='execute'):
                return None
            receiver=value.func.value
            instance=isinstance(receiver,ast.Name) and receiver.id in instances
            inline=(isinstance(receiver,ast.Call) and isinstance(receiver.func,ast.Name) and receiver.func.id in constructors)
            if not (instance or inline) or not value.args or not isinstance(value.args[0],ast.Constant) or not isinstance(value.args[0].value,str):return None
            try:arguments=ast.literal_eval(value.args[1]) if len(value.args)>1 else None
            except (ValueError,SyntaxError,RecursionError):arguments=None
            record={'tool':value.args[0].value,'arguments':arguments,'print_prefixes':[]}
            if len(records)<64:records.append(record)
            return record
        for node in tree.body:
            if isinstance(node,(ast.Import,ast.ImportFrom)):
                for alias in node.names:
                    name=alias.asname or alias.name.split('.')[0]
                    constructors.discard(name);instances.discard(name);results.pop(name,None)
                    if (isinstance(node,ast.ImportFrom) and node.module in ('autoproteus.tools','harness.autoproteus.tools')
                            and alias.name=='Workspace'):
                        constructors.add(name)
            elif isinstance(node,(ast.Assign,ast.AnnAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                value=node.value
                created=(isinstance(value,ast.Call) and isinstance(value.func,ast.Name) and value.func.id in constructors)
                record=invocation(value)
                for target in targets:
                    if isinstance(target,ast.Name):
                        constructors.discard(target.id);instances.discard(target.id);results.pop(target.id,None)
                        if created:instances.add(target.id)
                        if record:results[target.id]=record
                    elif isinstance(target,ast.Attribute) and isinstance(target.value,ast.Name):
                        instances.discard(target.value.id)
            elif isinstance(node,ast.Expr):
                value=node.value
                if isinstance(value,ast.Call) and isinstance(value.func,ast.Name) and value.func.id=='print' and value.args and not value.keywords:
                    last=value.args[-1]
                    record=results.get(last.id) if isinstance(last,ast.Name) else invocation(last)
                    prefixes=value.args[:-1]
                    if record and all(isinstance(part,ast.Constant) and isinstance(part.value,str) for part in prefixes):
                        record['print_prefixes'].append(' '.join(part.value for part in prefixes)+(' ' if prefixes else ''))
                else:invocation(value)
            else:
                # Do not follow branches, loops, functions or potential rebinding.
                constructors.clear();instances.clear();results.clear()
        return records
    except (ValueError,TypeError,SyntaxError,RecursionError):
        return []


def python_results(data, tool, path):
    """Printed result of an observed literal call on the actual fresh input."""
    result=data.get('result',{})
    if not data.get('ok') or result.get('exit_code')!=0:return []
    records=python_invocations(data.get('action',{}).get('arguments',{}).get('command',''))
    values=[]
    for record in records:
        if record['tool']!=tool or not isinstance(record['arguments'],dict) or record['arguments'].get('path')!=path:continue
        for line in result.get('output','').splitlines():
            for prefix in record['print_prefixes']:
                if not line.startswith(prefix):continue
                payload=line[len(prefix):]
                try:value=json.loads(payload)
                except (ValueError,RecursionError):
                    try:value=ast.literal_eval(payload)
                    except (ValueError,SyntaxError,RecursionError):continue
                if isinstance(value,dict):values.append(value)
    return values
