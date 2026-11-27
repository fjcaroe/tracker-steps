"""Create an independent, RAM-backed PG12 trial from the qualified local 189-module Cerro database."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


RAM = Path('/dev/shm/steps-cerro-u46')
SOCKET = str(RAM/'socket')
SOURCE = 'COMMUNITY_CERRO_BOM_CONCEPTS_20261127U45P'
TRIAL = 'COMMUNITY_CERRO_BOM_PACKING_20261127U46B'
FINAL = 'COMMUNITY_CERRO_BOM_PACKING_20261127U46C'
PG_UID = 61012


def prepare(executor,trial=TRIAL):
    assert trial in (TRIAL,FINAL,'COMMUNITY_CERRO_BOM_PACKING_20261127U46D')
    if os.getuid() or not os.path.ismount('/dev/shm'):
        raise RuntimeError('Private temporary PostgreSQL requires the local memory filesystem')
    RAM.mkdir(mode=0o751,exist_ok=True)
    assert RAM.resolve()==RAM and RAM.stat().st_uid==0
    for name,mode in [('cluster',0o700),('socket',0o711),('pg',0o700)]:
        path=RAM/name
        path.mkdir(mode=mode,exist_ok=True)
        os.chown(path,PG_UID,PG_UID)
    def command(*args,check=True):
        return subprocess.run(['python3',str(executor),'--user','postgres','--',*map(str,args)],capture_output=True,check=check)
    dbopts=['-h',SOCKET,'-p','55443']
    def sql(query,db='postgres'):
        return command('psql',*dbopts,'-XAt','-v','ON_ERROR_STOP=1','-d',db,'-c',query).stdout.decode().strip()
    cluster=RAM/'cluster'
    if not (cluster/'PG_VERSION').exists():
        assert shutil.disk_usage(RAM).free>1024**3
        command('initdb','-D',cluster,'--encoding=UTF8','--lc-collate=C.UTF-8','--lc-ctype=C.UTF-8','--auth-local=peer','--auth-host=reject')
        with (cluster/'postgresql.conf').open('a') as cfg:
            cfg.write("\nlisten_addresses = ''\nport = 55443\nunix_socket_directories = '"+SOCKET+"'\ntimezone = 'UTC'\n")
        (cluster/'pg_hba.conf').write_text('local all all peer map=cerro_local\n')
        (cluster/'pg_ident.conf').write_text('cerro_local postgres postgres\ncerro_local odoo dev_odoo18\n')
    assert (cluster/'PG_VERSION').read_text().strip()=='12'
    if command('pg_ctl','status','-D',cluster,check=False).returncode:
        command('pg_ctl','start','-D',cluster,'-l',RAM/'pg/postgres.log','-w')
    assert sql("SELECT current_user,current_setting('server_version_num'),current_setting('listen_addresses')")=='postgres|120022|'
    if not sql("SELECT 1 FROM pg_roles WHERE rolname='dev_odoo18'"):
        sql('CREATE ROLE dev_odoo18 LOGIN NOSUPERUSER')
    dump=RAM/'pg/cerro-packing-seed.dump'
    seal=RAM/'source-dump.json'
    if not seal.exists():
        assert shutil.disk_usage(RAM).free>850*1024**2
        command('pg_dump','-h','/work/cerro-pg/socket','-p','55442','--format=custom','-f',dump,SOURCE)
        seal.write_text(json.dumps(dict(source=SOURCE,target=trial,sha256=hashlib.sha256(dump.read_bytes()).hexdigest()),sort_keys=True))
    claim=json.loads(seal.read_bytes())
    assert claim['source']==SOURCE and claim['target'] in ('COMMUNITY_CERRO_BOM_PACKING_20261127U46A',TRIAL,FINAL,'COMMUNITY_CERRO_BOM_PACKING_20261127U46D')
    assert claim['sha256']==hashlib.sha256(dump.read_bytes()).hexdigest()
    if not sql("SELECT 1 FROM pg_database WHERE datname='" +trial+"'"):
        command('createdb',*dbopts,'--owner=dev_odoo18','--template=template0',trial)
    if not sql("SELECT to_regclass('public.ir_model')",trial):
        result=command('pg_restore',*dbopts,'--single-transaction','--exit-on-error','--no-tablespaces','-d',trial,dump,check=False)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace')[-1200:])
    return claim
