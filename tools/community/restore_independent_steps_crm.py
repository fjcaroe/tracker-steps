"""Recover the checked Steps sales archive on an empty, private PostgreSQL server without the originating database."""
import argparse
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, object_catalog, restore_objects
from restore_converted_sys_cohort import full_snapshot, open_as_user, verify_same
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import GIB, LOCK, require
from seal_converted_runtime import extract_runtime
from verify_converted_backup import verify
from verify_converted_sql_schema import schema


MANIFEST = '5de21f357e0c270d33cdbb23268c343ba2643a2be5ca44992210831132b22f79'
RECEIPT = '3751d557e97953ff54ad2347c5967f103e0a38a458c6ad95fb22f1e6b2fc9769'
DATABASE = 'COMMUNITY_STEPS_CRM_RECOVERY_20261127U43D'
HIDDEN = ('/opt/odoo18', '/opt/steps-managed', '/opt/luis_odoo18', '/var/lib/postgresql',
          '/srv/odoo-data/steps-anchor-validation')


def read(folder, name):
    return json.loads((folder/name).read_bytes())


def start_recovery(work):
    require(work.resolve(strict=True) == work and work.parent == Path('/opt/steps-validation')
            and re.fullmatch(r'steps-independent-[A-Za-z0-9-]+',work.name), 'new-private-work-area-required')
    require((work/'code'/Path(__file__).name).resolve(strict=True) == Path(__file__).resolve(),
            'run-from-the-private-recovery-code')
    pgroot = Path('/var/lib/postgresql')
    require((not pgroot.is_dir() or shutil.disk_usage(pgroot).free >= 5*GIB)
            and shutil.disk_usage(work).free >= 7*GIB, 'private-recovery-space-required')
    require(not (work/'cluster').exists() and not (work/'restored').exists(), 'use-new-recovery-destination')
    socket = work/'socket'
    socket.mkdir(mode=0o755)
    postgres = pwd.getpwnam('postgres')
    os.chown(socket,postgres.pw_uid,postgres.pw_gid)
    socket.chmod(0o755)
    config = work/'recovery.conf'
    with config.open('x') as cfg:
        cfg.write('[options]\ndb_user = odoo\nlist_db = False\n')
    config.chmod(0o644)
    masks = [arg for name in HIDDEN for arg in ('--tmpfs',name)]
    args = ['bwrap','--die-with-parent','--unshare-net','--ro-bind','/','/','--tmpfs','/tmp',
            '--tmpfs','/opt/steps-validation','--dir',str(work),'--bind',str(work),str(work),
            '--bind',str(socket),'/run/postgresql','--ro-bind',str(config),'/etc/odoo18.conf',
            *masks,'--proc','/proc','--dev-bind','/dev','/dev','--','/usr/bin/python3','-B',
            str(Path(__file__).resolve()),str(work),'--isolated']
    subprocess.run(args,check=True)


def restore_database(work, database_connection):
    archive = work/'inbox'
    proof = read(archive,'restore-proof.json')
    verified = verify(archive,RECEIPT,MANIFEST)
    require(verified['providers']==157 and verified['supplemental_files']==0
            and proof['role_probe']['sale_quotation']['form_initialized'], 'qualified-steps-archive-required')
    require(database_connection == str(work/'cluster'), 'wrong-private-cluster')
    require(query('postgres',"SELECT string_agg(datname,',' ORDER BY datname) FROM pg_database") ==
            'postgres,template0,template1', 'private-server-must-start-empty')
    require(query('postgres',"SELECT count(*) FROM pg_roles WHERE rolname='odoo'") == '0',
            'expected-new-local-role')
    pg('createuser','--no-superuser','--no-createdb','--no-createrole','odoo')
    pg('createdb','--template=template0','--owner=odoo','--encoding=UTF8','--lc-collate=C',
       '--lc-ctype=C.UTF-8',DATABASE)
    out = work/'restored'
    out.mkdir()
    with (archive/'source.dump').open('rb') as source, (out/'restore.log').open('xb') as log:
        pg('pg_restore','--exit-on-error','--single-transaction','--no-tablespaces','--dbname='+DATABASE,
           stdin=source,stdout=log,stderr=log)
    require(query(DATABASE,"SELECT current_database()") == DATABASE, 'wrong-restored-database')
    frozen = json.loads(gzip.decompress((archive/'source-snapshot.json.gz').read_bytes()))
    verify_same(frozen, full_snapshot(DATABASE))
    ddl = pg('pg_dump','--schema-only','--no-tablespaces',DATABASE,readonly=True,stdout=subprocess.PIPE).stdout
    require(schema(ddl) == read(archive,'schema-proof.json')['archive_schema_sha256'], 'independent-schema-differs')
    data = out/'data'
    store = data/'filestore'/DATABASE
    store.mkdir(parents=True)
    attached = attachments(DATABASE,query)
    objects = object_catalog(attached['references'])
    restore_objects(archive/'filestore.tar',store,objects)
    physical = inventory(store,objects)
    tree = hashlib.sha256(json.dumps(physical,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    require(tree == read(archive,'filestore-physical.json')['tree_sha256'], 'independent-filestore-differs')
    sealed = out/'sealed'
    sealed.mkdir()
    core = sealed/'runtime'
    extract_runtime(archive/'runtime.tar.gz',core,read(archive,'runtime-members.json'))
    service = pwd.getpwnam('odoo')
    for folder in (out,sealed,core,*(p for p in core.rglob('*') if p.is_dir())):
        os.chown(folder,0,service.pw_gid)
        folder.chmod(0o750)
    for obj in (data,*data.rglob('*')):
        os.chown(obj,service.pw_uid,service.pw_gid)
    providers = read(archive,'effective-providers.json')
    hidden = [Path(entry[0]) for entry in providers.values()]
    first = open_as_user(out,DATABASE,service,1,hidden,private_server=True)
    verify_same(frozen,full_snapshot(DATABASE))
    second = open_as_user(out,DATABASE,service,2,hidden,private_server=True)
    verify_same(frozen,full_snapshot(DATABASE))
    require(first == second == proof['role_probe'], 'orphaned-restore-business-result-differs')
    return {'source_manifest':MANIFEST, 'initial_databases':['postgres','template0','template1'],
            'owner':'odoo','local_authentication':'peer','source_config_replaced':True,
            'postgres_major':12,'restored':DATABASE,'table_rows':verified['rows'],
            'checked_boots':2,'physical_files':len(physical),'providers':len(providers),
            'relational_definitions':{name:len(rows) for name,rows in frozen.items()},
            'schema_sha256':schema(ddl),'role_probe':first}


def isolated(work):
    socket = work/'socket'
    require(os.path.samefile(socket,'/run/postgresql') and
            {line.split(':')[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]} == {'lo'}
            and all(not any(Path(p).iterdir()) for p in HIDDEN), 'original-environment-must-be-unreachable')
    pg_bin = Path(subprocess.check_output(['pg_config','--bindir'],text=True).strip())
    require(pg_bin == Path('/usr/lib/postgresql/12/bin'), 'use-the-original-postgresql-major')
    cluster = work/'cluster'
    cluster.mkdir(mode=0o700)
    postgres = pwd.getpwnam('postgres')
    os.chown(cluster,postgres.pw_uid,postgres.pw_gid)
    def local(command, *args):
        subprocess.run(['runuser','-u','postgres','--',str(pg_bin/command),*args],check=True,
                       stdout=subprocess.DEVNULL)
    local('initdb','-D',str(cluster),'--auth-local=peer','--auth-host=reject','--encoding=UTF8',
          '--locale=C','--lc-ctype=C.UTF-8')
    options = "-c listen_addresses='' -c unix_socket_directories=/run/postgresql -c port=5432"
    local('pg_ctl','-D',str(cluster),'-o',options,'-l',str(cluster/'server.log'),'-w','start')
    try:
        result = restore_database(work,query('postgres','SHOW data_directory'))
    finally:
        local('pg_ctl','-D',str(cluster),'-w','-m','fast','stop')
    require(not (cluster/'postmaster.pid').exists(), 'private-server-still-running')
    result['private_server_stopped'] = True
    (work/'independent-proof.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work',type=Path)
    parser.add_argument('--isolated',action='store_true',help=argparse.SUPPRESS)
    args = parser.parse_args()
    os.umask(0o077)
    if args.isolated:
        isolated(args.work)
    else:
        with open(LOCK,'rb') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            start_recovery(args.work)
