"""Restore the accepted Steps 166 database for a payroll-free expense UI rehearsal."""
import fcntl
import json
import os
from pathlib import Path
import pwd
import shutil
from tempfile import TemporaryDirectory

from audit_steps_sales_schema import objects
from complete_converted_filestore import inventory
from custody_sys_previred_filestore import attachments, digest, object_catalog
from recover_steps_fiscal_fields import TARGET as SOURCE, WORK as PRIOR
from restore_converted_sys_cohort import check_modules, full_snapshot, save, verify_same
from restore_native_product_backup import pg, query
from restore_steps_sales_backup import BASE, SPACE
from restore_sys_previred_pair import GIB, LOCK, require
from verify_steps_support_backup import compressed


TARGET = 'COMMUNITY_STEPS_EXPENSE_20261127U50E'
WORK = BASE/'steps-expense-20261127U50E'
CHECKPOINT = PRIOR/'all-166/final-checkpoint'
INDEX = '183a72362efaa1fc6f9d44e946b9f7219efb0760a2b80caabb6cad611cf4c021'
ANCHORS = ('hr_expense', 'hr_expense_sheet', 'ir_attachment')


def prepare():
    require(Path(__file__).resolve().parent == WORK/'code' and WORK.resolve(strict=True) == WORK,
            'wrong-private-expense-folder')
    require(digest(CHECKPOINT/'checkpoint.json') == INDEX, 'incorrect-financial-checkpoint')
    proof = json.loads((CHECKPOINT/'checkpoint.json').read_bytes())
    for name in ('source.dump', 'snapshot.json.gz', 'sql-objects.json.gz', 'providers.json', 'filestore.json.gz'):
        require(digest(CHECKPOINT/name) == proof['files'][name][1], 'different-financial-backup-'+name)
    marker = WORK/'identity.json'
    identity = {'database': TARGET, 'source': SOURCE, 'index': INDEX}
    exists = query('postgres', f"SELECT count(*) FROM pg_database WHERE datname='{TARGET}'") == '1'
    if not marker.exists():
        require(not exists, 'target-already-exists')
        save(marker, identity)
    require(json.loads(marker.read_bytes()) == identity, 'unexpected-expense-identity')
    expected = compressed(CHECKPOINT, 'filestore.json.gz')
    if not exists:
        volume = Path(query('postgres', f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{SPACE}'"))
        size = int(query('postgres', f"SELECT pg_database_size('{SOURCE}')"))
        needed = 5*GIB + size + sum(v[0] for v in expected.values())
        require(volume.resolve(strict=True).is_relative_to(BASE/'community-payroll-storage-20261028') and
                min(shutil.disk_usage(volume).free, shutil.disk_usage(WORK).free) > needed, 'insufficient-private-space')
        pg('createdb', '--template=template0', '--owner=odoo', '--tablespace='+SPACE, '--encoding=UTF8',
           '--lc-collate=C', '--lc-ctype=C.UTF-8', TARGET)
    require(query('postgres', f"SELECT pg_get_userbyid(datdba)||'/'||spcname FROM pg_database d JOIN pg_tablespace s "
                  f"ON d.dattablespace=s.oid WHERE datname='{TARGET}'") == 'odoo/'+SPACE, 'incorrect-owner-or-storage')
    if query(TARGET, "SELECT count(*) FROM pg_tables WHERE schemaname='public'") == '0':
        with (CHECKPOINT/'source.dump').open('rb') as source, (WORK/'restore.log').open('ab') as log:
            pg('pg_restore', '--exit-on-error', '--single-transaction', '--no-tablespaces', '-d', TARGET,
               stdin=source, stdout=log, stderr=log)
    frozen = compressed(CHECKPOINT, 'snapshot.json.gz')
    verify_same(frozen, full_snapshot(TARGET, ANCHORS))
    require(objects(TARGET) == compressed(CHECKPOINT, 'sql-objects.json.gz') and
            check_modules(TARGET, 'hr_expense') == json.loads((CHECKPOINT/'providers.json').read_bytes()), 'incomplete-expense-restore')
    catalog = object_catalog(attachments(TARGET, query)['references'])
    destination = WORK/'data/filestore'/TARGET
    if not destination.exists():
        origin = PRIOR/'data/filestore'/SOURCE
        require(inventory(origin, catalog) == expected, 'different-parent-filestore')
        require(shutil.disk_usage(WORK).free > 5*GIB + sum(v[0] for v in expected.values()), 'insufficient-filestore-space')
        destination.parent.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=destination.parent) as temp:
            copied = Path(temp)/'files'
            shutil.copytree(origin, copied)
            require(inventory(copied, catalog) == expected, 'expense-filestore-copy-differs')
            copied.rename(destination)
        service = pwd.getpwnam('odoo')
        for path in [WORK/'data', *(WORK/'data').rglob('*')]:
            os.chown(path, service.pw_uid, service.pw_gid)
    require(inventory(destination, catalog) == expected, 'different-expense-filestore')
    args = json.loads((PRIOR/'private-args.json').read_bytes())
    require(args[args.index('-d')+1] == SOURCE and '--net' in args and '--no-http' in args, 'unexpected-fiscal-runtime')
    args[args.index('-d')+1] = TARGET
    for idx, arg in enumerate(args):
        if arg == '--db-filter=^'+SOURCE+'$':
            args[idx] = '--db-filter=^'+TARGET+'$'
        elif arg.startswith(('--data-dir=', '--logfile=')):
            require(str(PRIOR/'data') in arg, 'unexpected-runtime-data-path')
            args[idx] = arg.replace(str(PRIOR/'data'), str(WORK/'data'))
    require('--db-filter=^'+TARGET+'$' in args and '--data-dir='+str(WORK/'data') in args, 'incorrect-expense-runtime')
    save(WORK/'private-args.json', args)
    verify_same(frozen, full_snapshot(TARGET, ANCHORS))
    print(json.dumps({'database': TARGET, 'parent': INDEX, 'rows': proof['rows'], 'objects': len(expected),
                      'active': len(check_modules(TARGET, 'hr_expense'))}))


if __name__ == '__main__':
    os.umask(0o077)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prepare()
