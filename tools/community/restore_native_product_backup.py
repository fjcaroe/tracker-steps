"""Restore a Steps or Cerro native SQL database and all referenced attachment bytes offline."""
import argparse
import configparser
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess

from custody_sys_previred_filestore import attachments, capture, digest, object_catalog, restore_objects
from restore_sys_previred_pair import GIB, LOCK, SOCKET, require, save


PRODUCTS = {'steps': ('karo_consultorias', 2), 'cerro': ('CERRO_EL_PLOMO', 7)}


def pg(tool, *args, readonly=False, **kwargs):
    cmd = ['sudo', '-n', '-u', 'postgres']
    if readonly:
        cmd.extend(['env', 'PGOPTIONS=-c default_transaction_read_only=on'])
    return subprocess.run([*cmd, tool, '--host=' + SOCKET, '--no-password', *args], check=True, **kwargs)


def query(database, sql):
    return pg('psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', database, '-c', sql,
              readonly=True, text=True, stdout=subprocess.PIPE).stdout.strip()


def native_orm_probe(database, uid, config, options, service, folder):
    runtime = Path('/opt/odoo18/odoo-bin')
    # Odoo accepts an addons path only when it actually contains an addon.
    # Use the same base provider as this runtime, without copying any sources.
    core = (runtime.parent / 'odoo/addons/base').resolve(strict=True)
    require((core / '__manifest__.py').is_file(), 'native-base-provider-missing')
    (folder / 'overlay/base').symlink_to(core, target_is_directory=True)
    args = [
        'unshare', '--net', '--', 'sh', '-ec', 'ip link set dev lo up; exec "$@"', 'steps',
        'sudo', '-n', '-u', service.pw_name, 'env', 'PYTHONDONTWRITEBYTECODE=1',
        '/usr/bin/python3.10', str(runtime), 'shell', '-c', config,
        '-d', database, '--db-filter=^' + database + '$', '--db_host=/var/run/postgresql',
        '--data-dir=' + str(folder / 'data'), '--load=base,web', '--no-http',
        '--workers=0', '--max-cron-threads=0', '--stop-after-init',
        '--addons-path=' + str(folder / 'overlay') + ',' + options['addons_path'],
        '--logfile=' + str(folder / 'data/odoo-custody.log'),
    ]
    probe = """
import hashlib, json
from collections import Counter
assert env.cr.dbname == database
user = env['res.users'].browse(uid)
assert user.exists() and user.active and not user.share
scope = env['ir.attachment'].with_user(user).with_context(
    allowed_company_ids=user.company_ids.ids, bin_size=False)
assert not scope.env.su
rows = scope.search([('store_fname','!=',False), ('file_size','>',0), ('file_size','<',2000000),
                     ('res_model','!=',False)], order='file_size desc, id', limit=12)
assert rows
models = Counter()
for row in rows:
    binary = row.raw
    assert len(binary) == row.file_size and hashlib.sha1(binary).hexdigest() == row.checksum
    models[row.res_model] += 1
env.cr.rollback()
print('NATIVE_ATTACHMENT_RESTORE=' + json.dumps({'uid':uid,'read':len(rows),'models':dict(models)}))
"""
    source = f'database={database!r}\nuid={uid!r}\n' + probe
    with (folder / 'shell.log').open('xb') as output:
        subprocess.run(args, input=source.encode(), stdout=output, stderr=subprocess.STDOUT, check=True)
    lines = (folder / 'shell.log').read_text(errors='replace').splitlines()
    receipts = [json.loads(line.split('=', 1)[1]) for line in lines if line.startswith('NATIVE_ATTACHMENT_RESTORE=')]
    require(len(receipts) == 1 and receipts[0]['uid'] == uid and receipts[0]['read'] > 0,
            'native-attachment-role-proof-missing')
    return receipts[0]


def restore(args):
    source, uid = PRODUCTS[args.product]
    registry = json.loads(args.registry.read_text(encoding='utf-8-sig'))['environments'][args.product]
    require(registry['database'] == source and registry['role'] == 'production', 'product-registry-drift')
    config = configparser.ConfigParser(interpolation=None, strict=False)
    require(config.read(registry['config']), 'native-config-missing')
    options = config['options']
    filestore = (Path(options['data_dir']) / 'filestore' / source).resolve(strict=True)
    require(filestore.name == source and filestore.parent.name == 'filestore', 'filestore-product-drift')
    owner, encoding, collate, ctype, db_size = json.loads(query('postgres',
        "SELECT json_build_array(pg_get_userbyid(datdba),pg_encoding_to_char(encoding),datcollate,datctype,"
        f"pg_database_size(datname)) FROM pg_database WHERE datname='{source}'"))
    require(options['db_user'] == owner, 'native-database-owner-drift')
    service = pwd.getpwnam(owner)
    require(service.pw_uid > 0, 'native-service-must-be-unprivileged')
    folder = args.parent / (args.product + '-' + args.suffix)
    require(args.parent.is_absolute() and args.parent.is_dir() and args.parent.resolve() == args.parent
            and args.parent.is_relative_to('/opt/steps-validation') and not folder.exists(),
            'new-private-restore-directory-required')
    database = 'MANAGEMENT_QA_' + args.product.upper() + '_CUSTODY_' + args.suffix
    require(query('postgres', f"SELECT count(*) FROM pg_database WHERE datname='{database}'") == '0',
            'new-private-database-required')
    sql_volume = Path(query('postgres', 'SHOW data_directory'))
    require(shutil.disk_usage(sql_volume).free >= 5 * GIB + db_size, 'database-reserve-required')
    require(shutil.disk_usage(args.parent).free >= 2 * GIB + db_size, 'backup-reserve-required')
    folder.mkdir(mode=0o700)
    os.chown(folder, 0, service.pw_gid)
    folder.chmod(0o750)
    if args.dump:
        require(args.dump.is_file() and args.dump.resolve() == args.dump
                and re.fullmatch('[a-f0-9]{64}', args.dump_sha256 or '')
                and digest(args.dump) == args.dump_sha256, 'existing-dump-mismatch')
        dump = args.dump
    else:
        dump = folder / 'source.dump'
        with dump.open('xb') as output:
            pg('pg_dump', '-Fc', '--dbname=' + source, readonly=True, stdout=output)
    dump_hash = digest(dump)
    save(folder, 'backup.json', {'source': source, 'sha256': dump_hash, 'bytes': dump.stat().st_size})
    pg('createdb', '--template=template0', '--owner=' + owner, '--encoding=' + encoding,
       '--lc-collate=' + collate, '--lc-ctype=' + ctype, database)
    with dump.open('rb') as incoming, (folder / 'restore.log').open('xb') as log:
        pg('pg_restore', '--exit-on-error', '--no-tablespaces', '--dbname=' + database,
           stdin=incoming, stdout=log, stderr=log)
    before = attachments(database, query)
    catalog = object_catalog(before['references'])
    require(catalog and before['database'] == database, 'no-restored-attachment-objects')
    sealed = capture(filestore, folder, catalog)
    target = folder / 'data/filestore' / database
    target.mkdir(parents=True)
    restore_objects(folder / 'filestore.tar', target, catalog)
    overlay = folder / 'overlay'
    overlay.mkdir(mode=0o700)
    for path in (overlay, folder / 'data', *(folder / 'data').rglob('*')):
        require(not path.is_symlink(), 'private-restore-symlink')
        os.chown(path, service.pw_uid, service.pw_gid)
    installed, enterprise = json.loads(query(database, """
        SELECT json_build_array(count(*),count(*) FILTER (WHERE license='OEEL-1')) FROM ir_module_module
        WHERE state='installed'"""))
    role = native_orm_probe(database, uid, registry['config'], options, service, folder)
    after = attachments(database, query)
    require(object_catalog(after.pop('references')) == catalog, 'native-attachment-objects-changed')
    del before['references']
    require(after == before, 'native-attachment-rows-changed')
    receipt = {**before, **sealed, 'source': source, 'sql_sha256': dump_hash,
               'native_role': role, 'installed': installed, 'enterprise': enterprise,
               'verified_restore': True, 'restored_attachment_rows_preserved': True}
    save(folder, 'restore-proof.json', receipt)
    print(json.dumps(receipt, sort_keys=True), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--product', choices=PRODUCTS, required=True)
    parser.add_argument('--suffix', required=True)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--dump', type=Path)
    parser.add_argument('--dump-sha256')
    args = parser.parse_args()
    require(re.fullmatch('[A-Z0-9_]{1,30}', args.suffix) and bool(args.dump) == bool(args.dump_sha256),
            'invalid-product-restore-arguments')
    os.umask(0o077)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        restore(args)


if __name__ == '__main__':
    main()
