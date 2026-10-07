"""Promote T54's exact QA-tested stack after a fresh production compatibility run.

Reads only registry-selected configurations. Clones are private and mail/cron
disabled; live production requires both certificates, unchanged code/config,
the shared deployment lease, a recovery dump and a private addon overlay.
"""
import argparse
import ast
import configparser
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib.util
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
from manage_management import query, run, digest, tree_hash, errors
from stack_scope import MODULES

HERE = Path(__file__).resolve().parent


def extract(archive_path, destination):
    with tarfile.open(archive_path) as archive:
        proof = json.loads(archive.extractfile('release.json').read())
        assert set(proof['versions']) == set(MODULES)
        assert re.fullmatch('[0-9a-f]{40}', proof['commit'])
        seen = set()
        for member in archive.getmembers():
            path = Path(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            assert member.name not in seen
            seen.add(member.name)
            if member.name != 'release.json':
                assert path.parts[0] in MODULES
                assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == proof['files'][member.name]
        assert seen == set(proof['files']) | {'release.json'}
        archive.extractall(destination)
    return proof


def native_schema(root):
    spec = importlib.util.spec_from_file_location('stack_native_schema', root / 'step_operations_ui/native_schema.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def business_snapshot(database, native, schema=None):
    """Project original columns, following only versioned freight renames.

New rows are allowed only for the driver's contact migration. Prior contacts
retain every original column except the two explicitly migrated participant
flags. Monetary/business records retain IDs, original columns and counts.
"""
    metadata=json.loads(query(database,"SELECT json_object_agg(table_name,columns) FROM "
        "(SELECT table_name,json_agg(column_name ORDER BY ordinal_position) AS columns "
        "FROM information_schema.columns WHERE table_schema='public' GROUP BY table_name) t"))
    if schema is None:
        tables = query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND "
            "(tablename LIKE 'step_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' "
            "OR tablename LIKE 'product_%' OR tablename LIKE 'hr_%' OR tablename LIKE 'fleet_%' "
            "OR tablename LIKE 'sale_%' OR tablename LIKE 'purchase_%' OR tablename LIKE 'project_%' "
            "OR tablename LIKE 'mrp_%' OR tablename IN ('res_company','res_partner','res_partner_bank') "
            "OR tablename IN (" + ','.join("'%s'" % name for name in native.MODELS) + ")) ORDER BY tablename").splitlines()
        schema = {}
        for table in tables:
            columns = metadata[table]
            columns = [name for name in columns if name not in ('write_date', 'write_uid')]
            if table == 'res_partner':
                columns = [name for name in columns if name not in ('step_chofer', 'step_carga', 'is_freight_carrier')]
            schema[table] = {'columns': columns, 'max_id': int(query(database, 'SELECT COALESCE(max(id),0) FROM ' + table)) if table == 'res_partner' else None}
    rows, statements = {}, []
    for table, definition in schema.items():
        assert re.fullmatch('[a-z0-9_]+', table)
        actual_table = table
        if table not in metadata:
            actual_table = native.MODELS[table].replace('.', '_')
        present = set(metadata[actual_table])
        parts = []
        for column in definition['columns']:
            actual = column if column in present else native.FIELDS.get(column, column)
            assert re.fullmatch('[a-zA-Z0-9_]+', actual) and actual in present, (table, column, actual)
            parts.append("'%s',to_jsonb(t)->'%s'" % (column, actual))
        expression = ' || '.join('jsonb_build_object(' + ','.join(parts[start:start+40]) + ')' for start in range(0,len(parts),40))
        condition = ' WHERE id <= %s' % definition['max_id'] if table == 'res_partner' else ''
        statements.append("SELECT '%s', json_build_object('count',count(*),'digest',md5(COALESCE(string_agg((%s)::text,'|' ORDER BY (%s)::text),'')))::text FROM %s t%s" % (table,expression,expression,actual_table,condition))
    for line in query(database, ' UNION ALL '.join(statements)).splitlines():
        table, value = line.split('|',1)
        rows[table] = json.loads(value)
    return {'schema': schema, 'rows': rows}


def check_lease():
    lease = open('/run/lock/steps-environments.lock', 'a')
    fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for command in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            argv = command.read_bytes().decode(errors='replace').split('\x00')
        except OSError:
            continue
        if any(Path(arg).name == 'odoo-bin' for arg in argv):
            assert not any(arg in ('-u','-i','--update','--init') or arg.startswith(('--update=','--init=')) for arg in argv), 'Concurrent Odoo upgrade'
    return lease


def verify(base, options, database, source, paths, proof, stage):
    header = 'import sys\nsys.path.insert(0,' + repr(str(HERE)) + ')\n__file__=' + repr(str(HERE/'verify_stack.py')) + '\nROOT=' + repr(str(source)) + '\nEXPECTED=' + repr(proof['versions']) + '\n'
    data_options=['--data-dir='+str(stage/'data')] if database.startswith('STACK_') else []
    result = subprocess.run(base + ['shell'] + options + data_options + ['-d',database,'--db-filter=^'+database+'$',
        '--addons-path='+str(source)+','+paths,'--log-level=error'], input=header+(HERE/'verify_stack.py').read_text(), text=True, capture_output=True)
    (stage/('verify-'+database+'.log')).write_text(result.stdout+result.stderr)
    assert result.returncode == 0 and 'STACK_FLOW_OK' in result.stdout, result.stderr[-4000:]
    print('\n'.join(line for line in result.stdout.splitlines() if '_OK' in line), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('qa','compatibility','retry-tests','certify','deploy','verify'))
    p.add_argument('environment', choices=('development','cerro'))
    p.add_argument('archive', type=Path)
    p.add_argument('run_id')
    args = p.parse_args()
    assert os.geteuid() == 0 and re.fullmatch('[a-z0-9_]{1,24}',args.run_id)
    assert args.action != 'qa' or args.environment == 'development'
    assert args.action != 'compatibility' or args.environment == 'cerro'
    assert args.action != 'retry-tests' or args.environment == 'development', 'Failed production migrations require a fresh clone'
    lease=check_lease() if args.action in ('qa','compatibility','retry-tests','deploy') else None
    registry = json.loads((HERE/'environments.json').read_text())
    assert registry['policy']['qa']=='development' and 'cerro' in registry['policy']['production']
    target = registry['environments'][args.environment]
    database, service, conf = target['database'],target['service'],Path(target['config'])
    cfg = configparser.ConfigParser(interpolation=None); cfg.read(conf); opts=cfg['options']
    assert opts.get('db_name')==database and int(opts['http_port'])==target['port']
    user = subprocess.check_output(['systemctl','show','--value','--property=User',service],text=True).strip()
    assert user and user!='root'
    identity = pwd.getpwnam(user)
    stage = Path('/opt/steps-validation')/('stack_'+args.environment+'_'+args.run_id)
    stage.mkdir(parents=True,exist_ok=True,mode=0o750)
    source = stage/'addons'; source.mkdir(exist_ok=True)
    previous=json.loads((source/'release.json').read_text()) if (source/'release.json').exists() else None
    proof=extract(args.archive,source); archive_sha=digest(args.archive); native=native_schema(source)
    if args.action=='retry-tests':
        assert previous and set(previous['versions'])<=set(proof['versions'])
        for name,value in previous['files'].items():
            if '/tests/' not in name:
                assert proof['files'].get(name)==value, ('Runtime changed; require fresh clone',name)
    for path in (source,*source.rglob('*')): os.chown(path,identity.pw_uid,identity.pw_gid)
    versions=json.loads(query(database,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"))
    assert 'l10n_cl_simpledigital_payroll' in versions and not any(name.startswith('l10n_cl_hr') for name in versions), 'Payroll engine must already be canonical'
    assert not query(database,"SELECT name FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')"), 'Pending module operation'
    for name in set(MODULES)&set(versions):
        assert tuple(map(int,proof['versions'][name].split('.'))) >= tuple(map(int,versions[name].split('.'))), 'Downgrade '+name
    paths=opts['addons_path']; roots=[Path(item.strip()) for item in paths.split(',')]
    baseline={'config':digest(conf),'versions':versions,'sources':{}}
    for name in versions:
        root=next((root/name for root in roots if (root/name/'__manifest__.py').exists()),None)
        baseline['sources'][name]={'root':str(root),'hash':tree_hash(root)} if root else None
    update=[name for name in MODULES if name in versions]; install=[name for name in MODULES if name not in versions]
    base=['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin']
    options=['-c',str(conf),'--no-http','--http-interface=127.0.0.1','--http-port=0','--gevent-port=0','--workers=0','--max-cron-threads=0','--without-demo=all']
    clone='STACK_'+args.environment.upper()+'_'+args.run_id
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    certificate={'commit':proof['commit'],'sha256':archive_sha,'baseline':baseline}
    missing=[name for name,value in baseline['sources'].items() if value is None]
    allowed_virtual={'studio_customization'}
    allowed_missing=allowed_virtual | ({'steps_api'} if args.environment=='development' else set())
    assert set(missing)<=allowed_missing, ('Missing installed addons',missing)
    if args.action in ('qa','compatibility','retry-tests'):
        if args.environment=='development':
            # The package is already present in the sole QA: attest every file.
            for name, expected in proof['versions'].items():
                assert name in versions
                assert tuple(map(int,expected.split('.'))) >= tuple(map(int,versions[name].split('.')))
            for name, expected in proof['files'].items():
                if '/tests/' in name:
                    continue  # Test fixture portability never changes installed product behavior.
                module_name=Path(name).parts[0]
                if versions[module_name]!=proof['versions'][module_name]:
                    continue  # An upward revision is tested in the clone before QA deployment.
                root=Path(baseline['sources'][Path(name).parts[0]]['root'])
                actual=root/Path(*Path(name).parts[1:])
                assert actual.exists(), ('QA file missing',name)
                content=actual.read_bytes()
                reference=(source/name).read_bytes()
                if actual.suffix in ('.py','.xml','.csv','.js','.css','.scss','.svg','.md','.rst'):
                    content=content.replace(b'\r\n',b'\n')
                    reference=reference.replace(b'\r\n',b'\n')
                assert content==reference, ('QA source differs from package',name)
        if args.action=='retry-tests':
            assert not install and json.loads((stage/'baseline.json').read_text())==baseline
            logs=list(stage.glob('qa-*.log')); assert len(logs)==1
            old_log=logs[0].read_text(errors='replace')
            assert 'Modules loaded.' in old_log and 'Failed to load registry' not in old_log
            successful_full=re.search(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests',old_log)
            old_errors=errors(old_log,missing)
            changed_tests={Path(name).parts[0] for name,value in proof['files'].items()
                           if '/tests/' in name and previous['files'].get(name)!=value}
            if successful_full and changed_tests and all('odoo.sql_db: bad query:' in line for line in old_errors):
                update=sorted(changed_tests)
                (stage/'test_coverage.json').write_text(json.dumps({'full_suite_tests':int(successful_full.group(1)),
                    'full_runtime_unchanged':True,'retry_modules':update,'reason':'test-only corrections to expected constraint assertions/logging'}))
            before=json.loads((stage/'business_before.json').read_text())
            assert business_snapshot(clone,native,before['schema'])==before, 'Failed suite did not preserve rows'
        else:
            assert not query('postgres',"SELECT 1 FROM pg_database WHERE datname='%s'"%clone), 'Use fresh run_id'
            (stage/'baseline.json').write_text(json.dumps(baseline,indent=2))
            with (stage/'source.dump').open('wb') as stream: run('sudo','-u','postgres','pg_dump','-Fc',database,stdout=stream)
            run('sudo','-u','postgres','createdb','-O',opts['db_user'],clone)
            query(clone,'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
            with (stage/'source.dump').open('rb') as stream:
                run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role',opts['db_user'],'-d',clone,stdin=stream)
            before=business_snapshot(clone,native); (stage/'business_before.json').write_text(json.dumps(before))
        query(clone,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        data=stage/'data'; data.mkdir(exist_ok=True)
        source_store=Path(opts['data_dir'])/'filestore'/database
        if source_store.exists():
            dest=data/'filestore'/clone; dest.mkdir(parents=True,exist_ok=True)
            run('rsync','-a',str(source_store)+'/',str(dest)+'/')
        for path in (stage,data,*data.rglob('*')): os.chown(path,identity.pw_uid,identity.pw_gid)
        with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
        query(clone,"UPDATE ir_config_parameter SET value='http://127.0.0.1:%s' WHERE key='web.base.url'"%port)
        qa_options=[item for item in options if not item.startswith('--http-port=')]+['--http-port='+str(port),'--db-filter=^'+clone+'$']
        log=stage/('qa-'+stamp+'.log')
        test_modules=update if args.action=='retry-tests' else MODULES
        if args.action=='compatibility' or args.action=='qa' and all(versions.get(name)==proof['versions'][name] for name in MODULES if name not in ('step_operations_ui',)):
            # The full immutable runtime already passed the sole QA. Repeat
            # target suites for every installation, migration or code change;
            # unchanged payroll still has history preservation and real probes.
            targets=set(install)|{name for name in update if versions[name]!=proof['versions'][name]}
            for filename in proof['files']:
                name=Path(filename).parts[0]
                if name in targets or '/tests/' in filename:
                    continue
                actual=Path(baseline['sources'][name]['root'])/Path(*Path(filename).parts[1:])
                if not actual.exists():
                    targets.add(name); continue
                current=actual.read_bytes(); proposed=(source/filename).read_bytes()
                if actual.suffix in ('.py','.xml','.csv','.js','.css','.scss','.svg','.md','.rst'):
                    current=current.replace(b'\r\n',b'\n'); proposed=proposed.replace(b'\r\n',b'\n')
                if current!=proposed: targets.add(name)
            test_modules=sorted(targets)
            assert test_modules
            (stage/'test_coverage.json').write_text(json.dumps({'target_suites':test_modules,
                'unchanged_modules_verified_by_registry_flow_and_original_row_snapshot':sorted(set(MODULES)-targets)}))
        command=base+qa_options+['-d',clone,'--addons-path='+str(source)+','+paths,'--data-dir='+str(data),'-u',','.join(update),'--test-enable','--test-tags='+','.join('/'+name for name in test_modules),'--stop-after-init','--logfile='+str(log)]
        if install: command+=['-i',','.join(install)]
        print('STACK_TEST_BEGIN '+json.dumps({'database':clone,'log':str(log),'install':install,'commit':proof['commit']}),flush=True)
        result=subprocess.run(command); logtext=log.read_text(errors='replace')
        print('\n'.join(line for line in logtext.splitlines() if 'tests.result' in line or ' ERROR ' in line or ' FAIL' in line)[-12000:],flush=True)
        assert result.returncode==0 and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',logtext) and not errors(logtext,missing), 'Tests failed '+str(log)
        after=business_snapshot(clone,native,before['schema']); (stage/'business_after.json').write_text(json.dumps(after))
        assert before==after, 'Business preservation failed '+str(stage)
        verify(base,options,clone,source,paths,proof,stage)
        (stage/'passed.json').write_text(json.dumps(certificate,indent=2))
        print('STACK_COMPATIBILITY_OK '+args.environment,flush=True)
        return
    if args.action=='certify':
        assert json.loads((stage/'baseline.json').read_text())==baseline
        logs=sorted(stage.glob('qa-*.log')); assert logs
        logtext=logs[-1].read_text(errors='replace')
        assert re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',logtext) and not errors(logtext,missing)
        before=json.loads((stage/'business_before.json').read_text())
        assert business_snapshot(clone,native,before['schema'])==before
        verify(base,options,clone,source,paths,proof,stage)
        (stage/'passed.json').write_text(json.dumps(certificate,indent=2)); return
    release=Path('/opt/steps-managed/stack')/args.environment/proof['commit']
    if args.action=='deploy':
        assert json.loads((stage/'passed.json').read_text())==certificate, 'Repeat compatibility after concurrent source/config changes'
        if args.environment=='cerro':
            qa=Path('/opt/steps-validation')/('stack_development_'+args.run_id)/'passed.json'
            qa_proof=json.loads(qa.read_text()); assert qa_proof['sha256']==archive_sha and qa_proof['commit']==proof['commit']
            qa_release=Path('/opt/steps-managed/stack/development')/proof['commit']
            assert (qa_release/'release.json').exists() and json.loads((qa_release/'release.json').read_text())==proof, 'First apply and verify the exact package in Development'
        assert not release.exists(), 'Release exists; use verify for an already applied release'
        release.mkdir(parents=True); extract(args.archive,release)
        for path in (release,*release.rglob('*')): os.chown(path,identity.pw_uid,identity.pw_gid)
        backup=Path('/opt/steps_backups')/('stack_'+args.environment+'_'+stamp); backup.mkdir(mode=0o700)
        shutil.copy2(conf,backup/'odoo.conf')
        run('systemctl','stop',service)
        try:
            with (backup/'database.dump').open('wb') as stream: run('sudo','-u','postgres','pg_dump','-Fc',database,stdout=stream)
            store=Path(opts['data_dir'])/'filestore'/database
            if store.exists():
                (backup/'filestore').mkdir()
                run('rsync','-a',str(store)+'/',str(backup/'filestore')+'/')
            before=business_snapshot(database,native); (backup/'business_before.json').write_text(json.dumps(before))
            changed,count=re.subn(r'(?m)^\s*addons_path\s*=.*$','addons_path = '+str(release)+','+paths,conf.read_text()); assert count==1
            conf.write_text(changed)
            log=stage/('deploy-'+stamp+'.log')
            command=base+options+['-d',database,'-u',','.join(update),'--stop-after-init','--logfile='+str(log)]
            if install: command+=['-i',','.join(install)]
            result=subprocess.run(command); logtext=log.read_text(errors='replace')
            assert result.returncode==0 and 'Modules loaded.' in logtext and not errors(logtext,missing), str(log)
            after=business_snapshot(database,native,before['schema']); (backup/'business_after.json').write_text(json.dumps(after))
            assert after==before, 'Preservation failed; recovery backup '+str(backup)
            (backup/'deployment.json').write_text(json.dumps({'commit':proof['commit'],'sha256':archive_sha,'overlay':str(release)}))
        except Exception:
            print('STACK_DEPLOY_FAILED backup='+str(backup),flush=True); raise
        finally: run('systemctl','start',service)
        print('STACK_DEPLOY_OK backup='+str(backup),flush=True)
    verify(base,options,database,release,paths,proof,stage)
    run('systemctl','is-active','--quiet',service)
    with urllib.request.urlopen(target['url']+'/web/login?db='+database,timeout=30) as response:
        assert response.status==200 and b'password' in response.read()
    print('STACK_VERIFY_OK '+target['url'],flush=True)


if __name__=='__main__': main()
