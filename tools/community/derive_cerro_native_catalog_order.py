"""Compose the open catalog with its two real model providers on historical native Cerro."""
import argparse
import ast
import hashlib
from pathlib import Path
import shutil

CATALOG = 'b1fcae22bf92978d463af8e37cc816ccb5e4425b55b1ce89d9ba1c24ab112bd0'
LEGACY = '6f43141a41d9a1d04a9f885cea76af6fc490d14b5af3df8a2652605cfd86c7f3'
SEASON = '2e622200c2719704ac4ec23ec30ab922d2239e36c8b5b5403933c2b29e5340df'


def derive(catalog, legacy, output):
    for file, digest in ((catalog/'__manifest__.py',CATALOG),(legacy/'__manifest__.py',LEGACY),
                         (legacy/'models/step_temporada.py',SEASON)):
        if hashlib.sha256(file.read_bytes()).hexdigest()!=digest:
            raise ValueError('An original catalog or native HR provider differs from the Cerro source')
    source = (catalog/'__manifest__.py').read_text()
    spec = ast.literal_eval(source)
    old = ast.literal_eval((legacy/'__manifest__.py').read_text())
    assert spec['depends']==['step_agriculture_core'] and old['version']=='18.0.1.4.0'
    assert old['license']==spec['license']=='LGPL-3'
    assert 'step_agriculture_core' not in old['depends']
    shutil.copytree(catalog,output,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    # The historical native Step HR owns step.temporada too. Its declaration
    # must precede the multi-company extension in every complete registry.
    changed=source.replace("'18.0.1.1.0'","'18.0.1.1.1'").replace("['step_agriculture_core']","['step_agriculture_core','step_hr']")
    expected=dict(spec,version='18.0.1.1.1',depends=['step_agriculture_core','step_hr'])
    assert ast.literal_eval(changed)==expected
    (output/'__manifest__.py').write_text(changed)
    return hashlib.sha256(changed.encode()).hexdigest()


def declarations(file):
    tree = ast.parse(file.read_text(encoding='utf8'))
    for definition in tree.body:
        if isinstance(definition, ast.ClassDef):
            attrs={node.targets[0].id:node for node in definition.body if isinstance(node, ast.Assign)
                   and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('_name','_inherit')}
            if '_name' in attrs:
                yield ast.literal_eval(attrs['_name'].value),attrs


def derive_core(core, legacy, output):
    from check_cerro_studio_strict import tree_sha
    if tree_sha(core)!='c033b2fa4a1c45072abeb1707eba9cd672167d300707bd0d02981654870258db' or tree_sha(legacy)!='e730c267fdf497578ba46aef221a66510f9134f404ab1513304bdb5c9f017890':
        raise ValueError('The full agricultural core or original historical HR sources changed')
    originals = {name for file in (legacy/'models').glob('*.py') for name,_ in declarations(file)}
    rewritten={}
    adopted=set()
    for file in (core/'models').glob('*.py'):
        lines=file.read_text(encoding='utf8').splitlines(keepends=True)
        changes=[]
        for name,attrs in declarations(file):
            assert name in originals and name not in adopted
            adopted.add(name)
            if '_inherit' in attrs:
                member=attrs['_inherit']
                parents=ast.literal_eval(member.value)
                parents=[parents] if isinstance(parents,str) else list(parents)
                assert name not in parents
                changes.append((member.lineno-1,member.end_lineno,'    _inherit = '+repr([name,*parents])+'\n'))
            else:
                member=attrs['_name']
                changes.append((member.end_lineno,member.end_lineno,'    _inherit = '+repr(name)+'\n'))
        if changes:
            for first,last,value in sorted(changes,reverse=True):
                lines[first:last]=[value]
            result=''.join(lines)
            ast.parse(result)
            rewritten[file.relative_to(core)]=result
    assert {'step.fundo','step.temporada','step.especie','step.centro.costo','step.work.schedule'}<=adopted
    shutil.copytree(core,output,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for file,code in rewritten.items():
        (output/file).write_text(code,encoding='utf8')
    manifest=output/'__manifest__.py'
    source=manifest.read_text(encoding='utf8')
    spec=ast.literal_eval(source)
    assert spec['version']=='18.0.1.1.3' and 'step_hr' not in spec['depends']
    changes=source.replace("'18.0.1.1.3'","'18.0.1.1.4'").replace("'depends': [","'depends': ['step_hr', ")
    assert ast.literal_eval(changes)==dict(spec,version='18.0.1.1.4',depends=['step_hr',*spec['depends']])
    manifest.write_text(changes,encoding='utf8')
    return {'native_core':tree_sha(output),'shared_models':sorted(adopted)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('catalog','legacy','output'):
        parser.add_argument('--'+arg,type=Path,required=True)
    args=parser.parse_args()
    print(derive(args.catalog,args.legacy,args.output))
