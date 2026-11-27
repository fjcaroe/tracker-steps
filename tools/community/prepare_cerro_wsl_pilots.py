"""Prepare only the isolated Cerro PG12 cluster inside the existing, verified local Focal userspace."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT=Path('/var/tmp/steps-community-qa-focal')
WORK=ROOT/'work/cerro-pg'
INSIDE=Path('/work/cerro-pg')
UID=61012
DBS=('COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M','COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44K',
     'COMMUNITY_CERRO_BOM_PRODUCT_20261126U42P')


def mkdir(name,mode,uid):
    p=WORK/name
    p.mkdir(parents=True,exist_ok=True)
    assert p.resolve().is_relative_to(WORK.resolve()) and not p.is_symlink()
    os.chown(p,uid,uid)
    p.chmod(mode)
    return p


def prepare(executor,artifacts):
    assert os.getuid()==0 and (ROOT/'pg-source-members.json').is_file()
    assert executor.name=='run_focal_print_command.py'
    WORK.mkdir(mode=0o751,parents=True,exist_ok=True)
    assert not WORK.is_symlink()
    incoming=mkdir('artifacts',0o750,UID)
    code=mkdir('code',0o755,0)
    for name in ('audit_cerro_original_schema.py','backup_cerro_catalog_pilots.py','rehearse_cerro_private_backup.py',
                 'cerro_backup_constraints.py','cerro_accounting_checks.py'):
        shutil.copyfile(Path(__file__).with_name(name),code/name)
        (code/name).chmod(0o644)
    for db in DBS:
        for part in ('dump','inventory','filestore'):
            file=artifacts/(db+'-'+part)
            claim=json.loads(file.with_suffix('.json').read_bytes())
            assert claim['database']==db and claim['artifact']==part
            assert file.stat().st_size==claim['bytes'] and hashlib.sha256(file.read_bytes()).hexdigest()==claim['sha256']
            dest=incoming/file.name
            if not dest.exists():
                # These three sealed object tar streams are literally identical
                # and immutable, while each restored Odoo filestore is private.
                identical=incoming/('physical-'+claim['sha256']+'.tar')
                if part=='filestore':
                    if not identical.exists():
                        shutil.copyfile(file,identical)
                        identical.chmod(0o440)
                        os.chown(identical,0,UID)
                    os.link(identical,dest)
                else:
                    shutil.copyfile(file,dest)
            assert hashlib.sha256(dest.read_bytes()).hexdigest()==claim['sha256']
            dest.chmod(0o440)
            os.chown(dest,0,UID)
            manifest=dest.with_suffix('.json')
            manifest.write_text(json.dumps(claim,sort_keys=True))
            manifest.chmod(0o440)
            os.chown(manifest,0,UID)
    for proof in artifacts.glob('*-constraints.gz'):
        target=incoming/proof.name
        shutil.copyfile(proof,target)
        os.chown(target,0,UID)
        target.chmod(0o440)
    cluster=mkdir('cluster',0o700,UID)
    mkdir('socket',0o711,UID)
    mkdir('logs',0o700,UID)
    def pg(*args,check=True):
        runner=['python3',str(executor),'--user','postgres','--',*map(str,args)]
        return subprocess.run(runner,check=check,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    if not (cluster/'PG_VERSION').exists():
        res=pg('initdb','-D',INSIDE/'cluster','--encoding=UTF8','--lc-collate=C.UTF-8',
               '--lc-ctype=C.UTF-8','--auth-local=peer','--auth-host=reject')
        assert 'Success.' in res.stdout
    assert (cluster/'PG_VERSION').read_text().strip()=='12'
    hba=cluster/'pg_hba.conf'
    ident=cluster/'pg_ident.conf'
    if not (cluster/'cerro-local.conf').exists():
        (cluster/'cerro-local.conf').write_text("listen_addresses = ''\nport = 55442\nunix_socket_directories = '/work/cerro-pg/socket'\ntimezone = 'UTC'\n")
        with (cluster/'postgresql.conf').open('a') as fp:
            fp.write("\ninclude = 'cerro-local.conf'\n")
        hba.write_text("local all all peer map=cerro_local\nhost all all 127.0.0.1/32 reject\nhost all all ::1/128 reject\n")
        ident.write_text("cerro_local postgres postgres\ncerro_local odoo dev_odoo18\n")
    if pg('pg_ctl','status','-D',INSIDE/'cluster',check=False).returncode:
        pg('pg_ctl','start','-D',INSIDE/'cluster','-l',INSIDE/'logs/postgres.log','-w')
    psql=['psql','-XAt','-v','ON_ERROR_STOP=1','-h',INSIDE/'socket','-p','55442','-d','postgres','-c']
    response=pg(*psql,"SELECT current_user,current_setting('server_version_num'),current_setting('listen_addresses')").stdout.strip()
    assert response=='postgres|120022|'
    if not pg(*psql,"SELECT 1 FROM pg_roles WHERE rolname='dev_odoo18'").stdout.strip():
        pg(*psql,'CREATE ROLE dev_odoo18 LOGIN NOSUPERUSER')
    for db in DBS:
        dest=mkdir('restore-'+db,0o700,UID)
        claim={'database':db,'archive_sha256':json.loads((incoming/(db+'-dump.json')).read_bytes())['sha256']}
        marker=dest/'restore-start.json'
        owner=pg(*psql,"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='"+db+"'").stdout.strip()
        if not marker.exists():
            assert not owner
            marker.write_text(json.dumps(claim,sort_keys=True))
        assert json.loads(marker.read_bytes())==claim
        if not owner:
            pg('createdb','-h',INSIDE/'socket','-p','55442','--template=template0','--owner=dev_odoo18',
               '--encoding=UTF8','--lc-collate=C.UTF-8','--lc-ctype=C.UTF-8',db)
        else:
            assert owner=='dev_odoo18'
        loaded=pg('psql','-XAt','-h',INSIDE/'socket','-p','55442','-d',db,'-c',"SELECT to_regclass('public.ir_model')").stdout.strip()
        if not loaded:
            restored=pg('pg_restore','-h',INSIDE/'socket','-p','55442','--exit-on-error','--single-transaction',
                        '--no-tablespaces','-d',db,INSIDE/'artifacts'/(db+'-dump'),check=False)
            (dest/'pg-restore.log').write_text(restored.stdout)
            if restored.returncode:
                raise ValueError('PG12 restore failed for '+db+': '+restored.stdout[-500:])
        total=pg('psql','-XAt','-h',INSIDE/'socket','-p','55442','-d',db,'-c',
                 "SELECT count(*) FROM ir_module_module WHERE state='installed'").stdout.strip()
        print(db,total,flush=True)


if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--executor',type=Path,required=True)
    cli.add_argument('--artifacts',type=Path,required=True)
    args=cli.parse_args()
    prepare(args.executor,args.artifacts)
