"""Replay the Steps CRM selection on a fresh private pair from a sealed native SQL and filestore."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys

from custody_sys_previred_filestore import attachments, digest, object_catalog, restore_objects
from restore_native_product_backup import pg, query
from restore_sys_previred_pair import GIB, LOCK, require


def postgres_probe(action, native, community, plan=None):
    script = """
import json,sys,psycopg2
args=json.load(sys.stdin)
sys.path.insert(0,args['code'])
if args['action']=='prepare':
    from prepare_steps_crm_cohort import prepare
    with psycopg2.connect(dbname=args['community'],host='/var/run/postgresql') as conn, conn.cursor() as cr:
        report=prepare(cr)
else:
    from check_steps_crm_preservation import compare
    report=compare(args['native'],args['community'],args['plan'])
print(json.dumps(report))
"""
    payload = {'action': action, 'code': str(Path(__file__).resolve().parent), 'native': native,
               'community': community, 'plan': plan}
    # Send the JSON separately from Python source, including only the two known private database names.
    output = subprocess.check_output(['runuser','-u','postgres','--','env','PYTHONDONTWRITEBYTECODE=1',
                                      sys.executable,'-c',script], input=json.dumps(payload).encode())
    return json.loads(output)


def restore(args):
    base = Path('/opt/steps-validation')
    suffix = args.suffix
    require(re.fullmatch(r'[A-Z0-9_]{1,25}', suffix), 'private-suffix-required')
    native, community = [prefix + '_STEPS_CRM_' + suffix for prefix in ('MANAGEMENT_QA','COMMUNITY')]
    for path in (args.dump, args.control):
        require(path.resolve(strict=True) == path and path.is_file() and path.is_relative_to(base),
                'sealed-private-files-required')
    require(args.output.parent.resolve(strict=True) == args.output.parent and args.output.is_relative_to(base)
            and args.output.name == 'steps-crm-' + suffix.lower() and not args.output.is_symlink(),
            'use-a-private-work-directory')
    backup = json.loads(args.control.read_bytes())
    archive = args.control.with_name('filestore.tar')
    require(backup['source'] == 'karo_consultorias' and backup['verified_restore'] and
            re.fullmatch(r'MANAGEMENT_QA_STEPS_CUSTODY_[A-Z0-9_]+', backup['database']) and
            digest(args.dump) == backup['sql_sha256'] and archive.resolve(strict=True) == archive
            and digest(archive) == backup['archive_sha256'], 'wrong-native-steps-backup')
    names = f"('{native}','{community}')"
    identity = {'native': native, 'community': community, 'source_sql': backup['sql_sha256'],
                'filestore': backup['archive_sha256']}
    if args.output.exists():
        require(json.loads((args.output/'identity.json').read_bytes()) == identity, 'restore-identity-mismatch')
    else:
        require(query('postgres', f"SELECT count(*) FROM pg_database WHERE datname IN {names}") == '0',
                'two-new-databases-required')
    properties = json.loads(query('postgres', "SELECT json_build_array(pg_get_userbyid(datdba),"
        "pg_encoding_to_char(encoding),datcollate,datctype,pg_database_size(datname)) FROM pg_database "
        f"WHERE datname='{backup['database']}'"))
    owner, encoding, locale, ctype, size = properties
    service = pwd.getpwnam(owner)
    require(service.pw_uid != 0, 'expected-service-account')
    tablespace = 'steps_community_storage_20261028_community'
    volume = Path(query('postgres', f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{tablespace}'"))
    require(volume.resolve(strict=True).is_relative_to(base / 'community-payroll-storage-20261028'),
            'unexpected-private-tablespace')
    require(shutil.disk_usage(query('postgres','SHOW data_directory')).free >= 5*GIB and
            shutil.disk_usage(volume).free >= 2*GIB + 2*size + backup['payload_bytes'], 'insufficient-space')
    if not args.output.exists():
        args.output.mkdir(mode=0o750)
        (args.output/'identity.json').write_text(json.dumps(identity))
    os.chown(args.output, 0, service.pw_gid)
    args.output.chmod(0o750)
    for database in (native, community):
        if query('postgres', f"SELECT count(*) FROM pg_database WHERE datname='{database}'") == '0':
            pg('createdb','--template=template0','--owner='+owner,'--encoding='+encoding,'--lc-collate='+locale,
               '--lc-ctype='+ctype,'--tablespace='+tablespace,database)
        if query(database, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == '0':
            with args.dump.open('rb') as stream, (args.output / (database+'.log')).open('ab') as log:
                pg('pg_restore','--exit-on-error','--single-transaction','--no-tablespaces','--dbname='+database,
                   stdin=stream, stdout=log, stderr=log)
    stored = attachments(community, query)
    require(stored['rows_sha256'] == backup['rows_sha256'], 'original-attachments-drift')
    catalog = object_catalog(stored['references'])
    target = args.output / 'data/filestore' / community
    if not target.exists():
        from tempfile import TemporaryDirectory
        target.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=target.parent) as temp:
            objects = Path(temp) / 'objects'
            objects.mkdir()
            restore_objects(archive, objects, catalog)
            objects.rename(target)
    restored = {obj.relative_to(target).as_posix(): obj for obj in target.rglob('*') if obj.is_file()}
    require(restored.keys() == catalog.keys() and all(
        obj.stat().st_size == catalog[key] and digest(obj,'sha1') == obj.name for key,obj in restored.items()),
        'restored-attachment-content-differs')
    for obj in (args.output / 'data', *(args.output / 'data').rglob('*')):
        os.chown(obj, service.pw_uid, service.pw_gid)
    plan_path = args.output / 'plan.json'
    if plan_path.exists():
        plan = json.loads(plan_path.read_bytes())
    else:
        plan = postgres_probe('prepare', native, community)
        plan_path.write_text(json.dumps(plan))
    report = postgres_probe('compare', native, community, plan)
    report.update(attachment_objects=len(catalog), source_dump_sha256=backup['sql_sha256'],
                  attachment_archive_sha256=backup['archive_sha256'])
    (args.output / 'preservation.json').write_text(json.dumps(report, indent=2))
    require(report['preserved_tables_and_schema'] and report['preserved_counters'], 'fresh-steps-pair-drift')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('dump','control','output'):
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--suffix', required=True)
    opts = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore(opts)
