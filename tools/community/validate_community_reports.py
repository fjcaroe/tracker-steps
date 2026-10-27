"""Private-only Treasury extraction and fresh Cerro-copy validation. No deploy mode.

The clean runtime must be a checkout of official Odoo Community. The copy
retains Enterprise during this first extraction; it is not a full conversion.
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
import sys
from contextlib import ExitStack
import subprocess


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sql(database, statement):
    return run('sudo', '-u', 'postgres', 'psql', '-q', '-v', 'ON_ERROR_STOP=1', '-d', database, '-At',
               input=statement, text=True, capture_output=True).stdout.strip()


def snapshot(database):
    tables = sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND "
                 "(tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'step_%' OR "
                 "tablename LIKE 'hr_%' OR tablename LIKE 'res_users%' OR tablename IN ('ir_ui_menu_group_rel','rule_group_rel','res_groups_implied_rel') OR tablename IN "
                 "('res_company','res_partner','res_currency','res_currency_rate','res_groups_users_rel','res_company_users_rel')) "
                 "ORDER BY tablename").splitlines()
    tables = [t for t in tables if t not in ('step_treasury_report', 'step_treasury_report_partner_rel', 'step_treasury_report_journal_rel')]
    statements = []
    for table in tables:
        assert re.fullmatch('[a-z_][a-z0-9_]*', table)
        # Numeric trailing zeroes are representation only (15.00 == 15).
        # Trim fractional trailing zeroes exactly, including on PostgreSQL 12.
        # No float conversion, rounding, or changes to strings/nulls.
        normalized = "(SELECT jsonb_object_agg(key,CASE WHEN jsonb_typeof(value)='number' " \
            "THEN to_jsonb((CASE WHEN strpos(value#>>'{}','.')>0 THEN " \
            "rtrim(rtrim(value#>>'{}','0'),'.') ELSE value#>>'{}' END)::numeric) " \
            "ELSE value END) FROM jsonb_each(to_jsonb(t)))"
        statements.append("SELECT '" + table + "' AS name, json_build_object('rows',count(*),'hash',"
            "md5(coalesce(string_agg(n::text,E'\\n' ORDER BY n::text),'')),'representation_hash',"
            "md5(coalesce(string_agg(raw::text,E'\\n' ORDER BY raw::text),''))) AS value FROM "
            "(SELECT " + normalized + " AS n,to_jsonb(t) AS raw FROM " + table + ' t) rows')
    if not statements:
        return {}
    # A single SQL statement gives every table the same MVCC snapshot and
    # avoids a separate sudo/psql process per table.
    return json.loads(sql(database, "SET jit=off; SELECT json_object_agg(name,value) FROM (" +
                          ' UNION ALL '.join(statements) + ') snapshots'))


def same_values(before, after):
    return before.keys() == after.keys() and all(
        (before[t]['rows'], before[t]['hash']) == (after[t]['rows'], after[t]['hash']) for t in before)


def field_ids(database):
    return json.loads(sql(database, "SELECT coalesce(json_object_agg(model||'.'||name,id),'{}'::json) FROM ir_model_fields "
        "WHERE (name IN ('operational_currency_id','operational_rate_date','observed_exchange_rate','operational_debit',"
        "'operational_credit','operational_exchange_rate','operational_balance','is_operational_exchange_adjustment',"
        "'conversion_amount','conversion_currency_id') AND model IN ('res.company','res.config.settings','account.move',"
        "'account.move.line','account.payment','account.payment.register')) OR model IN "
        "('step.cashflow','step.cashflow.line','step.treasury.concept','step.vendor.proforma','step.vendor.proforma.line')"))


def report_menus(database):
    return json.loads(sql(database, "SELECT coalesce(json_object_agg(d.name,to_jsonb(m)), '{}'::json) "
        "FROM ir_model_data d JOIN ir_ui_menu m ON m.id=d.res_id WHERE d.module='step_account_treasury' "
        "AND d.model='ir.ui.menu' AND d.name IN ('menu_treasury_bank_reconciliation',"
        "'menu_treasury_partner_ledger','menu_treasury_cash_flow_statement','menu_treasury_aged_receivable',"
        "'menu_treasury_aged_payable')"))


def security_contract(database):
    parts = []
    for model, table in (('ir.model.access', 'ir_model_access'), ('ir.rule', 'ir_rule'), ('res.groups', 'res_groups')):
        parts.append("SELECT d.name, to_jsonb(t)-'write_date'-'write_uid' AS value FROM ir_model_data d "
            "JOIN " + table + " t ON t.id=d.res_id WHERE d.module='step_account_treasury' AND d.model='" + model + "'")
    return json.loads(sql(database, "SELECT json_object_agg(name,value) FROM (" + ' UNION ALL '.join(parts) + ") policies"))


def action_contract(database):
    return json.loads(sql(database, "SELECT json_build_object('all_clients',"
        "(SELECT coalesce(json_object_agg(id,to_jsonb(t)-'write_date'-'write_uid'),'{}'::json) FROM ir_act_client t),"
        "'native_five',(SELECT coalesce(json_object_agg(d.name,to_jsonb(t)),'{}'::json) "
        "FROM ir_model_data d JOIN ir_act_client t ON t.id=d.res_id WHERE d.module='account_reports' "
        "AND d.name IN ('action_account_report_bank_reconciliation','action_account_report_partner_ledger',"
        "'action_account_report_cs','action_account_report_ar','action_account_report_ap')))"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('community', 'cerro-copy'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--database', required=True)
    parser.add_argument('--environment', choices=('cerro','qa-cerro','development'), default='cerro')
    args = parser.parse_args()
    assert os.geteuid() == 0
    root = args.root.resolve(); stage = root / args.mode
    prefix = 'COMMUNITY_TREASURY_' if args.mode == 'community' else 'MANAGEMENT_QA_CERRO_TREASURY_'
    if args.environment == 'qa-cerro': prefix = 'MANAGEMENT_QA_QA-CERRO_'
    assert re.fullmatch(prefix + '[A-Za-z0-9_]+', args.database), 'Only private test databases are allowed'
    assert not stage.exists(), 'Use a new stage/root for a fresh validation; never reset a database'
    stage.mkdir(mode=0o750)
    conf = Path('/etc/dev_odoo18.conf' if args.mode == 'community' or args.environment == 'development' else '/etc/odoo18-qa-cerroelplomo.conf' if args.environment == 'qa-cerro' else '/etc/odoo18-cerroelplomo.conf')
    config = configparser.ConfigParser(interpolation=None); config.read(conf); options = config['options']
    source = options['db_name']; assert source == ('LAB_TAREAS' if args.mode == 'community' or args.environment == 'development' else 'QA-CERROELPLOMO' if args.environment == 'qa-cerro' else 'CERRO_EL_PLOMO')
    user = 'odoo' if args.mode == 'community' or args.environment == 'development' else 'cerroqa_odoo18' if args.environment == 'qa-cerro' else 'cerro_odoo18'
    identity = pwd.getpwnam(user)
    data = stage / 'data'; data.mkdir()
    addons = root / 'addons'
    assert (addons / 'step_accounting_multicurrency_core' / '__manifest__.py').exists()
    fingerprints = {}
    for module in ('step_accounting_multicurrency_core', 'step_accounting_multicurrency', 'step_account_treasury', 'step_account_treasury_reports', 'step_treasury_community_reports'):
        for path in sorted((addons / module).rglob('*')):
            if path.is_file() and '__pycache__' not in path.parts:
                fingerprints[str(path.relative_to(addons))] = hashlib.sha256(path.read_bytes()).hexdigest()
    (stage / 'source-files.json').write_text(json.dumps(fingerprints, indent=2))
    with ExitStack() as stack:
        lock = stack.enter_context(open('/run/lock/steps-environments.lock', 'a'))
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not sql('postgres', "SELECT 1 FROM pg_database WHERE datname='" + args.database + "'"), 'Database already exists'
        if args.environment == 'qa-cerro':
            sys.path.insert(0, str(addons / 'tools/ops'))
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
            source_store = Path(options['data_dir']) / 'filestore' / source
            target_store = data / 'filestore' / args.database; target_store.mkdir(parents=True)
            run('rsync', '-a', str(source_store) + '/', str(target_store) + '/')
            sys.path.insert(0, str(addons / 'tools/community'))
            from manage_community_reports import runtime_contract
            (stage / 'source-contract.json').write_text(json.dumps(runtime_contract(conf), indent=2))
            baseline = snapshot(args.database)
            (stage / 'business-before.json').write_text(json.dumps(baseline, indent=2))
            original_actions = action_contract(args.database)
            (stage / 'actions-before.json').write_text(json.dumps(original_actions, indent=2))
            original_security = security_contract(args.database)
            (stage / 'security-before.json').write_text(json.dumps(original_security, indent=2))
            original_menus = report_menus(args.database)
            (stage / 'menus-before.json').write_text(json.dumps(original_menus, indent=2))
            assert len(original_menus) == 5, 'Expected five original report menus'
            original_fields = field_ids(args.database)
            (stage / 'field-ids-before.json').write_text(json.dumps(original_fields, indent=2))
            runtime = Path('/opt/odoo18')
            addon_paths = str(addons) + ',' + options['addons_path']
            init = ['-i', 'step_accounting_multicurrency_core,step_treasury_community_reports', '-u', 'step_accounting_multicurrency,step_account_treasury']
            tags = '/step_accounting_multicurrency_core,/step_account_treasury,/step_treasury_community_reports,/step_treasury_invoice_payment'
        else:
            runtime = root / 'community-runtime'
            assert (runtime / '.git').exists()
            remote = run('git', '-C', str(runtime), 'remote', 'get-url', 'origin', text=True, capture_output=True).stdout.strip()
            assert remote == 'https://github.com/odoo/odoo.git', 'Use official Community sources'
            revision = run('git', '-C', str(runtime), 'rev-parse', 'HEAD', text=True, capture_output=True).stdout.strip()
            (stage / 'runtime-revision.txt').write_text(revision)
            pure = stage / 'addons'; pure.mkdir()
            for module in ('step_accounting_multicurrency_core', 'step_account_treasury', 'step_treasury_community_reports'):
                (pure / module).symlink_to(addons / module)
            addon_paths = str(pure) + ',' + str(runtime / 'addons')
            init = ['-i', 'step_treasury_community_reports']
            tags = '/step_accounting_multicurrency_core,/step_account_treasury,/step_treasury_community_reports'
        for path in [stage, *stage.rglob('*')]:
            if not path.is_symlink(): os.chown(path, identity.pw_uid, identity.pw_gid)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
        entrypoint = runtime / 'odoo-bin'
        if args.mode == 'cerro-copy':
            # Reuse the reviewed Cerro upgrade adapter: keep already validated
            # canonical fruit FKs while an older base definition loads first.
            entrypoint = addons / 'tools/ops/run_sag_cerro_upgrade.py'
            assert entrypoint.exists()
        base = ['sudo', '-u', user, '/usr/bin/python3.10', str(entrypoint)]
        opts = ['-c', str(conf), '-d', args.database, '--db-filter=^' + args.database + '$',
                '--addons-path=' + addon_paths, '--data-dir=' + str(data), '--load=base,web',
                '--http-interface=127.0.0.1', '--http-port=' + str(port), '--gevent-port=0',
                '--workers=0', '--max-cron-threads=0', '--without-demo=all']
        log = stage / 'tests.log'
        print('COMMUNITY_TREASURY_BEGIN ' + json.dumps({'mode': args.mode, 'database': args.database, 'log': str(log)}), flush=True)
        with (stage / 'bootstrap.log').open('w') as stream:
            result = subprocess.run(base + opts + init + ['--logfile=' + str(log), '--test-enable', '--test-tags=' + tags, '--stop-after-init'], stdout=stream, stderr=subprocess.STDOUT)
        text = log.read_text(errors='replace')
        print('\n'.join(line for line in text.splitlines() if 'tests.result' in line or ' ERROR ' in line or ' CRITICAL ' in line)[-6500:], flush=True)
        assert result.returncode == 0 and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests', text), 'Tests failed: ' + str(log)
        sql(args.database, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        if baseline is not None:
            after = snapshot(args.database); (stage / 'business-after.json').write_text(json.dumps(after, indent=2))
            assert same_values(baseline, after), 'Existing business records changed'
            (stage / 'security-after.json').write_text(json.dumps(security_contract(args.database), indent=2))
            (stage / 'menus-after.json').write_text(json.dumps(report_menus(args.database), indent=2))
            (stage / 'field-ids-after.json').write_text(json.dumps(field_ids(args.database), indent=2))
            (stage / 'actions-after.json').write_text(json.dumps(action_contract(args.database), indent=2))
            assert action_contract(args.database) == original_actions, 'Existing client actions changed'
            assert security_contract(args.database) == original_security, 'Treasury access rules or groups changed'
            assert {k:{f:v for f,v in row.items() if f not in ('action','write_date','write_uid')} for k,row in report_menus(args.database).items()} == {k:{f:v for f,v in row.items() if f not in ('action','write_date','write_uid')} for k,row in original_menus.items()}, 'Report menu IDs or permissions changed'
            assert field_ids(args.database) == original_fields, 'Field IDs changed'
        check = (addons / 'tools/community/verify_community_reports.py').read_text()

        result = subprocess.run(base + ['shell'] + opts + ['--no-http', '--log-level=critical'],
            input='MODE=' + repr(args.mode) + '\n' + check, text=True, capture_output=True)
        (stage / 'verify.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and 'COMMUNITY_TREASURY_REGISTRY_OK' in result.stdout, result.stderr[-2500:]
        print(result.stdout, flush=True)
        if baseline is not None:
            assert same_values(baseline, snapshot(args.database))
        (stage / 'passed.json').write_text(json.dumps({'mode': args.mode, 'database': args.database,
            'tests_log': str(log), 'business_preserved': baseline is not None, 'writes_to_production': False}, indent=2))
        print('COMMUNITY_TREASURY_OK ' + args.mode, flush=True)


if __name__ == '__main__': main()
