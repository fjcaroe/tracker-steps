"""Install the SyS payroll print extension only in the isolated .6.3 QA copy."""
import argparse
import fcntl
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory

from load_steps_sales_extension import guarded_command
from seal_local_sys_193 import MEM, PORT, SOCKET, capture, inventory, psql, save


DB = 'COMMUNITY_SYS_PREVIRED_COHORT_20261127U49E'
WORK = Path('/dev/shm/sys-negative-net-u49e')
STAGE = WORK/'role-print'
HERE = Path(__file__).resolve().parent
MODULE = 'step_sys_payslip_print'
PACKAGE = '21e2a31caf6e6a82497bbf003af485e524121838782c0a8873156aa14d11fa08'
FILES = ('__init__.py','__manifest__.py','payslip.py','report/payslip.xml')
METADATA = {'ir_model_data','ir_ui_view','ir_model','ir_model_fields','ir_module_module','ir_module_module_dependency','ir_cron_trigger'}


def build():
    data = io.BytesIO()
    with tarfile.open(fileobj=data,mode='w') as tar:
        for name in FILES:
            raw = (HERE.parents[1]/MODULE/name).read_bytes().replace(b'\r\n',b'\n')
            item = tarfile.TarInfo(MODULE+'/'+name)
            item.mode, item.size = 0o644, len(raw)
            tar.addfile(item,io.BytesIO(raw))
    return data.getvalue()


def odoo(roots, args, *, printing=False, **options):
    launch = [sys.executable, str(HERE/'run_focal_print_command.py'), '--user','odoo','--sys-payslip-form']
    if printing:
        launch.append('--loopback')
    command = ['python3.10','/work/sys-fg-code/odoo-bin',*args,'-c',str(WORK/'odoo.conf'),'-d',DB,
               '--db-filter=^'+DB+'$','--addons-path='+','.join(map(str, roots)),
               '--data-dir='+str(WORK/'data'),'--no-http','--workers=0','--max-cron-threads=0','--stop-after-init','--load=base,web']
    if not printing:
        command = guarded_command(command,STAGE,json.loads((STAGE/'required.json').read_bytes()))
    return subprocess.run([*launch,'--',*command],capture_output=True,**options)


def install(destination):
    assert WORK.is_dir() and psql("SHOW data_directory",'postgres') == str(MEM/'postgres/cluster')
    query = """SELECT name,latest_version,license FROM ir_module_module WHERE state='installed' ORDER BY name"""
    providers = psql(query,DB).splitlines()
    already = f'{MODULE}|18.0.1.0.0|LGPL-3' in providers
    assert len(providers) == 193+already and 'step_payroll_oca_sys_history|18.0.1.6.3|LGPL-3' in providers
    data = build()
    checksum = hashlib.sha256(data).hexdigest()
    if checksum != PACKAGE:
        raise ValueError('The print extension differs from the qualified archive')
    STAGE.mkdir(exist_ok=True)
    frozen = STAGE/'before'
    frozen.mkdir(exist_ok=True)
    basefile = frozen/'snapshot.json.gz'
    if not basefile.exists():
        assert not already
        capture(DB,SOCKET,PORT,frozen)
    snapshot = json.loads(gzip.decompress(basefile.read_bytes()))['snapshot']
    save(STAGE/'required.json',snapshot)
    overlay = STAGE/'addons'/checksum
    area = overlay/MODULE
    area.mkdir(parents=True,exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(data)) as pack:
        for item in pack:
            path = overlay/item.name
            path.parent.mkdir(exist_ok=True)
            raw = pack.extractfile(item).read()
            if not path.exists():
                path.write_bytes(raw)
            assert path.read_bytes() == raw
    assert set(p.relative_to(area).as_posix() for p in area.rglob('*') if p.is_file()) == set(FILES)
    code = STAGE/'code'
    code.mkdir(exist_ok=True)
    for name in ('load_steps_sales_extension.py','preflight_original_history_storage.py'):
        shutil.copyfile(HERE/name,code/name)
    roots = [overlay,WORK/'overlay',MEM/'overlay','/work/sys-fg-code/addons','/work/sys-fg-code/odoo/addons']
    tree = inventory(WORK/'data/filestore'/DB)
    assert len(tree) == 2708
    for step in ('install','update'):
        if already and step == 'install':
            continue
        proc = odoo(roots,['-i' if step == 'install' else '-u',MODULE])
        log = STAGE/(step+'.log')
        log.write_bytes(proc.stderr+proc.stdout)
        log.chmod(0o600)
        if proc.returncode:
            raise RuntimeError('The print extension did not load. See '+str(log))
    active = psql(query,DB).splitlines()
    assert sorted(active) == sorted(set(providers)|{f'{MODULE}|18.0.1.0.0|LGPL-3'})
    after = STAGE/'after'
    after.mkdir(exist_ok=True)
    with TemporaryDirectory(dir=after) as tmp:
        final = capture(DB,SOCKET,PORT,Path(tmp))['snapshot']
    changed = sorted(n for n,v in snapshot['public_tables'].items() if final['public_tables'][n] != v)
    assert set(changed) <= METADATA and all(final[k] == snapshot[k] for k in snapshot if k not in ('public_tables','sequence_values'))
    assert inventory(WORK/'data/filestore'/DB) == tree
    assert psql("SELECT count(*) FROM ir_model_data WHERE module='step_sys_payslip_print' AND name='sys_payroll_print' AND model='ir.ui.view'",DB)=='1'
    release = destination/(MODULE+'-'+checksum+'.tar')
    if not release.exists():
        with release.open('xb') as stream:
            stream.write(data)
    assert release.read_bytes() == data
    save(STAGE/'roots.json',list(map(str,roots)))
    out = dict(database=DB,package=checksum,providers=len(active),physical_files=len(tree),
               unchanged_tables=len(snapshot['public_tables'])-len(changed),metadata=changed)
    save(destination/'sys-role-print-install.json',out)
    print(json.dumps(out))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    opts = parser.parse_args()
    with open('/dev/shm/steps-shared-qa-restore.lock','a+b') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        install(opts.destination)
