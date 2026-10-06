"""Validate/promote an immutable freight-only release in Desarrollo.

Snapshots hash every original business column. Only the explicitly consolidated
route aliases are normalized, with ambiguity refused by the versioned migration.
"""
import argparse
import ast
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
import socket
import subprocess
import tarfile
import time
import urllib.request

from manage_management import digest, errors, query, run, tree_hash

HERE = Path(__file__).resolve().parent
MODULE = 'step_operations_ui'


def extract(release, target):
    with tarfile.open(release) as archive:
        proof = json.loads(archive.extractfile('release.json').read())
        assert re.fullmatch('[0-9a-f]{40}', proof['commit'])
        assert set(proof['versions']) == {MODULE}
        found = set()
        for member in archive.getmembers():
            path = Path(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            assert member.name == 'release.json' or path.parts[0] == MODULE
            assert member.name not in found
            found.add(member.name)
            if member.name != 'release.json':
                assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == proof['files'][member.name]
        assert found == set(proof['files']) | {'release.json'}
        archive.extractall(target)
    return proof


def snapshot(database, schema=None):
    if schema is None:
        tables = json.loads(query(database, """SELECT json_agg(tablename ORDER BY tablename) FROM pg_tables
            WHERE schemaname='public' AND (tablename LIKE 'x_%flete%' OR tablename='x_modalidad_de_frio'
            OR tablename IN ('account_move','account_move_line','mail_message','mail_followers','mail_activity','ir_attachment'))"""))
        schema = {table: json.loads(query(database, "SELECT json_agg(column_name ORDER BY ordinal_position) "
                  "FROM information_schema.columns WHERE table_schema='public' AND table_name='%s'" % table))
                  for table in tables}
    result = {}
    for table, columns in schema.items():
        assert re.fullmatch('[a-z0-9_]+', table) and all(re.fullmatch('[a-z0-9_]+', column) for column in columns)
        expression = 'to_jsonb(t)'
        if table == 'x_tramo_de_flete':
            parts = []
            for canonical, legacy in (('origin', 'x_studio_lugar_desde'), ('destination', 'x_studio_lugar_hasta'),
                                      ('company_id', 'x_studio_empresa')):
                if canonical in columns and legacy in columns:
                    empty = "NULLIF(t.%s,'')" if canonical != 'company_id' else 't.%s'
                    value = 'COALESCE(%s,%s)' % (empty % canonical, empty % legacy)
                    parts += ["'%s',%s" % (canonical, value), "'%s',%s" % (legacy, value)]
            if parts:
                expression += ' || jsonb_build_object(' + ','.join(parts) + ')'
        expression = "(SELECT jsonb_object_agg(key,value) FROM jsonb_each(%s) WHERE key=ANY(ARRAY[%s]))" % (
            expression, ','.join("'%s'" % column for column in columns))
        column = 'model' if table == 'mail_message' else 'res_model'
        condition = (" WHERE %s IN ('x_tramo_de_flete','x_modalidad_de_frio','x_tarifa_de_fletes',"
                     "'x_orden_de_flete','x_planificacion_de_flete','x_contabilizacion_de_f')" % column
                     if table in ('mail_message','mail_followers','mail_activity','ir_attachment') else '')
        result[table] = query(database, "SELECT json_build_object('count',count(*),'digest',md5(COALESCE("
                              "string_agg((%s)::text,'|' ORDER BY t.id),''))) FROM %s t%s" % (expression, table, condition))
    return {'schema': schema, 'rows': result}


def verify(base, options, database, source, opts, proof, stage):
    header = 'ROOT=' + repr(str(source)) + '\nEXPECTED=' + repr(proof['versions'][MODULE]) + '\n'
    result = subprocess.run(base + ['shell'] + options + ['-d', database, '--db-filter=^' + database + '$',
        '--addons-path=' + str(source) + ',' + opts['addons_path'], '--log-level=error'],
        input=header + (HERE / 'verify_freight.py').read_text(), text=True, capture_output=True)
    (stage / ('verify-' + database + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'FREIGHT_REGISTRY_OK' in result.stdout, result.stderr[-3000:]
    print('\n'.join(line for line in result.stdout.splitlines() if line.startswith('FREIGHT_REGISTRY_OK')), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('qa', 'certify', 'deploy', 'verify'))
    parser.add_argument('release', type=Path)
    parser.add_argument('run_id')
    args = parser.parse_args()
    assert os.geteuid() == 0 and re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
    registry = json.loads((HERE / 'environments.json').read_text())
    assert registry['policy']['qa'] == 'development'
    target = registry['environments']['development']
    database, service = target['database'], target['service']
    conf = Path(target['config'])
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(conf)
    opts = cfg['options']
    assert opts['db_name'] == database
    assert not query(database, "SELECT name FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove')"), \
        'Pending upgrades in source database; reconcile before testing/promoting'
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', service], text=True).strip()
    identity = pwd.getpwnam(user)
    stage = Path('/opt/steps-validation') / ('freight_development_' + args.run_id)
    stage.mkdir(parents=True, exist_ok=True, mode=0o750)
    staged = stage / 'addons'
    staged.mkdir(exist_ok=True)
    proof = extract(args.release, staged)
    for path in [stage, staged, *staged.rglob('*')]:
        os.chown(path, identity.pw_uid, identity.pw_gid)
    installed = query(database, "SELECT latest_version FROM ir_module_module WHERE name='step_operations_ui' AND state='installed'")
    assert installed and tuple(map(int, proof['versions'][MODULE].split('.'))) >= tuple(map(int, installed.split('.')))
    dependencies = ast.literal_eval((staged / MODULE / '__manifest__.py').read_text())['depends']
    baseline = {'config_sha256': digest(conf), 'installed_version': installed, 'sources': {}}
    shared_modules = json.loads(query(database, "SELECT json_object_agg(name,latest_version) FROM ir_module_module "
                   "WHERE state='installed' AND (name LIKE 'step%' OR name IN ('web_studio','studio_customization'))"))
    baseline['shared_versions'] = shared_modules
    for name in sorted({MODULE, *dependencies, *shared_modules}):
        # Missing legacy steps_api is audited separately; the service already
        # reports that exact exception and no promotion may add another.
        candidates = [Path(path.strip()) / name for path in opts['addons_path'].split(',')
                      if (Path(path.strip()) / name / '__manifest__.py').exists()]
        if name == 'steps_api' and not candidates:
            baseline['sources'][name] = {'missing_legacy': True}
            continue
        assert candidates, 'Missing source: ' + name
        source = candidates[0]
        baseline['sources'][name] = {'path': str(source), 'sha256': tree_hash(source)}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    base = ['sudo', '-u', user, 'nice', '-n', '15', '/usr/bin/python3.10', '/opt/odoo18/odoo-bin']
    options = ['-c', str(conf), '--no-http', '--http-interface=127.0.0.1', '--http-port=0', '--gevent-port=0',
               '--workers=0', '--max-cron-threads=0', '--without-demo=all']
    qa_db = 'FREIGHT_QA_' + args.run_id
    release_root = Path('/opt/steps-managed/freight/development') / proof['commit']
    sha = digest(args.release)
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if args.action in ('qa', 'deploy'):
            for command in Path('/proc').glob('[0-9]*/cmdline'):
                try:
                    argv = command.read_bytes().decode(errors='replace').split('\x00')
                except OSError:
                    continue
                if any(Path(arg).name == 'odoo-bin' for arg in argv):
                    assert not any(arg in ('-u','-i','--update','--init') or arg.startswith(('--update=','--init='))
                                   for arg in argv), 'Concurrent Odoo upgrade PID ' + command.parent.name
        if args.action == 'qa':
            assert not query('postgres', "SELECT 1 FROM pg_database WHERE datname='%s'" % qa_db), 'Fresh clone required'
            (stage / 'baseline.json').write_text(json.dumps(baseline, indent=2))
            with (stage / 'source.dump').open('wb') as stream:
                run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', database, stdout=stream)
            run('sudo', '-u', 'postgres', 'createdb', '-O', opts['db_user'], qa_db)
            query(qa_db, 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
            with (stage / 'source.dump').open('rb') as stream:
                run('sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-acl', '--no-comments',
                    '--role', opts['db_user'], '-d', qa_db, stdin=stream)
            query(qa_db, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
            before = snapshot(qa_db)
            (stage / 'business_before.json').write_text(json.dumps(before, indent=2))
            data = stage / 'data'
            store = Path(opts['data_dir']) / 'filestore' / database
            destination = data / 'filestore' / qa_db
            destination.mkdir(parents=True)
            if store.exists():
                run('rsync', '-a', str(store) + '/', str(destination) + '/')
            for path in [data, *data.rglob('*')]:
                os.chown(path, identity.pw_uid, identity.pw_gid)
            with socket.socket() as listener:
                listener.bind(('127.0.0.1', 0))
                port = listener.getsockname()[1]
            qa_options = [option for option in options if not option.startswith('--http-port=')]
            qa_options += ['--http-port=' + str(port), '--db-filter=^' + qa_db + '$']
            query(qa_db, "UPDATE ir_config_parameter SET value='http://127.0.0.1:%s' WHERE key='web.base.url'" % port)
            log = stage / ('qa-' + stamp + '.log')
            print('FREIGHT_QA_BEGIN ' + json.dumps({'database': qa_db, 'log': str(log), 'commit': proof['commit']}), flush=True)
            result = subprocess.run(base + qa_options + ['-d', qa_db, '--addons-path=' + str(staged) + ',' + opts['addons_path'],
                '--data-dir=' + str(data), '-u', MODULE, '--test-enable', '--test-tags=/' + MODULE,
                '--stop-after-init', '--logfile=' + str(log)])
            text = log.read_text(errors='replace')
            print('\n'.join(line for line in text.splitlines() if 'tests.result' in line or ' ERROR ' in line or ' FAIL' in line)[-6000:], flush=True)
            assert result.returncode == 0 and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests when loading database '
                    + re.escape("'" + qa_db + "'"), text) and not errors(text), 'QA failed: ' + str(log)
        if args.action in ('qa', 'certify'):
            assert json.loads((stage / 'baseline.json').read_text()) == baseline, 'Source/config drift; repeat fresh QA'
            log = next(stage.glob('qa-*.log'))
            text = log.read_text(errors='replace')
            assert re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests when loading database '
                   + re.escape("'" + qa_db + "'"), text) and not errors(text)
            before = json.loads((stage / 'business_before.json').read_text())
            assert snapshot(qa_db, before['schema']) == before, 'Original records/amounts not preserved'
            verify(base, options, qa_db, staged, opts, proof, stage)
            (stage / 'qa_passed.json').write_text(json.dumps({'commit': proof['commit'], 'sha256': sha, 'database': qa_db}))
            print('FREIGHT_QA_OK', flush=True)
            return
        passed = json.loads((stage / 'qa_passed.json').read_text())
        assert passed['commit'] == proof['commit'] and passed['sha256'] == sha
        if args.action == 'deploy':
            assert json.loads((stage / 'baseline.json').read_text()) == baseline, 'Source/config drift; repeat fresh QA'
            assert not release_root.exists()
            release_root.mkdir(parents=True)
            extract(args.release, release_root)
            for path in [release_root, *release_root.rglob('*')]:
                os.chown(path, identity.pw_uid, identity.pw_gid)
            backup = Path('/opt/steps_backups') / ('freight_development_' + stamp)
            backup.mkdir(mode=0o700)
            shutil.copy2(conf, backup / 'odoo.conf')
            run('systemctl', 'stop', service)
            try:
                with (backup / 'database.dump').open('wb') as stream:
                    run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', database, stdout=stream)
                before = snapshot(database)
                new_paths = str(release_root) + ',' + opts['addons_path']
                changed, count = re.subn(r'(?m)^\s*addons_path\s*=.*$', 'addons_path = ' + new_paths, conf.read_text())
                assert count == 1
                conf.write_text(changed)
                log = stage / ('deploy-' + stamp + '.log')
                result = subprocess.run(base + options + ['-d', database, '-u', MODULE, '--stop-after-init', '--logfile=' + str(log)])
                text = log.read_text(errors='replace')
                assert result.returncode == 0 and 'Modules loaded.' in text and not errors(text), str(log)
                assert snapshot(database, before['schema']) == before, 'Original business records not preserved'
                (backup / 'deployment.json').write_text(json.dumps({'commit': proof['commit'], 'sha256': sha,
                    'overlay': str(release_root), 'log': str(log)}))
            finally:
                run('systemctl', 'start', service)
            print('FREIGHT_DEPLOY_OK backup=' + str(backup), flush=True)
        verify(base, options, database, release_root, opts, proof, stage)
        run('systemctl', 'is-active', '--quiet', service)
        for attempt in range(6):
            try:
                with urllib.request.urlopen(target['url'] + '/web/login?db=' + database, timeout=20) as response:
                    assert response.status == 200 and b'password' in response.read()
                break
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(5)
        print('FREIGHT_VERIFY_OK ' + json.dumps({'commit': proof['commit'], 'url': target['url']}), flush=True)


if __name__ == '__main__':
    main()
