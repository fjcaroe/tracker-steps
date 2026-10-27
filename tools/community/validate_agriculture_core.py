"""Validate agricultural ownership extraction in pure Community or a fresh copy.

No deploy, uninstall, license edits or restore over an existing database.
Uses the canonical copy/precision/error safeguards of the Treasury validators.
"""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess
import sys
from contextlib import ExitStack

from validate_community_reports import run, sql, snapshot as finance_snapshot, same_values

MODULES = ('step_agriculture_core', 'step_hr', 'step_agriculture_catalogs', 'step_packing',
           'step_inventory_fruit_tag', 'step_management_costs', 'step_management_costs_agriculture')
BASE_MODULES = MODULES
PRODUCER_MODULES = ('step_producers', 'step_producer_contract_report', 'step_producer_estimate_report',
                    'step_producer_purchase_mode', 'step_management_costs_producers')
OPERATIONS_MODULES = ('step_operations_core', 'step_machinery', 'step_project_agriculture_scope',
                      'step_management_costs_machinery')

LABOR_MODULES = ('step_labor_operations_core', 'step_mobilization', 'step_mobilization_agriculture')

# Regenerable compiled web bundles only. Business files, view attachments,
# source maps, private files and anything without the exact cache URL stay strict.
GENERATED_ASSET_CACHE = """(t.res_model='ir.ui.view' AND t.res_field IS NULL
 AND t.res_id=0 AND t.type='binary' AND t.public IS TRUE
 AND t.mimetype IN ('text/css','application/javascript')
 AND t.url ~ '^/web/assets/[0-9a-f]+/[^/]+[.](css|js)$')"""


def verify_native(base, opts, addons, stage, mode):
    check = (addons / 'tools/community/verify_agriculture_core.py').read_text()
    if 'step_producers' in MODULES:
        check += '\n' + (addons / 'tools/community/verify_producers.py').read_text()
    if 'step_operations_core' in MODULES:
        check += '\n' + (addons / 'tools/community/verify_operations.py').read_text()
    if 'step_labor_operations_core' in MODULES:
        check += '\n' + (addons / 'tools/community/verify_labor.py').read_text()
    result = subprocess.run(base + ['shell'] + opts + ['--no-http', '--log-level=critical'],
        input='MODE=' + repr(mode) + '\n' + check, text=True, capture_output=True)
    (stage / 'verify.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'AGRICULTURE_NATIVE_OK' in result.stdout, result.stderr[-3000:]
    if 'step_operations_core' in MODULES:
        assert 'OPERATIONS_NATIVE_OK' in result.stdout and 'PRODUCERS_NATIVE_OK' in result.stdout
    if 'step_labor_operations_core' in MODULES:
        assert 'LABOR_NATIVE_OK' in result.stdout
    print(result.stdout, flush=True)


def verify_existing(args):
    assert args.mode == 'community', 'This post-check only accepts the pure private Community stage'
    root = args.root.resolve(); stage = root / args.mode; addons = root / 'addons'
    proof = json.loads((stage / 'passed.json').read_text())
    assert proof['database'] == args.database
    for relative, digest in json.loads((stage / 'source-files.json').read_text()).items():
        assert hashlib.sha256((addons / relative).read_bytes()).hexdigest() == digest, relative
    conf = '/etc/dev_odoo18.conf'
    runtime = root / 'community-runtime'
    assert run('git', '-C', str(runtime), 'remote', 'get-url', 'origin', text=True,
               capture_output=True).stdout.strip() == 'https://github.com/odoo/odoo.git'
    opts = ['-c', conf, '-d', args.database, '--addons-path=' + str(stage / 'addons') + ',' + str(runtime / 'addons'),
            '--data-dir=' + str(stage / 'data'), '--load=base,web', '--workers=0', '--max-cron-threads=0']
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        verify_native(['sudo', '-u', 'odoo', '/usr/bin/python3.10', str(runtime / 'odoo-bin')],
                      opts, addons, stage, args.mode)


def snapshot(database):
    result = finance_snapshot(database)
    for table in ('product_template', 'product_product', 'fleet_vehicle', 'res_sector'):
        result[table] = json.loads(sql(database,
            "SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,"
            "E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM " + table + ' t'))
    operational_tables = sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND "
        "(tablename LIKE 'project_%' OR tablename LIKE 'fleet_%' OR tablename LIKE 'monthly_%' OR "
        "tablename LIKE 'real_cost_%' OR tablename LIKE 'regist_cost_%' OR tablename IN ('type_service_machinery','type_costing_machinery')) ORDER BY tablename").splitlines()
    for table in operational_tables:
        assert re.fullmatch('[a-z_][a-z0-9_]*', table)
        result[table] = json.loads(sql(database,
            "SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,"
            "E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM " + table + ' t'))
    if 'step_labor_operations_core' in MODULES:
        labor_tables = sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND "
            "(tablename LIKE 'tarja_%' OR tablename LIKE 'product_pricelist%' OR tablename IN "
            "('partner_pricelist_rel','grupo_variedad_pricelist_rel','step_analytic_pricelist_rel')) ORDER BY tablename").splitlines()
        for table in labor_tables:
            assert re.fullmatch('[a-z_][a-z0-9_]*', table)
            result[table] = json.loads(sql(database,
                "SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,"
                "E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM " + table + ' t'))
    # These SQL projections retain their source row IDs, dates, quantities and
    # monetary values when only the presentation changes from Gantt to Calendar.
    for table in ('step_producer_contract_report', 'step_producer_estimate_report'):
        if sql(database, "SELECT to_regclass('" + table + "') IS NOT NULL") == 't':
            result[table] = json.loads(sql(database,
                "SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,"
                "E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM " + table + ' t'))
    # Only new core menu memberships are added. Original menu memberships
    # remain exact and are also checked in the identity contract.
    result['ir_ui_menu_group_rel'] = json.loads(sql(database,
        "SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,"
        "E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM ir_ui_menu_group_rel t WHERE menu_id NOT IN "
        "(SELECT res_id FROM ir_model_data WHERE module IN ('step_agriculture_core','step_labor_operations_core') AND model='ir.ui.menu')"))
    return result


def source_contract(conf, addons):
    sys.path.insert(0, str(addons / 'tools/community'))
    from manage_community_reports import runtime_contract
    result = runtime_contract(conf)
    config = configparser.ConfigParser(interpolation=None); assert config.read(conf)
    roots = [Path(p.strip()) for p in config['options']['addons_path'].split(',')]
    sources = {}
    for module in MODULES:
        directory = next((p / module for p in roots if (p / module / '__manifest__.py').exists()), None)
        sources[module] = None if directory is None else {
            str(p.relative_to(directory)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(directory.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    result['agriculture_sources'] = sources
    return result


def identity_contract(database):
    # Include ALL original field/model IDs, policies, menus and action-view
    # bindings, not just the agricultural subset. Ignore write audit only.
    queries = []
    for table in ('ir_model', 'ir_model_fields', 'ir_model_fields_selection', 'ir_model_access', 'ir_rule', 'ir_ui_menu',
                  'ir_act_window_view', 'ir_ui_menu_group_rel', 'rule_group_rel',
                  'res_groups_implied_rel'):
        queries.append("SELECT '" + table + "' AS name,coalesce(jsonb_agg(to_jsonb(t)-'write_date'-'write_uid' "
                       "ORDER BY to_jsonb(t)::text),'[]'::jsonb) AS value FROM " + table + ' t')
    return json.loads(sql(database, 'SELECT json_object_agg(name,value) FROM (' +
                          ' UNION ALL '.join(queries) + ') t'))


def history_contract(database):
    queries = []
    for table in ('mail_message', 'mail_tracking_value', 'mail_followers', 'mail_activity', 'ir_attachment'):
        payload = ("CASE WHEN t.res_model='ir.ui.menu' AND t.res_field='web_icon_data' THEN "
                   "to_jsonb(t)-'write_date'-'write_uid' ELSE to_jsonb(t) END") if table == 'ir_attachment' else 'to_jsonb(t)'
        where = (' WHERE NOT coalesce(' + GENERATED_ASSET_CACHE + ',false)') if (
            table == 'ir_attachment' and 'step_operations_core' in MODULES) else ''
        queries.append("SELECT '" + table + "' AS name,json_build_object('rows',count(*),'hash',"
                       "md5(coalesce(string_agg((" + payload + ")::text,E'\\n' ORDER BY (" + payload + ")::text),''))) AS value FROM " + table + ' t' + where)
    queries.append("SELECT 'expiration',coalesce(json_object_agg(key,value),'{}'::json) FROM ir_config_parameter "
                   "WHERE key IN ('database.expiration_date','database.expiration_reason')")
    return json.loads(sql(database, 'SELECT json_object_agg(name,value) FROM (' +
                          ' UNION ALL '.join(queries) + ') t'))


def main():
    global MODULES
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('community', 'cerro-copy'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--environment', choices=('cerro', 'development', 'qa-cerro'), default='cerro')
    parser.add_argument('--profile', choices=('agriculture', 'producers', 'operations', 'labor'), default='agriculture')
    parser.add_argument('--verify-existing', action='store_true', help='Add native checks to an already passed pure stage')
    args = parser.parse_args()
    MODULES = BASE_MODULES + (PRODUCER_MODULES if args.profile in ('producers','operations','labor') else ()) + (
        OPERATIONS_MODULES if args.profile in ('operations','labor') else ()) + (
        LABOR_MODULES if args.profile == 'labor' else ())
    assert os.geteuid() == 0
    assert re.fullmatch(('COMMUNITY_AGRICULTURE_' if args.mode == 'community' else
                         'MANAGEMENT_QA_QA-CERRO_' if args.environment == 'qa-cerro' else
                         'MANAGEMENT_QA_CERRO_AGRICULTURE_') + '[A-Za-z0-9_]+', args.database)
    if args.verify_existing:
        verify_existing(args)
        return
    root = args.root.resolve(); stage = root / args.mode
    assert not stage.exists(), 'Fresh validation root required'
    stage.mkdir(mode=0o750)
    addons = root / 'addons'
    fingerprints = {str(path.relative_to(addons)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for module in MODULES for path in sorted((addons / module).rglob('*'))
                    if path.is_file() and '__pycache__' not in path.parts}
    (stage / 'source-files.json').write_text(json.dumps(fingerprints, indent=2))
    conf = Path('/etc/dev_odoo18.conf' if args.mode == 'community' or args.environment == 'development' else
                '/etc/odoo18-qa-cerroelplomo.conf' if args.environment == 'qa-cerro' else '/etc/odoo18-cerroelplomo.conf')
    config = configparser.ConfigParser(interpolation=None); assert config.read(conf)
    options = config['options']
    source = options['db_name']
    assert source == ('LAB_TAREAS' if args.mode == 'community' or args.environment == 'development' else
                      'QA-CERROELPLOMO' if args.environment == 'qa-cerro' else 'CERRO_EL_PLOMO')
    user = 'odoo' if args.mode == 'community' or args.environment == 'development' else (
        'cerroqa_odoo18' if args.environment == 'qa-cerro' else 'cerro_odoo18')
    identity = pwd.getpwnam(user)
    data = stage / 'data'; data.mkdir()
    with ExitStack() as stack:
        lock = stack.enter_context(open('/run/lock/steps-environments.lock', 'a'))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not sql('postgres', "SELECT 1 FROM pg_database WHERE datname='" + args.database + "'")
        sys.path.insert(0, str(addons / 'tools/ops'))
        if args.environment == 'qa-cerro':
            from customer_qa_clone_access import clone_database_access
            stack.enter_context(clone_database_access(sql, args.database, stage))
        run('sudo', '-u', 'postgres', 'createdb', '--owner=' + options['db_user'], args.database)
        baseline = None
        if args.mode == 'cerro-copy':
            with (stage / 'source.dump').open('wb') as stream:
                run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', source, stdout=stream)
            with (stage / 'source.dump').open('rb') as stream:
                run('sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-acl', '--no-comments',
                    '--role=' + options['db_user'], '-d', args.database, stdin=stream)
            sql(args.database, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
            store = data / 'filestore' / args.database; store.mkdir(parents=True)
            run('rsync', '-a', str(Path(options['data_dir']) / 'filestore' / source) + '/', str(store) + '/')
            contract = source_contract(conf, addons)
            (stage / 'source-contract.json').write_text(json.dumps(contract, indent=2))
            baseline = snapshot(args.database)
            original = identity_contract(args.database)
            calendar_bindings = json.loads(sql(args.database,
                "SELECT coalesce(json_agg(t.id),'[]'::json) FROM ir_act_window_view t "
                "JOIN ir_model_data d ON d.res_id=t.view_id AND d.model='ir.ui.view' "
                "WHERE d.name='report_gantt' AND d.module IN ('step_producer_contract_report',"
                "'step_producer_estimate_report')")) if args.profile in ('producers','operations','labor') else []
            if args.profile in ('producers','operations','labor'):
                assert len(calendar_bindings) == 2, 'Expected two original report-view bindings'
            (stage / 'calendar-bindings-before.json').write_text(json.dumps(calendar_bindings))
            history = history_contract(args.database)
            for name, value in [('business-before', baseline), ('identity-before', original), ('history-before', history)]:
                (stage / (name + '.json')).write_text(json.dumps(value, indent=2))
            runtime = Path('/opt/odoo18')
            addon_paths = str(addons) + ',' + options['addons_path']
            installed = contract['installed_versions']
            upgrades = [m for m in MODULES if m in installed]
            new_cores = [m for m in ('step_agriculture_core','step_operations_core','step_labor_operations_core')
                         if m in MODULES and m not in installed]
            init = (['-i', ','.join(new_cores)] if new_cores else []) + (
                ['-u', ','.join(upgrades)] if upgrades else [])
            entrypoint = addons / 'tools/ops/run_agriculture_upgrade.py'
        else:
            runtime = root / 'community-runtime'
            assert (runtime / '.git').exists()
            assert run('git', '-C', str(runtime), 'remote', 'get-url', 'origin', text=True,
                       capture_output=True).stdout.strip() == 'https://github.com/odoo/odoo.git'
            assert not run('git', '-C', str(runtime), 'status', '--porcelain', text=True,
                           capture_output=True).stdout.strip(), 'Official Community checkout must be clean'
            (stage / 'runtime-revision.txt').write_text(run('git', '-C', str(runtime), 'rev-parse', 'HEAD',
                                                         text=True, capture_output=True).stdout)
            pure = stage / 'addons'; pure.mkdir()
            for module in MODULES:
                if module == 'step_hr':
                    continue
                (pure / module).symlink_to(addons / module)
            addon_paths = str(pure) + ',' + str(runtime / 'addons')
            init = ['-i', 'step_agriculture_catalogs,step_packing,step_inventory_fruit_tag,step_management_costs_agriculture']
            if args.profile in ('producers','operations','labor'):
                init[1] += ',' + ','.join(PRODUCER_MODULES)
            if args.profile in ('operations','labor'):
                init[1] += ',' + ','.join(OPERATIONS_MODULES)
            if args.profile == 'labor':
                init[1] += ',' + ','.join(LABOR_MODULES)
            entrypoint = runtime / 'odoo-bin'
        for path in [stage, *stage.rglob('*')]:
            if not path.is_symlink(): os.chown(path, identity.pw_uid, identity.pw_gid)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
        base = ['sudo', '-u', user, '/usr/bin/python3.10', str(entrypoint)]
        opts = ['-c', str(conf), '-d', args.database, '--db-filter=^' + args.database + '$',
                '--addons-path=' + addon_paths, '--data-dir=' + str(data), '--load=base,web',
                '--http-interface=127.0.0.1', '--http-port=' + str(port), '--gevent-port=0',
                '--workers=0', '--max-cron-threads=0', '--without-demo=all']
        log = stage / 'tests.log'
        print('AGRICULTURE_BEGIN ' + str(log), flush=True)
        with (stage / 'bootstrap.log').open('w') as stream:
            result = subprocess.run(base + opts + init + ['--logfile=' + str(log), '--test-enable',
                '--test-tags=' + ','.join('/' + m for m in MODULES if m != 'step_hr'), '--stop-after-init'],
                stdout=stream, stderr=subprocess.STDOUT)
        text = log.read_text(errors='replace')
        print('\n'.join(line for line in text.splitlines() if 'tests.result' in line or
                        ' ERROR ' in line or ' CRITICAL ' in line)[-6500:], flush=True)
        from manage_management import errors
        allowed = tuple(n for n in ('steps_api',) if args.mode != 'community' and n in installed)
        assert result.returncode == 0 and not errors(text, allowed) and re.search(
            r'0 failed, 0 error\(s\) of [1-9][0-9]* tests', text), 'Tests failed: ' + str(log)
        verify_native(base, opts, addons, stage, args.mode)
        if baseline is not None:
            after = snapshot(args.database); (stage / 'business-after.json').write_text(json.dumps(after, indent=2))
            current = identity_contract(args.database); (stage / 'identity-after.json').write_text(json.dumps(current, indent=2))
            final_history = history_contract(args.database); (stage / 'history-after.json').write_text(json.dumps(final_history, indent=2))
            assert same_values(baseline, after), 'Existing business values changed'
            for table, rows in original.items():
                # New core menus/metadata are expected; each preexisting row is exact.
                if table in ('ir_model', 'ir_model_fields'):
                    now = {r['id']: r for r in current[table]}
                    for row in rows:
                        got = now.get(row['id'])
                        assert got and all(got[k] == v for k,v in row.items() if k != 'modules'), (table, row['id'])
                else:
                    expected = [dict(row, view_mode='calendar') if table == 'ir_act_window_view' and
                                row['id'] in calendar_bindings and row['view_mode'] in ('gantt', 'calendar') else row
                                for row in rows]
                    assert all(row in current[table] for row in expected), 'Existing identities changed: ' + table
            assert final_history == history, 'Chatter, attachments or expiration changed'
            assert source_contract(conf, addons) == contract, 'Source service configuration, versions or files changed'
        (stage / 'passed.json').write_text(json.dumps({'mode': args.mode, 'database': args.database,
            'environment': args.environment, 'business_preserved': baseline is not None,
            'profile': args.profile,
            'writes_to_source': False, 'modules': MODULES, 'files': len(fingerprints)}, indent=2))
        print('AGRICULTURE_OK ' + args.mode, flush=True)


if __name__ == '__main__':
    main()
