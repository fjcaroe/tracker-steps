"""Retire legacy payroll through verified private clones, preserving histories.

QA is Desarrollo only. Production compatibility clones do not publish apps.
The vendor engine is copied privately from the current shared server source;
its hash is bound to the tested Git package and checked before installation.
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
from manage_management import run, query, digest, tree_hash, errors

HERE = Path(__file__).parent
VENDOR = Path('/opt/rrhh/l10n_cl_simpledigital_payroll')
MODULES = ('step_environment_policy', 'step_payroll_engine_transition', 'step_hr_contract_days', 'step_hr_previred', 'step_hr_previred_simpledigital', 'step_hr_contract_lifecycle', 'step_hr_contract_lifecycle_simpledigital', 'step_hr_remuneration_book', 'step_inventory_packing', 'step_packing_operations', 'step_producer_fruit_flow')
OPTIONAL = {'step_inventory_packing', 'step_packing_operations', 'step_producer_fruit_flow'}


def history(database):
    # Monetary detail, states and accounting links must survive verbatim.
    result = {}
    columns = {
        'hr_payslip': ('id','employee_id','contract_id','struct_id','date_from','date_to','state','move_id'),
        'hr_payslip_line': ('id','slip_id','salary_rule_id','code','amount','quantity','rate','total'),
        'hr_payslip_worked_days': ('id','payslip_id','work_entry_type_id','number_of_days','number_of_hours','amount'),
        'account_move': ('id','state','date','amount_total'),
        'account_move_line': ('id','move_id','account_id','debit','credit','balance','amount_currency'),
    }
    for table, fields in columns.items():
        present = json.loads(query(database, "SELECT json_agg(column_name) FROM information_schema.columns WHERE table_name='%s'" % table) or '[]')
        fields = [f for f in fields if f in present]
        if fields:
            result[table] = query(database, "SELECT json_build_object('rows',count(*),'digest',md5(COALESCE(string_agg(json_build_array(%s)::text,'|' ORDER BY id),''))) FROM %s" % (','.join(fields), table))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('qa','compatibility','deploy','verify'))
    p.add_argument('environment', choices=('development','demo-sys','steps','sys','cerro'))
    p.add_argument('archive', type=Path)
    p.add_argument('run_id')
    args = p.parse_args()
    assert os.geteuid() == 0 and re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
    registry = json.loads((HERE/'environments.json').read_text())
    assert args.action != 'qa' or args.environment == registry['policy']['qa']
    target = registry['environments'][args.environment]
    database, conf, service = target['database'], Path(target['config']), target['service']
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(conf)
    opts = cfg['options']
    assert opts.get('db_name') in (None, '', database) and int(opts['http_port']) == target['port']
    user = subprocess.check_output(['systemctl','show','--value','--property=User',service],text=True).strip()
    assert user and user != 'root'
    identity = pwd.getpwnam(user)
    stage = Path('/opt/steps-validation') / ('payroll_' + args.environment + '_' + args.run_id)
    stage.mkdir(parents=True,exist_ok=True,mode=0o750)
    staged = stage/'addons'
    staged.mkdir(exist_ok=True)
    with tarfile.open(args.archive) as archive:
        proof = json.loads(archive.extractfile('release.json').read())
        assert set(proof['versions']) == set(MODULES)
        seen = set()
        for member in archive.getmembers():
            path = Path(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts and member.name not in seen
            seen.add(member.name)
            if member.name != 'release.json':
                assert path.parts[0] in MODULES
                assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == proof['files'][member.name]
        assert seen == set(proof['files']) | {'release.json'}
        archive.extractall(staged)
    vendor_hash = tree_hash(VENDOR)
    shutil.copytree(VENDOR,staged/VENDOR.name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.bak*'))
    all_modules = [VENDOR.name,*[m for m in MODULES if m not in OPTIONAL]]
    addons = str(staged)+','+opts['addons_path']
    installed = json.loads(query(database,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'") or '{}')
    baseline = {'config':digest(conf),'vendor':vendor_hash,'modules':{}}
    for name in MODULES:
        if name in installed:
            assert tuple(map(int,proof['versions'][name].split('.'))) >= tuple(map(int,installed[name].split('.'))), 'Downgrade '+name
            source = next(Path(path.strip())/name for path in opts['addons_path'].split(',') if (Path(path.strip())/name/'__manifest__.py').exists())
            baseline['modules'][name]={'version':installed[name],'hash':tree_hash(source)}
    for path in [stage,*stage.rglob('*')]:
        os.chown(path,identity.pw_uid,identity.pw_gid)
    qa_db = 'PAYROLL_COMPAT_' + args.environment.upper().replace('-','_') + '_' + args.run_id
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    base = ['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin']
    options = ['-c',str(conf),'--no-http','--http-port=0','--workers=0','--max-cron-threads=0','--http-interface=127.0.0.1','--gevent-port=0','--without-demo=all']

    def execute(db, paths, data, label, install=(), update=(), shell=None, tests=False):
        command = base + (['shell'] if shell else []) + options + ['-d',db,'--db-filter=^'+db+'$','--addons-path='+paths,'--data-dir='+str(data)]
        log = stage/(label+'-'+stamp+'.log')
        if shell:
            result = run(*command,'--log-level=error',input='EXPECTED_DATABASE='+repr(db)+'\n'+shell,text=True,capture_output=True)
            log.write_text(result.stdout+result.stderr)
            assert 'Traceback' not in result.stderr, str(log)
            print(result.stdout[-1200:],flush=True)
        else:
            if install: command += ['-i',','.join(install)]
            if update: command += ['-u',','.join(update)]
            command += ['--stop-after-init','--logfile='+str(log)]
            if tests:
                with socket.socket() as listener:
                    listener.bind(('127.0.0.1',0))
                    private_port=listener.getsockname()[1]
                command=[v for v in command if not v.startswith('--http-port=')]
                command+=['--http-port='+str(private_port),'--test-enable','--test-tags',','.join('/'+name for name in MODULES)+',-step_book_perf']
                query(db,"UPDATE ir_config_parameter SET value='http://127.0.0.1:%s' WHERE key='web.base.url'"%private_port)
            result = subprocess.run(command)
            text = log.read_text(errors='replace')
            issues=errors(text)
            # New provider columns cannot be SQL-required on old drafts. The
            # adapter relaxes them later in the same graph and computation is
            # guarded until an administrator verifies the parameters.
            if label=='engine-install' and VENDOR.name in install:
                transitional=re.compile(r"odoo.schema: Table '(?:hr_contract|hr_employee)': unable to set NOT NULL on column '(?:analytic_account_id|health_institution|pension_option|has_gratification|is_retired_elderly|contract_type_id|hr_commune)'\s*$")
                issues=[line for line in issues if not transitional.search(line)]
            assert result.returncode == 0 and 'Modules loaded.' in text and not issues, 'Payroll failure: '+str(log)
            if tests:
                assert re.search(r"0 failed, 0 error\(s\) of [1-9][0-9]* tests when loading database '"+re.escape(db)+"'",text), 'Tests failed '+str(log)
        return log

    def transition(db, paths, data, tests=False):
        execute(db,paths,data,'archive-install',install=['step_payroll_engine_transition'])
        execute(db,paths,data,'retire',shell=(HERE/'transition_payroll.py').read_text())
        execute(db,paths,data,'native-report',shell=(HERE/'repair_native_payroll_report.py').read_text())
        existing = set(json.loads(query(db,"SELECT json_agg(name) FROM ir_module_module WHERE state='installed'") or '[]'))
        execute(db,paths,data,'engine-install',install=[n for n in all_modules if n not in existing],update=[n for n in MODULES if n in existing],tests=tests)
        execute(db,paths,data,'contract-mapping',shell=(HERE/'migrate_payroll_contracts.py').read_text())
        policy = "env['ir.config_parameter'].sudo().set_param('steps.environment.payroll_engine','l10n_cl_simpledigital_payroll')\n"
        policy += "env.cr.execute(\"UPDATE hr_contract SET step_payroll_migration_review=true WHERE state IN ('draft','open') AND (analytic_account_id IS NULL OR health_institution IS NULL OR pension_option IS NULL OR has_gratification IS NULL OR is_retired_elderly IS NULL)\")\n"
        if args.environment == 'demo-sys':
            roots = ['base.menu_administration','base.menu_management','hr_work_entry_contract_enterprise.menu_hr_payroll_root','hr.menu_hr_root','hr_attendance.menu_hr_attendance_root','hr_holidays.menu_hr_holidays_root','hr_expense.menu_hr_expense_root','contacts.menu_contacts','documents.menu_root','sign.menu_document','mail.menu_root_discuss','helpdesk.menu_helpdesk_root','step_support_assistant.menu_assistant_root']
            policy += "env['ir.config_parameter'].sudo().set_param('steps.environment.menu_root_xmlids',"+repr(json.dumps(roots))+")\n"
        execute(db,paths,data,'policy',shell=policy+"env['ir.ui.menu']._step_normalize_agriculture_menus()\nenv.cr.commit()\nprint('PAYROLL_POLICY_OK')\n")
        execute(db,paths,data,'verify',shell=(HERE/'verify_payroll.py').read_text())

    if args.action in ('qa','compatibility'):
        assert not query('postgres',"SELECT 1 FROM pg_database WHERE datname='%s'"%qa_db), 'Fresh run_id required'
        (stage/'baseline.json').write_text(json.dumps(baseline))
        before = history(database)
        (stage/'history_before.json').write_text(json.dumps(before))
        with (stage/'source.dump').open('wb') as stream: run('sudo','-u','postgres','pg_dump','-Fc',database,stdout=stream)
        run('sudo','-u','postgres','createdb','-O',opts['db_user'],qa_db)
        query(qa_db,'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
        with (stage/'source.dump').open('rb') as stream: run('sudo','-u','postgres','pg_restore','--no-owner','--no-comments','--role',opts['db_user'],'-d',qa_db,stdin=stream)
        query(qa_db,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        data = stage/'data'
        source = Path(opts['data_dir'])/'filestore'/database
        if source.exists():
            dest=data/'filestore'/qa_db
            dest.mkdir(parents=True,exist_ok=True)
            run('rsync','-a',str(source)+'/',str(dest)+'/')
        for path in [data,*data.rglob('*')] if data.exists() else []: os.chown(path,identity.pw_uid,identity.pw_gid)
        print('PAYROLL_CLONE_BEGIN '+json.dumps({'database':qa_db,'stage':str(stage)}),flush=True)
        transition(qa_db,addons,data,tests=True)
        assert history(qa_db)==before, 'Historical payroll/accounting changed'
        (stage/'passed.json').write_text(json.dumps({'commit':proof['commit'],'sha256':digest(args.archive),'vendor':vendor_hash,'history_preserved':True}))
        print('PAYROLL_CLONE_OK '+args.environment,flush=True)
        return
    passed = json.loads((stage/'passed.json').read_text())
    assert passed['commit']==proof['commit'] and passed['sha256']==digest(args.archive) and passed['vendor']==vendor_hash
    release=Path('/opt/steps-managed/payroll')/args.environment/proof['commit']
    if args.action == 'deploy':
        if args.environment != 'development':
            qa_release=Path('/opt/steps-managed/payroll/development')/proof['commit']/'release.json'
            assert qa_release.exists() and json.loads(qa_release.read_text())==proof, 'First deliver Desarrollo'
        assert json.loads((stage/'baseline.json').read_text())==baseline, 'Concurrent config/source change'
        with open('/run/lock/steps-environments.lock','a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            for path in Path('/proc').glob('[0-9]*/cmdline'):
                try: argv=path.read_bytes().decode(errors='replace').split('\x00')
                except OSError: continue
                for i,arg in enumerate(argv):
                    if Path(arg).name=='odoo-bin': assert not any(a in ('-u','-i','--update','--init') or a.startswith(('--update=','--init=')) for a in argv[i+1:]), 'Concurrent upgrade '+path.parent.name
            assert not release.exists()
            shutil.copytree(staged,release)
            backup=Path('/opt/steps_backups')/('payroll_'+args.environment+'_'+stamp)
            backup.mkdir(mode=0o700)
            shutil.copy2(conf,backup/'odoo.conf')
            run('systemctl','stop',service)
            try:
                with (backup/'database.dump').open('wb') as stream: run('sudo','-u','postgres','pg_dump','-Fc',database,stdout=stream)
                before=history(database)
                paths=str(release)+','+opts['addons_path']
                changed,count=re.subn(r'(?m)^\s*addons_path\s*=.*$','addons_path = '+paths,conf.read_text())
                assert count==1
                conf.write_text(changed)
                transition(database,paths,Path(opts['data_dir']))
                assert history(database)==before, 'Historical payroll/accounting changed'
                (backup/'release.json').write_text(json.dumps(passed))
                print('PAYROLL_DEPLOY_OK backup='+str(backup),flush=True)
            finally: run('systemctl','start',service)
    execute(database,str(release)+','+opts['addons_path'],Path(opts['data_dir']),'live-verify',shell=(HERE/'verify_payroll.py').read_text())
    for attempt in range(20):
        try:
            with urllib.request.urlopen(target['url']+'/web/login?db='+database,timeout=15) as response:
                assert response.status==200 and b'password' in response.read()
            break
        except Exception:
            if attempt==19: raise
            time.sleep(1)
    print('PAYROLL_VERIFY_OK '+args.environment,flush=True)


if __name__=='__main__': main()
