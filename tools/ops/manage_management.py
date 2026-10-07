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
SETTINGS = False
PRODUCERS = False
PACKING_INITIAL_MIGRATION = False


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def query(database, sql):
    # stdin also supports the large preservation query without argv limits.
    return subprocess.run(['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1', '-d', database, '-At'],
                          input=sql, text=True, check=True, stdout=subprocess.PIPE).stdout.strip()


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
    existing = set(query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public'").splitlines())
    statements = []
    for table in BUSINESS:
        assert re.fullmatch('[a-z_][a-z0-9_]*', table), 'Invalid preservation table'
        if table in existing:
            row = 'jsonb_strip_nulls(to_jsonb(t))' if PRODUCERS else 'to_jsonb(t)' if SETTINGS else "(to_jsonb(t)-ARRAY['center_id','cost_center_id','write_date'])"
            if MODULES == ('step_packing_operations',) and PACKING_INITIAL_MIGRATION:
                # Only the versioned migration's added fields are excluded;
                # preserve every pre-existing row, ID, quantity and value.
                additions = {
                    'step_packing_production': ['raw_product_id', 'instruction_id', 'sale_order_id'],
                    'stock_quant_package': ['step_packing_production_id', 'step_packaging_id', 'step_packing_line_id'],
                    'step_fruit_package_line': ['source_package_id'],
                    'step_export_stock_reservation': ['destination_country_id', 'sales_program_id', 'species_id', 'variety_id', 'producer_id', 'caliber_id', 'category_id', 'tag_kind'],
                    'step_packing_repack': ['date', 'process_type_id', 'packing_partner_id', 'packing_line_id'],
                }
                if table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            condition = " WHERE key <> 'web.base.url'" if (SETTINGS or PRODUCERS) and table == 'ir_config_parameter' else ''
            statements.append("SELECT '%s',json_build_object('count',count(*),'digest',md5(COALESCE(string_agg(%s::text,'|' ORDER BY %s::text),'')))::text FROM %s t%s" % (table, row, row, table, condition))
    # One SQL statement sees a consistent MVCC snapshot across every table.
    # It preserves the same row normalization and hashes as the former loop.
    return dict(line.split('|', 1) for line in query(database, ' UNION ALL '.join(statements)).splitlines()) if statements else {}


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


def errors(text, allowed_missing=('steps_api',)):
    found = []
    marker = 'Some modules are not loaded, some dependencies or manifest may be missing: '
    for line in text.splitlines():
        if ' ERROR ' not in line and ' CRITICAL ' not in line:
            continue
        if marker in line:
            missing = ast.literal_eval(line.split(marker, 1)[1].strip())
            if set(missing) <= set(allowed_missing):
                continue
        found.append(line)
    return found


def main():
    global MODULES, BUSINESS, SETTINGS, PRODUCERS, PACKING_INITIAL_MIGRATION
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('qa', 'compatibility', 'certify', 'deploy', 'verify'))
    parser.add_argument('environment', choices=('development', 'cerro', 'steps'))
    parser.add_argument('release', type=Path)
    parser.add_argument('run_id')
    parser.add_argument('--kind', choices=('management', 'export', 'homepage', 'settings', 'producers', 'fruit-reception', 'packing'), default='management')
    args = parser.parse_args()
    SETTINGS = args.kind in ('settings', 'fruit-reception', 'packing')
    PRODUCERS = args.kind == 'producers'
    if PRODUCERS:
        assert args.environment == 'development', 'Producer revisions are QA-only'
        MODULES = ('step_producers', 'step_producer_fruit_flow', 'step_export', 'step_producers_integrations')
        BUSINESS = tuple(query('LAB_TAREAS', "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename IN ('res_company','res_partner','res_partner_bank','mrp_bom','mrp_bom_line','ir_config_parameter')) ORDER BY tablename").splitlines())
    if SETTINGS:
        assert args.environment == 'development', 'Settings repair is QA-only'
        MODULES = ('step_packing_operations',) if args.kind == 'packing' else ('step_inventory_packing',) if args.kind == 'fruit-reception' else ('step_account_treasury_batch', 'step_dispatch_guide')
        BUSINESS = tuple(query('LAB_TAREAS', "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename IN ('res_company','res_partner','res_partner_bank','fleet_vehicle','ir_config_parameter')) ORDER BY tablename").splitlines())
    assert args.environment != 'steps' or args.kind == 'homepage'
    if args.kind == 'homepage':
        MODULES = ('step_demo_homepage',)
        BUSINESS = ('account_move', 'account_move_line')
    if args.kind == 'export':
        MODULES = ('step_export',)
        BUSINESS = tuple(query('LAB_TAREAS', "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_export_%' OR tablename IN ('account_move','account_move_line')) ORDER BY tablename").splitlines())
    assert os.geteuid() == 0 and re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
    registry = json.loads((HERE / 'environments.json').read_text())
    assert args.action != 'qa' or args.environment == registry['policy']['qa'], 'Only Desarrollo is QA'
    assert args.action != 'compatibility' or args.environment in registry['policy']['production']
    target = registry['environments'][args.environment]
    database, service = target['database'], target['service']
    allowed_missing = ['steps_api']
    conf = Path(target['config'])
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(conf)
    opts = cfg['options']
    assert opts.get('db_name') == database
    if args.kind == 'homepage' and args.environment == 'steps':
        legacy = query(database, "SELECT latest_version FROM ir_module_module WHERE name='steps_transport' AND state='installed'")
        paths = [Path(item.strip()) for item in opts['addons_path'].split(',')]
        if legacy == '18.0.1.5' and not any((item / 'steps_transport' / '__manifest__.py').exists() for item in paths):
            # Audited pre-existing missing addon in Steps, unrelated to website.
            # The target clone must retain the exact same legacy registration.
            allowed_missing.append('steps_transport')
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
    if args.kind == 'packing':
        PACKING_INITIAL_MIGRATION = tuple(map(int, installed['step_packing_operations'].split('.'))) < (18, 0, 2, 8, 0)
    if PRODUCERS:
        assert set(installed) >= set(MODULES) - {'step_producers_integrations'}, 'Revise only installed agricultural apps'
        assert query(database, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_account_treasury','step_packing_operations') AND state='installed'") == '2', 'Bridge dependencies must already be installed'
    if SETTINGS:
        assert set(installed) == set(MODULES), 'Repair only existing modules'
    if SETTINGS or PRODUCERS:
        assert not query(database, "SELECT name FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove')"), 'Pending upgrades'
    for name, old in installed.items():
        assert tuple(map(int, proof['versions'][name].split('.'))) >= tuple(map(int, old.split('.'))), 'Downgrade refused: ' + name
    update = [name for name in MODULES if name in installed]
    install = ['step_agriculture_catalogs'] if args.kind == 'management' else ['step_producers_integrations'] if PRODUCERS and 'step_producers_integrations' not in installed else []
    if args.kind == 'management' and query(database, "SELECT 1 FROM ir_module_module WHERE name='step_producers' AND state='installed'"):
        install.append('step_management_costs_producers')
    addon_paths = opts['addons_path'].split(',')
    baseline = {'config_sha256': digest(conf), 'modules': {}}
    for name in installed:
        source = next(Path(path.strip()) / name for path in addon_paths if (Path(path.strip()) / name / '__manifest__.py').exists())
        baseline['modules'][name] = {'source': str(source), 'sha256': tree_hash(source), 'version': installed[name]}
    if SETTINGS or PRODUCERS:
        shared = json.loads(query(database, "SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed' AND name LIKE 'step%'"))
        baseline['shared_modules'] = {}
        for name, version in shared.items():
            source = next((Path(path.strip()) / name for path in addon_paths if (Path(path.strip()) / name / '__manifest__.py').exists()), None)
            baseline['shared_modules'][name] = {'version': version, 'sha256': tree_hash(source) if source else None}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    base = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin']
    options = ['-c', str(conf), '--no-http', '--http-interface=127.0.0.1', '--http-port=0', '--gevent-port=0', '--workers=0', '--max-cron-threads=0', '--without-demo=all']
    qa_db = 'MANAGEMENT_QA_' + args.environment.upper() + '_' + args.run_id
    if args.action == 'certify':
        if args.kind == 'homepage' and 'steps_transport' in allowed_missing:
            assert query(qa_db, "SELECT latest_version FROM ir_module_module WHERE name='steps_transport' AND state='installed'") == '18.0.1.5'
        # Retry read-only post-test checks without repeating an unchanged suite.
        assert json.loads((stage / 'baseline.json').read_text()) == baseline
        logs=sorted(stage.glob('qa-*.log'))
        assert len(logs)==1
        text=logs[0].read_text(errors='replace')
        successful = 'Modules loaded.' in text if args.kind == 'homepage' else re.search(r"0 failed, 0 error\(s\) of [1-9][0-9]* tests when loading database '"+re.escape(qa_db)+"'",text)
        assert successful and not errors(text, allowed_missing)
        assert snapshot(qa_db)==json.loads((stage/'business_before.json').read_text())
        verify(base,options,qa_db,staged,opts,proof,stage,{*installed,*install})
        (stage/'qa_passed.json').write_text(json.dumps({'commit':proof['commit'],'release_sha256':release_sha,'database':qa_db,'log':str(logs[0])}))
        print('MANAGEMENT_CERTIFY_OK '+args.environment,flush=True)
        return
    if args.action in ('qa', 'compatibility'):
        if SETTINGS or PRODUCERS:
            settings_lease = open('/run/lock/steps-environments.lock', 'a')
            fcntl.flock(settings_lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for command in Path('/proc').glob('[0-9]*/cmdline'):
                try:
                    argv = command.read_bytes().decode(errors='replace').split('\x00')
                except OSError:
                    continue
                if any(Path(arg).name == 'odoo-bin' for arg in argv):
                    assert not any(arg in ('-u', '-i', '--update', '--init') or arg.startswith(('--update=', '--init=')) for arg in argv), 'Concurrent Odoo upgrade'
        if args.kind == 'homepage':
            from verify_home_heading_http import capture_before
            capture_before(target['url'], stage)
        # Catch import/API compatibility errors before restoring a whole clone.
        import_probe = "import sys,importlib.util\nsys.path.insert(0,'/opt/odoo18')\nspec=importlib.util.spec_from_file_location('odoo.addons.step_agriculture_catalogs.models.catalogs',%r)\nmodule=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\nprint('CATALOG_IMPORT_OK')\n" % str(staged / 'step_agriculture_catalogs/models/catalogs.py')
        if args.kind == 'management':
            run('/usr/bin/python3.10', '-c', import_probe)
        assert not query('postgres', "SELECT 1 FROM pg_database WHERE datname='%s'" % qa_db), 'Use a fresh run_id'
        (stage / 'baseline.json').write_text(json.dumps(baseline, indent=2))
        with (stage / 'source.dump').open('wb') as stream:
            run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', database, stdout=stream)
        run('sudo', '-u', 'postgres', 'createdb', '-O', opts['db_user'], qa_db)
        query(qa_db, 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
        with (stage / 'source.dump').open('rb') as stream:
            run('sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-acl', '--no-comments', '--role', opts['db_user'], '-d', qa_db, stdin=stream)
        # Compare the exact immutable dump restored for this run. The live QA
        # service can legitimately receive edits while pg_dump is running.
        before = snapshot(qa_db)
        (stage / 'business_before.json').write_text(json.dumps(before, indent=2))
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
        init_options = ['-i', ','.join(install)] if install else []
        result = subprocess.run(base + qa_options + ['-d', qa_db, '--addons-path=' + str(staged) + ',' + opts['addons_path'], '--data-dir=' + str(data)] + init_options + ['-u', ','.join(update), '--test-enable', '--test-tags', tags, '--stop-after-init', '--logfile=' + str(log)])
        text = log.read_text(errors='replace')
        print('\n'.join(line for line in text.splitlines() if 'tests.result' in line or ' ERROR ' in line or ' FAIL' in line)[-7000:], flush=True)
        results = re.findall(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests when loading database ' + re.escape("'" + qa_db + "'"), text)
        assert result.returncode == 0 and (results or (args.kind == 'homepage' and 'Modules loaded.' in text)) and not errors(text, allowed_missing), 'QA failed: ' + str(log)
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
                init_options = ['-i', ','.join(install)] if install else []
                result = subprocess.run(base + options + ['-d', database] + init_options + ['-u', ','.join(update), '--stop-after-init', '--logfile=' + str(log)])
                text = log.read_text(errors='replace')
                assert result.returncode == 0 and 'Modules loaded.' in text and not errors(text, allowed_missing), str(log)
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
    export = MODULES == ('step_export',)
    homepage = MODULES == ('step_demo_homepage',)
    probe = (HERE / ('verify_packing_revision.py' if MODULES == ('step_packing_operations',) else 'verify_fruit_reception.py' if MODULES == ('step_inventory_packing',) else 'verify_producer_revision.py' if PRODUCERS else 'verify_settings_navigation.py' if SETTINGS else 'verify_home_heading.py' if homepage else 'verify_export_navigation.py' if export else 'verify_management.py')).read_text()
    names = installed if SETTINGS or PRODUCERS or export or homepage else {*installed, 'step_agriculture_catalogs'}
    header = 'import sys\nsys.path.insert(0,' + repr(str(HERE)) + ')\nROOT=' + repr(str(source)) + '\nEXPECTED=' + repr({name: proof['versions'][name] for name in names}) + '\n'
    result = subprocess.run(base + ['shell'] + options + ['-d', database, '--db-filter=^' + database + '$', '--addons-path=' + str(source) + ',' + opts['addons_path'], '--log-level=error'], input=header + probe, text=True, capture_output=True)
    (stage / ('verify-' + database + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode==0 and 'MANAGEMENT_REGISTRY_OK' in result.stdout, result.stderr[-2500:]
    print('\n'.join(line for line in result.stdout.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK')), flush=True)
    if homepage:
        from verify_home_heading_http import verify_http
        verify_http(base, options, database, source, opts, stage)


if __name__ == '__main__':
    main()
