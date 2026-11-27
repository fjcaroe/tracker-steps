"""Clone the admitted Community library and its verified attachment objects for the Cerro Studio trial."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess

SOURCE = 'COMMUNITY_LIBRARY_CERRO_20261126U41L'
TARGET = 'COMMUNITY_CERRO_BOM_STRICT_20261126U42C'
SPACE = 'steps_community_storage_20261028_cerro'
ROOT = Path('/opt/steps-validation/community-cerro-studio-strict-20261126U42C')
ESTIMATE_TARGET = 'COMMUNITY_CERRO_BOM_ESTIMATE_20261126U42E'
ESTIMATE_ROOT = Path('/opt/steps-validation/community-cerro-estimation-20261126U42E')
FILES = Path('/opt/steps-validation/community-historical-library-20261126U41L/cerro/data/filestore') / SOURCE
GIB = 1024 ** 3


def pg(*args):
    return subprocess.check_output(['runuser', '-u', 'postgres', '--', *args], text=True).strip()


def sql(db, s):
    return pg('psql', '-XAt', '-v', 'ON_ERROR_STOP=1', '-d', db, '-c', s)


def module_census(db):
    return json.loads(sql(db, """SELECT json_build_object('installed', count(*) FILTER (WHERE state='installed'),
        'non_free',count(*) FILTER (WHERE state='installed' AND (license IS NULL OR license NOT IN
          ('LGPL-3','AGPL-3','GPL-3','GPL-2','GPL-3 or any later version','GPL-2 or any later version'))),
        'enterprise',count(*) FILTER (WHERE state='installed' AND license='OEEL-1'),
        'pending',count(*) FILTER (WHERE state IN ('to install','to upgrade','to remove')),
        'fundos',count(*) FILTER (WHERE state='installed' AND name='step_agriculture_shared_farms'))
        FROM ir_module_module"""))


def references(db):
    rows = sql(db, """SELECT store_fname,checksum,file_size FROM ir_attachment
                      WHERE store_fname IS NOT NULL GROUP BY 1,2,3 ORDER BY 1,2,3""")
    result = {}
    for row in rows.splitlines():
        name, checksum, size = row.split('|')
        if not re.fullmatch('[0-9a-f]{40}', checksum) or name != checksum[:2] + '/' + checksum or name in result:
            raise ValueError('The source attachment catalogue has an inconsistent object identity')
        result[name] = (checksum, int(size))
    if len(result) < 676:
        raise ValueError('The source contains fewer physical objects than the original Cerro receipt')
    return result


def write_once(path, data):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(data, stream, sort_keys=True, indent=2)
        stream.write('\n')


def copy_filestore(originals, root, target, source_objects):
    data = root / 'data'
    output = data / 'filestore' / target
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    account = pwd.getpwnam('odoo')
    for name, (checksum, size) in source_objects.items():
        source = originals / name
        if source.is_symlink() or source.parent.is_symlink() or not source.is_file():
            raise ValueError('Missing physical attachment in the source')
        dest = output / name
        dest.parent.mkdir(mode=0o700, exist_ok=True)
        if dest.is_symlink() or dest.parent.is_symlink():
            raise ValueError('Unexpected symlink in the private copy')
        if not dest.exists():
            staging = dest.with_suffix('.partial')
            with source.open('rb') as src, staging.open('wb') as tmp:
                shutil.copyfileobj(src, tmp)
            if staging.stat().st_size != size or hashlib.sha1(staging.read_bytes()).hexdigest() != checksum:
                raise ValueError('Attachment verification failed during copy')
            staging.replace(dest)
        if dest.stat().st_size != size or hashlib.sha1(dest.read_bytes()).hexdigest() != checksum:
            raise ValueError('Physical clone differs from the source')
        os.chown(dest, account.pw_uid, account.pw_gid)
        dest.chmod(0o600)
    for folder in [data, data / 'filestore', output, *(p for p in output.iterdir() if p.is_dir())]:
        os.chown(folder, account.pw_uid, account.pw_gid)
        folder.chmod(0o700)


def clone_and_copy(target=TARGET, root=ROOT):
    if (target, root) not in ((TARGET, ROOT), (ESTIMATE_TARGET, ESTIMATE_ROOT)):
        raise ValueError('Unknown private Cerro trial')
    root.mkdir(mode=0o751, parents=True, exist_ok=True)
    working = root / 'clone-started.json'
    ready = root / 'clone-receipt.json'
    expected = {'source': SOURCE, 'target': target, 'tablespace': SPACE}
    if ready.exists():
        receipt = json.loads(ready.read_text())
        if any(receipt.get(key) != value for key, value in expected.items()):
            raise ValueError('Existing strict copy has a different source')
        return receipt
    state = module_census(SOURCE)
    if any(state[n] for n in ('non_free', 'enterprise', 'pending')) or state['fundos'] != 1:
        raise ValueError('The source is waiting for Fundos or still has unresolved module transitions')
    pg_dir = Path(sql('postgres', 'SHOW data_directory'))
    space = Path(sql('postgres', f"SELECT pg_tablespace_location(oid) FROM pg_tablespace WHERE spcname='{SPACE}'"))
    size = int(sql('postgres', f"SELECT pg_database_size('{SOURCE}')"))
    ram = int(next(l.split()[1] for l in Path('/proc/meminfo').read_text().splitlines()
                   if l.startswith('MemAvailable:'))) * 1024
    if (not space.resolve().is_relative_to('/opt/steps-validation') or shutil.disk_usage(pg_dir).free < 5 * GIB
            or shutil.disk_usage(space).free < max(8 * GIB, 3 * size) or ram < 1536 * 1024 ** 2):
        raise ValueError('The destination tablespace, data or memory reservation is insufficient')
    owner_space = sql('postgres', f"""SELECT pg_get_userbyid(d.datdba),s.spcname
        FROM pg_database d JOIN pg_tablespace s ON d.dattablespace=s.oid WHERE datname='{SOURCE}'""")
    if owner_space != 'dev_odoo18|' + SPACE:
        raise ValueError('The source owner or tablespace is different')
    if int(sql(SOURCE, """SELECT count(*) FROM pg_class WHERE relkind IN ('r','i','m','t','S')
              AND NOT relisshared AND reltablespace NOT IN (0,(SELECT dattablespace FROM pg_database WHERE datname=current_database()))
              AND relnamespace NOT IN ('pg_catalog'::regnamespace,'information_schema'::regnamespace)""")):
        raise ValueError('The source has objects in an additional tablespace')
    source_objects = references(SOURCE)
    exists = sql('postgres', f"SELECT count(*) FROM pg_database WHERE datname='{target}'") == '1'
    if exists and not working.exists():
        raise ValueError('A different trial already owns this database name')
    if not working.exists():
        write_once(working, expected)
    elif json.loads(working.read_text()) != expected:
        raise ValueError('The partial trial belongs to a different source')
    if not exists:
        pg('createdb', '--owner=dev_odoo18', '--tablespace=' + SPACE, '--template=' + SOURCE, target)
    if module_census(target) != state or references(target) != source_objects:
        raise ValueError('The SQL clone differs from the admitted source')
    copy_filestore(FILES, root, target, source_objects)
    receipt = dict(expected, state=state, object_count=len(source_objects),
                   object_bytes=sum(size for _, size in source_objects.values()),
                   attachment_rows=int(sql(target, 'SELECT count(*) FROM ir_attachment')),
                   file_references=int(sql(target, 'SELECT count(store_fname) FROM ir_attachment')))
    write_once(ready, receipt)
    return receipt


if __name__ == '__main__':
    with open('/run/lock/steps-environments.lock', 'rb') as g:
        fcntl.flock(g, fcntl.LOCK_EX)
        print(json.dumps(clone_and_copy(), sort_keys=True))
