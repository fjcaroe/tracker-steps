"""Install and qualify the Cerro receipt-form extension on its own copy of the accepted collection release."""
import argparse
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

from build_cerro_verified_172 import build
from compare_cerro_studio_receipts import compare, receipt


HERE = Path(__file__).resolve().parent
RAM = Path('/dev/shm/steps-cerro-u46')
SOURCE = 'COMMUNITY_CERRO_BOM_PACKING_20261127U46A'
TARGET = 'COMMUNITY_CERRO_BOM_PACKING_20261127U46E'
MODULE = 'step_cerro_receipt_form'
PARENT = 'fd3ad217938e4c6e540d972ff31378b95e2728b89b3db7030411015c95ef6a90'
REFERENCES = {
    'operations': ('native-receipt-form-operations-v2-u46.json','78525a34766fcf93ac4f8c2eb4a0fd991ec6bbf2e4a1cdacb63d7fe94ac0a08e'),
    'quality': ('native-receipt-form-quality-u46.json','6d19b54997091150a346a9460ae70a607adf95bba441daf67c5c512d0e46f745'),
    'projections': ('native-receipt-form-projections-u46.json','a965df73f28cd6ecbd1027a543c7127bc3f6010370438cf10e84b0903dc82bf5'),
}
TOOLS = (
    'audit_cerro_original_schema','load_cerro_catalog_contracts','check_cerro_receipt_form_catalogue',
    'check_cerro_followup_catalogue','check_cerro_local_catalogue','check_cerro_pack_schema',
    'check_cerro_receipt_catalogue','probe_cerro_receipt_form','probe_cerro_receipt_stock','probe_cerro_receipt_scope',
    'probe_cerro_studio_fullread','probe_cerro_studio_navigation','probe_cerro_studio_client','probe_cerro_studio_views',
    'probe_cerro_packing_landscape',
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {p.relative_to(folder).as_posix(): digest(p) for p in folder.rglob('*') if p.is_file() and not p.is_symlink()}


def run(artifacts, result):
    source = RAM/'packing'
    target = RAM/'receipt-form-final'
    parent = artifacts/'u46a-followup-accepted.json'
    assert digest(parent) == PARENT and len(json.loads(parent.read_bytes())['matrix']['matching_full_record']) == 22
    for name, checksum in REFERENCES.values():
        assert digest(artifacts/name) == checksum
    target.mkdir(exist_ok=True, mode=0o755)
    code = target/'code'
    code.mkdir(exist_ok=True)
    marker = target/'parent.json'
    data = target/'data'
    pattern = json.loads((RAM/'packing-c/form-opts.json').read_bytes())
    assert pattern[pattern.index('-d')+1] == 'COMMUNITY_CERRO_BOM_PACKING_20261127U46C'
    assert '--no-http' in pattern and '--max-cron-threads=0' in pattern
    args = [word.replace('COMMUNITY_CERRO_BOM_PACKING_20261127U46C',TARGET).replace(str(RAM/'packing-c/data'),str(data))
            for word in pattern]
    addon_index, = [i for i,arg in enumerate(args) if arg.startswith('--addons-path=')]
    roots = args[addon_index].split('=',1)[1].split(',')
    assert Path(roots[0]).parent == RAM and Path(roots[0]).name.startswith('form194-')
    overlay = target/'addons'
    overlay.mkdir(exist_ok=True)
    args[addon_index] = '--addons-path='+','.join([str(overlay),*roots[1:]])
    remaining = list(TOOLS)
    copied = set()
    while remaining:
        name = remaining.pop()
        if name in copied:
            continue
        path = HERE/(name+'.py')
        shutil.copyfile(path,code/path.name)
        copied.add(name)
        for node in ast.walk(ast.parse(path.read_bytes())):
            if isinstance(node,ast.ImportFrom) and node.module and (HERE/(node.module+'.py')).is_file():
                remaining.append(node.module)
    plan = json.loads((source/'original-required.json').read_bytes())
    assert plan['database'] == SOURCE and len(plan['fields']) == 29
    (target/'original-required.json').write_text(json.dumps({**plan,'database':TARGET}))
    (target/'original-required.json').chmod(0o644)
    (target/'private-flags.json').write_text(json.dumps(args))

    def call(user, command, payload=None, log=None):
        proc = subprocess.run(['python3',str(HERE/'run_focal_print_command.py'),'--user',user,'--',*map(str,command)],
                              input=payload,capture_output=True)
        if log:
            log.write_bytes(proc.stdout+proc.stderr)
            log.chmod(0o600)
        if proc.returncode:
            if log:
                raise RuntimeError('Failed private command. See ' + str(log))
            proc.check_returncode()
        return proc.stdout.decode()

    def pg(program,*argv):
        return call('postgres',[program,'-h',RAM/'socket','-p','55443',*argv])

    def sql(db,statement):
        return pg('psql','-XAt','-v','ON_ERROR_STOP=1','-d',db,'-c',statement).strip()

    exists = sql('postgres',f"SELECT count(*) FROM pg_database WHERE datname='{TARGET}'") == '1'
    if not marker.is_file():
        assert not exists and sql(SOURCE,"SELECT count(*) FROM ir_module_module WHERE state='installed'") == '193'
        marker.write_text(PARENT)
    assert marker.read_text() == PARENT
    if not exists:
        filestore = source/'data/filestore'/SOURCE
        needed = int(sql('postgres',f"SELECT pg_database_size('{SOURCE}')")) + sum(p.stat().st_size for p in filestore.rglob('*') if p.is_file())
        assert shutil.disk_usage(RAM).free > needed + 200*1024**2
        pg('createdb','--template='+SOURCE,'--owner=dev_odoo18',TARGET)

    old = source/'data/filestore'/SOURCE
    expected = inventory(old)
    assert len(expected) == 677 and any(expected)
    dest = data/'filestore'/TARGET
    if not dest.exists():
        shutil.copytree(old,dest)
        for path in (data,data/'filestore',dest,*dest.rglob('*')):
            os.chown(path,61018,61018)
            path.chmod(0o700 if path.is_dir() else 0o600)
    assert inventory(dest) == expected
    with tempfile.TemporaryDirectory(dir=target) as tmp:
        archive = Path(tmp)/'receipt-form.tar'
        package = build(HERE.parents[1],archive,'receipt_form')
        with tarfile.open(archive) as bundle:
            for member in bundle:
                name = Path(member.name)
                assert member.isfile() and name.parent == Path(MODULE) and name.suffix == '.py'
                path = overlay/name
                path.parent.mkdir(exist_ok=True)
                payload = bundle.extractfile(member).read()
                if not path.exists():
                    path.write_bytes(payload)
                assert path.read_bytes() == payload

    loader = ['python3.10',code/'load_cerro_catalog_contracts.py','--cerro-local-qa',*args]
    audit = ['python3.10',code/'check_cerro_receipt_form_catalogue.py','--candidate',TARGET]
    state = sql(TARGET,f"SELECT state FROM ir_module_module WHERE name='{MODULE}'")
    if state != 'installed':
        assert sql(TARGET,"SELECT count(*) FROM ir_module_module WHERE state='installed'") == '193'
        call('odoo',loader+['-i',MODULE],log=target/'install.log')
    first = json.loads(call('postgres',audit,log=target/'first-catalogue.log'))
    call('odoo',loader+['-u',MODULE],log=target/'update.log')
    assert json.loads(call('postgres',audit,log=target/'updated-catalogue.log')) == first
    shell = ['python3.10','/work/sys-fg-code/odoo-bin','shell',*args]
    prelude = f'import json,sys\nsys.path.insert(0,{str(code)!r})\n'
    probe = prelude + """from probe_cerro_receipt_form import capture, operations, quality
from probe_cerro_packing_landscape import capture as landscape
from probe_cerro_studio_fullread import capture as full
from probe_cerro_studio_navigation import capture as routes
from probe_cerro_studio_client import capture as studio
def emit(tag, data):
    print(tag, json.dumps(data,sort_keys=True,ensure_ascii=True))
emit('projections',capture(env))
emit('operations',operations(env))
emit('quality',quality(env))
emit('VIEWS',dict(fullread=full(env),routes=routes(env),client=studio(env)))
emit('LANDSCAPE',landscape(env))
env.cr.rollback()
"""
    log = target/'functional.log'
    call('odoo',shell,probe.encode(),log)
    for key,(name,_) in REFERENCES.items():
        original = json.loads((artifacts/name).read_bytes())
        current = receipt(log,key)
        if key == 'projections':
            assert current['contexts'] == original['contexts'] and len(current['contexts']) == 64
        else:
            assert current == original,key
    matrix = compare(receipt(artifacts/'native-full.log','CERRO_FULL_READ'),
                     receipt(artifacts/'native-routes.log','CERRO_FULL'), receipt(log,'VIEWS'))
    assert all(len(matrix[key]) == 23 for key in ('matching_full_record','matching_studio_values','original_routes'))
    form = receipt(log,'LANDSCAPE')['5245']
    assert len(form['fields']) == 211 and not any(v.get('absent') for v in form['fields'].values())
    assert json.loads(call('postgres',audit,log=target/'after-flow-catalogue.log')) == first and inventory(dest) == expected
    summary = dict(archive=package,parent=PARENT,files=len(expected),schema=first, matrix=matrix,
                   form_fields=len(form['fields']),contexts=len(receipt(log,'projections')['contexts']),
                   quality_cases=len(receipt(log,'quality')), checked_actions=sum(form['buttons'].values()),
                   pending_actions=sorted(k for k,v in form['buttons'].items() if not v),
                   references={k:v[1] for k,v in REFERENCES.items()})
    contents = json.dumps(summary,sort_keys=True).encode()
    if result.exists():
        assert result.read_bytes() == contents
    else:
        result.write_bytes(contents)
    print(digest(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts',type=Path)
    parser.add_argument('result',type=Path)
    opts = parser.parse_args()
    os.umask(0o022)
    with open('/dev/shm/steps-shared-qa-restore.lock','a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        run(opts.artifacts,opts.result)
