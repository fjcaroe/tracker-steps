"""Prepare and publish the explicit T192 Cerro refresh with a recoverable QA archive."""
import argparse
import configparser
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import time
from urllib.request import urlopen

from customer_qa_clone_access import clone_database_access
from manage_management import errors, tree_hash
from provision_cerro_qa import (
    CONF, DB, DOMAIN, ROOT, SERVICE, SOURCE, USER, business_snapshot,
    neutralize_copy, query, run, verify, verify_neutralization, verify_packing,
)

SOURCE_CONF = Path('/etc/odoo18-cerroelplomo.conf')
OPERATIONS = Path(__file__).resolve().parent
COMMUNITY = OPERATIONS.parent / 'community'
QA_ONLY = {'step_accounting_multicurrency_core', 'step_treasury_community_reports'}
QA_NEWER = {'step_account_treasury', 'step_accounting_multicurrency'}


def configuration(path, database):
    config = configparser.ConfigParser(interpolation=None)
    assert config.read(path) and config['options']['db_name'] == database
    return config


def versions(database):
    assert query(database, "SELECT count(*) FROM ir_module_module WHERE state IN "
                 "('to install','to upgrade','to remove')") == '0'
    return json.loads(query(database, "SELECT json_object_agg(name,latest_version) "
                            "FROM ir_module_module WHERE state='installed'"))


def write_config(config, path):
    ident = pwd.getpwnam(USER)
    with path.open('w', encoding='utf-8') as stream:
        config.write(stream)
    os.chown(path, 0, ident.pw_gid)
    path.chmod(0o640)


def source_for(config, module):
    roots = (Path(part.strip()) for part in config['options']['addons_path'].split(','))
    return next(root / module for root in roots if (root / module / '__manifest__.py').is_file())


def freeze_addons(stage, prod, qa, production, existing):
    extras = existing.keys() - production.keys()
    upgrades = {name for name in production.keys() & existing.keys()
                if existing[name] != production[name]
                and tuple(map(int, existing[name].split('.'))) > tuple(map(int, production[name].split('.')))}
    assert extras <= QA_ONLY and upgrades <= QA_NEWER, 'Unreviewed QA-only module or version'
    target = stage / 'addons'
    target.mkdir()
    hashes = {}
    for module in sorted((production.keys() | existing.keys()) - {'studio_customization'}):
        source = source_for(qa if module in extras | upgrades else prod, module)
        shutil.copytree(source, target / module, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '.git'))
        hashes[module] = tree_hash(target / module)
        assert hashes[module] == tree_hash(source), module
    gid = pwd.getpwnam(USER).pw_gid
    for path in [target, *target.rglob('*')]:
        os.chown(path, 0, gid)
        path.chmod(0o750 if path.is_dir() or path.stat().st_mode & 0o111 else 0o640)
    return sorted(extras), sorted(upgrades), hashes


def verify_attachments(database, store):
    rows = query(database, "SELECT DISTINCT store_fname,checksum FROM ir_attachment WHERE store_fname IS NOT NULL")
    for line in rows.splitlines():
        name, checksum = line.split('|')
        assert re.fullmatch(r'[0-9a-f]{2}/[0-9a-f]{40}', name), 'Unexpected filestore path'
        file = store / name
        assert file.is_file() and hashlib.sha1(file.read_bytes()).hexdigest() == checksum, name
    return len(rows.splitlines())


def odoo(config, database, command=()):
    return ['sudo', '-u', USER, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin', *command,
            '-c', str(config), '-d', database, '--no-http', '--workers=0', '--max-cron-threads=0']


def dump(database, destination):
    with destination.open('xb') as stream:
        run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', database, stdout=stream)
    run('pg_restore', '--list', str(destination), stdout=subprocess.DEVNULL)


def sql_name(name):
    assert re.fullmatch(r'[A-Za-z0-9_-]{1,63}', name)
    return '"' + name + '"'


def rename_database(old, new):
    query('postgres', f'ALTER DATABASE {sql_name(old)} RENAME TO {sql_name(new)}')


def allow_connections(database, allow):
    query('postgres', f'ALTER DATABASE {sql_name(database)} ALLOW_CONNECTIONS {str(allow).lower()}')


def prepare(stage, candidate):
    assert shutil.disk_usage(ROOT).free > 12 * 2**30
    verify()
    prod = configuration(SOURCE_CONF, SOURCE)
    qa = configuration(CONF, DB)
    assert qa['options']['db_user'] == USER
    production, existing = versions(SOURCE), versions(DB)
    stage.parent.mkdir(mode=0o755, exist_ok=True)
    stage.parent.chmod(0o755)
    stage.mkdir(mode=0o750)
    stage.chmod(0o750)
    gid = pwd.getpwnam(USER).pw_gid
    os.chown(stage, 0, gid)
    install, upgrade, hashes = freeze_addons(stage, prod, qa, production, existing)
    print(f'T192_ADDONS_FROZEN modules={len(hashes)}', flush=True)
    data = stage / 'data'
    store = data / 'filestore' / candidate
    store.mkdir(parents=True)
    source_store = Path(prod['options']['data_dir']) / 'filestore' / SOURCE
    # Two passes keep immutable attachment files that existed before the dump
    # and add any that arrived before the dump snapshot was taken.
    run('rsync', '-a', str(source_store) + '/', str(store) + '/')
    snapshot_time = datetime.now(timezone.utc).isoformat()
    archive = stage / 'source.dump'
    dump(SOURCE, archive)
    archive.chmod(0o600)
    run('rsync', '-a', str(source_store) + '/', str(store) + '/')
    run('chown', '-R', USER + ':' + USER, str(data))
    for directory in (data, data / 'filestore', store):
        directory.chmod(0o700)
    config_file = stage / 'candidate.conf'
    qa['options'].update(db_name=candidate, dbfilter='^' + re.escape(candidate) + '$',
                         addons_path=str(stage / 'addons'), data_dir=str(data))
    write_config(qa, config_file)
    with clone_database_access(query, candidate, stage):
        run('sudo', '-u', 'postgres', 'createdb', '-O', USER, candidate)
        with archive.open('rb') as stream:
            run('sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-acl', '--no-comments',
                '--exit-on-error', '--role', USER, '-d', candidate, stdin=stream)
        assert versions(candidate) == production
        before = business_snapshot(candidate)
        neutralize_copy(candidate, config_file)
        assert business_snapshot(candidate) == before, 'Neutralization changed business history'
        print('T192_SNAPSHOT_NEUTRALIZED', flush=True)
        log = stage / 'upgrade.log'
        command = odoo(config_file, candidate)
        if install or upgrade:
            if install:
                command += ['-i', ','.join(install)]
            if upgrade:
                command += ['-u', ','.join(upgrade)]
            with log.open('w') as stream:
                run(*command, '--without-demo=all', '--stop-after-init', stdout=stream, stderr=stream)
            assert not errors(log.read_text(errors='replace')), str(log)
        query(candidate, "UPDATE ir_cron SET active=false WHERE active; "
                         "UPDATE ir_mail_server SET active=false WHERE active; "
                         "UPDATE fetchmail_server SET active=false WHERE active; "
                         "UPDATE mail_mail SET state='cancel' WHERE state IN ('outgoing','exception')")
        after = business_snapshot(candidate)
        assert all(after.get(table) == value for table, value in before.items()), [
            table for table, value in before.items() if after.get(table) != value]
        expected = production | {name: existing[name] for name in install + upgrade}
        assert versions(candidate) == expected
        verify_neutralization(candidate)
        assert query(candidate, "SELECT count(*) FROM res_company "
                     "WHERE l10n_cl_dte_service_provider IS DISTINCT FROM 'SIITEST'") == '0'
        verify_packing(candidate, config_file)
        probe = "MODE='qa-cerro'\n" + (COMMUNITY / 'verify_community_reports.py').read_text()
        result = run(*odoo(config_file, candidate, ['shell']), '--log-level=critical',
                     input=probe, text=True, capture_output=True)
        assert 'COMMUNITY_REPORTS_NATIVE_FLOW_OK' in result.stdout
        print(result.stdout.strip(), flush=True)
        attachments = verify_attachments(candidate, store)
        assert business_snapshot(candidate) == after
    proof = {'snapshot_time': snapshot_time, 'production_versions': production, 'qa_versions': existing,
             'versions': expected, 'sources': hashes, 'attachments': attachments,
             'source_config': hashlib.sha256(SOURCE_CONF.read_bytes()).hexdigest(),
             'qa_config': hashlib.sha256(CONF.read_bytes()).hexdigest()}
    (stage / 'validated.json').write_text(json.dumps(proof))
    print(f'T192_PREPARED {stage} modules={len(expected)} attachments={attachments}', flush=True)


def verify_https():
    for attempt in range(12):
        try:
            with urlopen('https://' + DOMAIN + '/web/login', timeout=10) as response:
                if response.status == 200 and b'password' in response.read():
                    return
        except OSError:
            pass
        if attempt < 11:
            time.sleep(2)
    raise RuntimeError('QA login failed')


def publish(stage, candidate, stamp):
    proof = json.loads((stage / 'validated.json').read_text())
    assert versions(SOURCE) == proof['production_versions'] and versions(DB) == proof['qa_versions']
    assert hashlib.sha256(SOURCE_CONF.read_bytes()).hexdigest() == proof['source_config']
    assert hashlib.sha256(CONF.read_bytes()).hexdigest() == proof['qa_config']
    assert versions(candidate) == proof['versions']
    assert all(tree_hash(stage / 'addons' / name) == digest for name, digest in proof['sources'].items())
    verify_neutralization(candidate)
    config = configuration(stage / 'candidate.conf', candidate)
    config['options'].update(db_name=DB, dbfilter='^' + DB + '$')
    filestore = stage / 'data' / 'filestore'
    assert verify_attachments(candidate, filestore / candidate) == proof['attachments']
    backup = Path('/opt/steps_backups') / ('t192_qa_cerro_' + stamp)
    backup.mkdir(mode=0o700)
    old_data = Path(configuration(CONF, DB)['options']['data_dir'])
    old = 'QA_CERRO_ARCHIVE_' + stamp
    shutil.copy2(CONF, backup / 'odoo.conf')
    old_frozen = new_live = False
    run('systemctl', 'stop', SERVICE)
    try:
        dump(DB, backup / 'database.dump')
        run('rsync', '-a', str(old_data / 'filestore' / DB) + '/', str(backup / 'filestore') + '/')
        count = verify_attachments(DB, backup / 'filestore')
        assert not query('postgres', f"SELECT 1 FROM pg_stat_activity WHERE datname='{DB}' LIMIT 1")
        allow_connections(DB, False)
        old_frozen = True
        rename_database(DB, old)
        (filestore / candidate).rename(filestore / DB)
        rename_database(candidate, DB)
        new_live = True
        write_config(config, CONF)
        run('systemctl', 'start', SERVICE)
        verify_https()
        verify()
        assert versions(DB) == proof['versions']
    except BaseException:
        run('systemctl', 'stop', SERVICE)
        if new_live:
            rename_database(DB, candidate)
        if old_frozen:
            if query('postgres', f"SELECT 1 FROM pg_database WHERE datname='{old}'"):
                rename_database(old, DB)
            allow_connections(DB, True)
        if (filestore / DB).exists():
            (filestore / DB).rename(filestore / candidate)
        shutil.copy2(backup / 'odoo.conf', CONF)
        os.chown(CONF, 0, pwd.getpwnam(USER).pw_gid)
        run('systemctl', 'start', SERVICE)
        raise
    proof.update(backup=str(backup), archive_database=old, archived_attachments=count)
    (stage / 'published.json').write_text(json.dumps(proof))
    print(f'T192_PUBLISHED snapshot={proof["snapshot_time"]} archive={old} backup={backup} '
          f'modules={len(proof["versions"])} attachments={proof["attachments"]}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'publish'))
    parser.add_argument('stamp')
    args = parser.parse_args()
    assert os.geteuid() == 0 and re.fullmatch(r'[0-9]{14}', args.stamp)
    os.umask(0o077)
    candidate = 'MANAGEMENT_QA_QA-CERRO_t192_' + args.stamp
    stage = ROOT / 'refresh' / args.stamp
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == 'prepare':
            prepare(stage, candidate)
        else:
            publish(stage, candidate, args.stamp)


if __name__ == '__main__':
    main()
