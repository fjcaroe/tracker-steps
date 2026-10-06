"""Test and promote the same agricultural management package without downgrades.

Private overlays avoid replacing addon roots shared with production. A passed
clone, unchanged source/config baseline, lease and backup are required to promote.
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
import urllib.request

HERE = Path(__file__).resolve().parent
MODULES = ('step_management_costs', 'step_management_costs_agriculture', 'step_management_costs_machinery',
           'step_management_costs_tracker', 'step_agriculture_catalogs', 'step_management_costs_producers')
BUSINESS = ('step_management_operational_budget', 'step_management_budget_line', 'step_management_budget_center',
            'step_management_estimation', 'step_management_estimation_line', 'step_management_historical_cost',
            'step_management_plan', 'step_management_production_order', 'step_management_crop_program')


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def query(database, sql):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1', '-d', database, '-Atc', sql], text=True).strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(path):
    digestor = hashlib.sha256()
    for file in sorted(path.rglob('*')):
        if file.is_file() and file.suffix in {'.py', '.xml', '.csv', '.js', '.scss', '.css'} and '__pycache__' not in file.parts:
            digestor.update(str(file.relative_to(path)).encode())
            digestor.update(file.read_bytes().replace(b'\r\n', b'\n'))
    return digestor.hexdigest()


def snapshot(database):
    result = {}
    for table in BUSINESS:
        if query(database, "SELECT to_regclass('%s')" % table):
            result[table] = query(database, "SELECT json_build_object('count',count(*),'digest',md5(COALESCE(string_agg((to_jsonb(t)-ARRAY['center_id','cost_center_id','write_date'])::text,'|' ORDER BY id),''))) FROM %s t" % table)
    return result


def extract(release, target):
    with tarfile.open(release) as archive:
        proof = json.loads(archive.extractfile('release.json').read())
        assert re.fullmatch('[0-9a-f]{40}', proof['commit'])
        assert set(proof['versions']) == set(MODULES)
        found = set()
        for member in archive.getmembers():
            path = Path(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            assert member.name == 'release.json' or path.parts[0] in MODULES
            assert member.name not in found
            found.add(member.name)
            if member.name != 'release.json':
                assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == proof['files'][member.name]
        assert found == set(proof['files']) | {'release.json'}
        archive.extractall(target)
    return proof


def errors(text):
    return [line for line in text.splitlines() if (' ERROR ' in line or ' CRITICAL ' in line) and
            not line.rstrip().endswith("Some modules are not loaded, some dependencies or manifest may be missing: ['steps_api']")]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('qa', 'compatibility', 'deploy', 'verify'))
    parser.add_argument('environment', choices=('development', 'cerro'))
    parser.add_argument('release', type=Path)
    parser.add_argument('run_id')
    args = parser.parse_args()
    assert os.geteuid() == 0 and re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
    registry = json.loads((HERE / 'environments.json').read_text())
    assert args.action != 'qa' or args.environment == registry['policy']['qa'], 'Only Desarrollo is QA'
    assert args.action != 'compatibility' or args.environment in registry['policy']['production']
    target = registry['environments'][args.environment]
    database, service = target['database'], target['service']
    conf = Path(target['config'])
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(conf)
    opts = cfg['options']
    assert opts.get('db_name') == database
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', service], text=True).strip()
    identity = pwd.getpwnam(user)
    stage = Path('/opt/steps-validation') / ('management_' + args.environment + '_' + args.run_id)
    stage.mkdir(parents=True, exist_ok=True, mode=0o750)
    os.chown(stage, identity.pw_uid, identity.pw_gid)
    staged = stage / 'addons'
    staged.mkdir(exist_ok=True)
    proof = extract(args.release, staged)
    for path in [staged, *staged.rglob('*')]:
        os.chown(path, identity.pw_uid, identity.pw_gid)
    release_sha = digest(args.release)
    installed = json.loads(query(database, "SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed' AND name IN (%s)" % ','.join("'%s'" % name for name in MODULES)))
    for name, old in installed.items():
        assert tuple(map(int, proof['versions'][name].split('.'))) >= tuple(map(int, old.split('.'))), 'Downgrade refused: ' + name
    update = [name for name in MODULES if name in installed]
    install = ['step_agriculture_catalogs']
    if query(database, "SELECT 1 FROM ir_module_module WHERE name='step_producers' AND state='installed'"):
        install.append('step_management_costs_producers')
    addon_paths = opts['addons_path'].split(',')
    baseline = {'config_sha256': digest(conf), 'modules': {}}
    for name in installed:
        source = next(Path(path.strip()) / name for path in addon_paths if (Path(path.strip()) / name / '__manifest__.py').exists())
        baseline['modules'][name] = {'source': str(source), 'sha256': tree_hash(source), 'version': installed[name]}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    base = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin']
    options = ['-c', str(conf), '--no-http', '--http-interface=127.0.0.1', '--http-port=0', '--gevent-port=0', '--workers=0', '--max-cron-threads=0', '--without-demo=all']
    qa_db = 'MANAGEMENT_QA_' + args.environment.upper() + '_' + args.run_id
    if args.action in ('qa', 'compatibility'):
        # Catch import/API compatibility errors before restoring a whole clone.
        import_probe = "import sys,importlib.util\nsys.path.insert(0,'/opt/odoo18')\nspec=importlib.util.spec_from_file_location('odoo.addons.step_agriculture_catalogs.models.catalogs',%r)\nmodule=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\nprint('CATALOG_IMPORT_OK')\n" % str(staged / 'step_agriculture_catalogs/models/catalogs.py')
        run('/usr/bin/python3.10', '-c', import_probe)
        assert not query('postgres', "SELECT 1 FROM pg_database WHERE datname='%s'" % qa_db), 'Use a fresh run_id'
        (stage / 'baseline.json').write_text(json.dumps(baseline, indent=2))
        before = snapshot(database)
        (stage / 'business_before.json').write_text(json.dumps(before, indent=2))
        with (stage / 'source.dump').open('wb') as stream:
            run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', database, stdout=stream)
        run('sudo', '-u', 'postgres', 'createdb', '-O', opts['db_user'], qa_db)
        query(qa_db, 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
        with (stage / 'source.dump').open('rb') as stream:
            run('sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-comments', '--role', opts['db_user'], '-d', qa_db, stdin=stream)
        query(qa_db, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        data = stage / 'data'
        source_store = Path(opts['data_dir']) / 'filestore' / database
        if source_store.exists():
            destination = data / 'filestore' / qa_db
            destination.mkdir(parents=True, exist_ok=True)
            run('rsync', '-a', str(source_store) + '/', str(destination) + '/')
        for path in [data, *data.rglob('*')] if data.exists() else []:
            os.chown(path, identity.pw_uid, identity.pw_gid)
        log = stage / ('qa-' + stamp + '.log')
        # HTTP tests must use a real private port and must never select the
        # source service's database through its inherited dbfilter.
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            private_port = listener.getsockname()[1]
        qa_options = [option for option in options if not option.startswith('--http-port=')]
        qa_options += ['--http-port=' + str(private_port), '--db-filter=^' + qa_db + '$']
        query(qa_db, "UPDATE ir_config_parameter SET value='http://127.0.0.1:%s' WHERE key='web.base.url'" % private_port)
        print('MANAGEMENT_QA_BEGIN ' + json.dumps({'database': qa_db, 'log': str(log), 'commit': proof['commit']}), flush=True)
        tags = ','.join('/' + name for name in [*update, *install])
        result = subprocess.run(base + qa_options + ['-d', qa_db, '--addons-path=' + str(staged) + ',' + opts['addons_path'], '--data-dir=' + str(data), '-i', ','.join(install), '-u', ','.join(update), '--test-enable', '--test-tags', tags, '--stop-after-init', '--logfile=' + str(log)])
        text = log.read_text(errors='replace')
        print('\n'.join(line for line in text.splitlines() if 'tests.result' in line or ' ERROR ' in line or ' FAIL' in line)[-7000:], flush=True)
        results = re.findall(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests when loading database ' + re.escape("'" + qa_db + "'"), text)
        assert result.returncode == 0 and results and not errors(text), 'QA failed: ' + str(log)
        assert snapshot(qa_db) == before, 'Business amounts/rows changed during migration'
        verify(base, options, qa_db, staged, opts, proof, stage, {*installed, *install})
        (stage / 'qa_passed.json').write_text(json.dumps({'commit': proof['commit'], 'release_sha256': release_sha, 'database': qa_db, 'log': str(log)}))
        print('MANAGEMENT_QA_OK ' + args.environment, flush=True)
        return
    passed = json.loads((stage / 'qa_passed.json').read_text())
    assert passed['commit'] == proof['commit'] and passed['release_sha256'] == release_sha
    release_root = Path('/opt/steps-managed/releases') / args.environment / proof['commit']
    if args.action == 'deploy':
        if args.environment != registry['policy']['qa']:
            qa_root = Path('/opt/steps-managed/releases/development') / proof['commit']
            assert (qa_root / 'release.json').exists(), 'First deliver this package to Desarrollo for review'
            assert json.loads((qa_root / 'release.json').read_text()) == proof
        assert json.loads((stage / 'baseline.json').read_text()) == baseline, 'Concurrent source/config change; repeat QA from current baseline'
        with open('/run/lock/steps-environments.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for command in Path('/proc').glob('[0-9]*/cmdline'):
                try:
                    argv = command.read_bytes().decode(errors='replace').split('\x00')
                except OSError:
                    continue
                for index, arg in enumerate(argv):
                    if Path(arg).name == 'odoo-bin':
                        assert not any(option in ('-u', '-i', '--update', '--init') or option.startswith(('--update=', '--init=')) for option in argv[index + 1:]), 'Concurrent upgrade PID ' + command.parent.name
            assert not release_root.exists(), 'Release already exists'
            release_root.mkdir(parents=True)
            extract(args.release, release_root)
            for path in [release_root, *release_root.rglob('*')]:
                os.chown(path, identity.pw_uid, identity.pw_gid)
            backup = Path('/opt/steps_backups') / ('management_' + args.environment + '_' + stamp)
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
                result = subprocess.run(base + options + ['-d', database, '-i', ','.join(install), '-u', ','.join(update), '--stop-after-init', '--logfile=' + str(log)])
                text = log.read_text(errors='replace')
                assert result.returncode == 0 and 'Modules loaded.' in text and not errors(text), str(log)
                assert snapshot(database) == before, 'Business migration check failed'
                # T52 explicitly asks that current Cerro catalog entries be shared.
                if args.environment == 'cerro':
                    script = "from odoo import Command\nmodels=('step.temporada','step.especie','step.grupo.variedad','step.variedad')\nfor name in models:\n    records=env[name].search([])\n    records.with_context(_install_scope=__import__('odoo.addons.step_agriculture_catalogs.models.catalogs',fromlist=['_INSTALL_SCOPE'])._INSTALL_SCOPE).write({'company_ids':[Command.clear()]})\nfor name in models:\n    env[name].search([])._check_catalog_scope()\nenv.cr.commit()\nprint('CERRO_CATALOGS_SHARED_OK')\n"
                    result = run(*(base[:4] + [base[4], 'shell'] + options + ['-d', database, '--log-level=error']), input=script, text=True, capture_output=True)
                    assert 'CERRO_CATALOGS_SHARED_OK' in result.stdout
                (backup / 'deployment.json').write_text(json.dumps({'commit': proof['commit'], 'sha256': release_sha, 'overlay': str(release_root), 'log': str(log)}))
            except Exception:
                # Keep the upgraded DB and recovery dump; never silently discard business data.
                print('MANAGEMENT_DEPLOY_FAILED backup=' + str(backup), flush=True)
                raise
            finally:
                run('systemctl', 'start', service)
            print('MANAGEMENT_DEPLOY_OK backup=' + str(backup), flush=True)
    verify(base, options, database, release_root, opts, proof, stage, {*installed, *install})
    run('systemctl', 'is-active', '--quiet', service)
    with urllib.request.urlopen(target['url'] + '/web/login?db=' + database, timeout=30) as response:
        assert response.status == 200 and b'password' in response.read()
    print('MANAGEMENT_VERIFY_OK ' + json.dumps({'environment': args.environment, 'commit': proof['commit'], 'url': target['url']}), flush=True)


def verify(base, options, database, source, opts, proof, stage, installed):
    probe = (HERE / 'verify_management.py').read_text()
    header = 'ROOT=' + repr(str(source)) + '\nEXPECTED=' + repr({name: proof['versions'][name] for name in [*installed, 'step_agriculture_catalogs']}) + '\n'
    result = run(*(base + ['shell'] + options + ['-d', database, '--db-filter=^' + database + '$', '--addons-path=' + str(source) + ',' + opts['addons_path'], '--log-level=error']), input=header + probe, text=True, capture_output=True)
    (stage / ('verify-' + database + '.log')).write_text(result.stdout + result.stderr)
    assert 'MANAGEMENT_REGISTRY_OK' in result.stdout, result.stderr[-2500:]
    print('\n'.join(line for line in result.stdout.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK')), flush=True)


if __name__ == '__main__':
    main()
