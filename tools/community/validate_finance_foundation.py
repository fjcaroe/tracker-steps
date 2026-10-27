"""Private-only Community core and fresh Cerro-copy validation. No deploy mode.

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
import subprocess


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def sql(database, statement):
    return run('sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1', '-d', database, '-At',
               input=statement, text=True, capture_output=True).stdout.strip()


def snapshot(database):
    tables = sql(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND "
                 "(tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'step_%' OR "
                 "tablename LIKE 'hr_%' OR tablename LIKE 'res_users%' OR tablename IN "
                 "('res_company','res_partner','res_currency','res_currency_rate','res_groups_users_rel','res_company_users_rel')) "
                 "ORDER BY tablename").splitlines()
    result = {}
    for table in tables:
        assert re.fullmatch('[a-z_][a-z0-9_]*', table)
        value = sql(database, "SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),''))) FROM " + table + ' t')
        result[table] = json.loads(value)
    return result


def field_ids(database):
    return json.loads(sql(database, "SELECT coalesce(json_object_agg(model||'.'||name,id),'{}'::json) FROM ir_model_fields "
        "WHERE name IN ('operational_currency_id','operational_rate_date','observed_exchange_rate','operational_debit',"
        "'operational_credit','operational_exchange_rate','operational_balance','is_operational_exchange_adjustment',"
        "'conversion_amount','conversion_currency_id') AND model IN ('res.company','res.config.settings','account.move',"
        "'account.move.line','account.payment','account.payment.register')"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('community', 'cerro-copy'))
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--database', required=True)
    args = parser.parse_args()
    assert os.geteuid() == 0
    root = args.root.resolve(); stage = root / args.mode
    prefix = 'COMMUNITY_FOUNDATION_' if args.mode == 'community' else 'MANAGEMENT_QA_CERRO_COMMUNITY_'
    assert re.fullmatch(prefix + '[A-Za-z0-9_]+', args.database), 'Only private test databases are allowed'
    assert not stage.exists(), 'Use a new stage/root for a fresh validation; never reset a database'
    stage.mkdir(mode=0o750)
    conf = Path('/etc/dev_odoo18.conf' if args.mode == 'community' else '/etc/odoo18-cerroelplomo.conf')
    config = configparser.ConfigParser(interpolation=None); config.read(conf); options = config['options']
    source = options['db_name']; assert source == ('LAB_TAREAS' if args.mode == 'community' else 'CERRO_EL_PLOMO')
    user = 'odoo' if args.mode == 'community' else 'cerro_odoo18'
    identity = pwd.getpwnam(user)
    data = stage / 'data'; data.mkdir()
    addons = root / 'addons'
    assert (addons / 'step_accounting_multicurrency_core' / '__manifest__.py').exists()
    with open('/run/lock/steps-environments.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert not sql('postgres', "SELECT 1 FROM pg_database WHERE datname='" + args.database + "'"), 'Database already exists'
        run('sudo', '-u', 'postgres', 'createdb', '--owner=' + options['db_user'], args.database)
        baseline = None
        if args.mode == 'cerro-copy':
            with (stage / 'source.dump').open('wb') as stream:
                run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', source, stdout=stream)
            run('sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-acl', '--no-comments',
                '--role=' + options['db_user'], '-d', args.database, str(stage / 'source.dump'))
            sql(args.database, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
            source_store = Path(options['data_dir']) / 'filestore' / source
            target_store = data / 'filestore' / args.database; target_store.mkdir(parents=True)
            run('rsync', '-a', str(source_store) + '/', str(target_store) + '/')
            baseline = snapshot(args.database)
            (stage / 'business-before.json').write_text(json.dumps(baseline, indent=2))
            original_fields = field_ids(args.database)
            (stage / 'field-ids-before.json').write_text(json.dumps(original_fields, indent=2))
            runtime = Path('/opt/odoo18')
            addon_paths = str(addons) + ',' + options['addons_path']
            init = ['-i', 'step_accounting_multicurrency_core', '-u', 'step_accounting_multicurrency']
            tags = '/step_accounting_multicurrency_core,/step_treasury_invoice_payment'
        else:
            runtime = root / 'community-runtime'
            assert (runtime / '.git').exists()
            remote = run('git', '-C', str(runtime), 'remote', 'get-url', 'origin', text=True, capture_output=True).stdout.strip()
            assert remote == 'https://github.com/odoo/odoo.git', 'Use official Community sources'
            revision = run('git', '-C', str(runtime), 'rev-parse', 'HEAD', text=True, capture_output=True).stdout.strip()
            (stage / 'runtime-revision.txt').write_text(revision)
            pure = stage / 'addons'; pure.mkdir()
            (pure / 'step_accounting_multicurrency_core').symlink_to(addons / 'step_accounting_multicurrency_core')
            addon_paths = str(pure) + ',' + str(runtime / 'addons')
            init = ['-i', 'step_accounting_multicurrency_core']
            tags = '/step_accounting_multicurrency_core'
        for path in [stage, *stage.rglob('*')]:
            if not path.is_symlink(): os.chown(path, identity.pw_uid, identity.pw_gid)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
        base = ['sudo', '-u', user, '/usr/bin/python3.10', str(runtime / 'odoo-bin')]
        opts = ['-c', str(conf), '-d', args.database, '--db-filter=^' + args.database + '$',
                '--addons-path=' + addon_paths, '--data-dir=' + str(data), '--load=base,web',
                '--http-interface=127.0.0.1', '--http-port=' + str(port), '--gevent-port=0',
                '--workers=0', '--max-cron-threads=0', '--without-demo=all']
        log = stage / 'tests.log'
        print('COMMUNITY_FOUNDATION_BEGIN ' + json.dumps({'mode': args.mode, 'database': args.database, 'log': str(log)}), flush=True)
        with log.open('w') as stream:
            result = subprocess.run(base + opts + init + ['--test-enable', '--test-tags=' + tags, '--stop-after-init'], stdout=stream, stderr=subprocess.STDOUT)
        text = log.read_text(errors='replace')
        print('\n'.join(line for line in text.splitlines() if 'tests.result' in line or ' ERROR ' in line or ' CRITICAL ' in line)[-6500:], flush=True)
        assert result.returncode == 0 and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests', text), 'Tests failed: ' + str(log)
        sql(args.database, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        if baseline is not None:
            after = snapshot(args.database); (stage / 'business-after.json').write_text(json.dumps(after, indent=2))
            assert after == baseline, 'Existing business records changed'
            assert field_ids(args.database) == original_fields, 'Field IDs changed'
        check = '''
import json
from odoo.tests import Form
from odoo.addons.step_accounting_multicurrency_core.hooks import CORE,LEGACY,VIEWS,FIELDS
try:
 for name in VIEWS: assert env.ref(CORE+'.'+name)==env.ref(LEGACY+'.'+name)
 for model,names in FIELDS.items():
  for name in names:
   key='field_'+model.replace('.','_')+'__'+name
   assert env.ref(CORE+'.'+key)==env.ref(LEGACY+'.'+key)
 Form(env['account.payment'],view='account.view_account_payment_form')
 ee=env['ir.module.module'].search_count([('state','=','installed'),('license','=','OEEL-1')])
 assert MODE!='community' or ee==0,'Enterprise modules installed in Community runtime'
 print('COMMUNITY_FOUNDATION_REGISTRY_OK '+json.dumps({'mode':MODE,'enterprise_installed':ee,'same_xmlids':True,'native_form':True,'writes':False}))
finally: env.cr.rollback()
'''
        result = subprocess.run(base + ['shell'] + opts + ['--no-http', '--log-level=critical'],
            input='MODE=' + repr(args.mode) + '\n' + check, text=True, capture_output=True)
        (stage / 'verify.log').write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and 'COMMUNITY_FOUNDATION_REGISTRY_OK' in result.stdout, result.stderr[-2500:]
        print(result.stdout, flush=True)
        if baseline is not None:
            assert snapshot(args.database) == baseline
        (stage / 'passed.json').write_text(json.dumps({'mode': args.mode, 'database': args.database,
            'tests_log': str(log), 'business_preserved': baseline is not None, 'writes_to_production': False}, indent=2))
        print('COMMUNITY_FOUNDATION_OK ' + args.mode, flush=True)


if __name__ == '__main__': main()
