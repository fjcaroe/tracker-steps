"""Install the exact clone-tested Steps App portal on registry-selected Desarrollo.

Run as root on odoo-new. No production target, mail, credentials changes or shared
addon replacement. QA uses a fresh private clone with mail/cron disabled.
"""
import argparse
import ast
import configparser
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path

MODULES = ('step_mobile_portal', 'step_mobile_portal_colaciones', 'step_mobile_portal_mobilization', 'step_mobile_portal_tracker')
DOMAINS = ('step_colaciones', 'step_mobilization')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def query(db, sql):
    return subprocess.check_output(['sudo', '-u', 'postgres', 'psql', '-d', db, '-Atc', sql], text=True).strip()

def installed(db):
    sql = "SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"
    return json.loads(query(db, sql))

def snapshot(db, schema=None):
    # Preserve original business columns and IDs. The portal adds metadata/UUIDs,
    # which must not change existing master or operation values.
    if schema is None:
        tables = query(db, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename IN ('res_company','res_partner','hr_employee','fleet_vehicle','product_template','product_product','hr_route','hr_route_line') OR tablename LIKE 'step_colacion%' OR tablename LIKE 'step_movi%') ORDER BY tablename").splitlines()
        schema = {t: query(db, "SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='%s' AND column_name NOT IN ('write_date','write_uid') ORDER BY ordinal_position" % t).splitlines() for t in tables}
    result = {}
    for table, columns in schema.items():
        assert re.fullmatch('[a-z0-9_]+', table) and all(re.fullmatch('[a-z0-9_]+', c) for c in columns)
        projection = ','.join('"%s"' % c for c in columns)
        row = query(db, "SELECT json_build_object('count',count(*),'digest',md5(COALESCE(string_agg(row_to_json(t)::text,'|' ORDER BY row_to_json(t)::text),''))) FROM (SELECT %s FROM %s) t" % (projection, table))
        result[table] = json.loads(row)
    return {'schema': schema, 'rows': result}

def lease():
    handle = open('/run/lock/steps-environments.lock', 'a')
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for file in Path('/proc').glob('[0-9]*/cmdline'):
        try: args = file.read_bytes().decode(errors='replace').split('\0')
        except OSError: continue
        if any(Path(a).name == 'odoo-bin' for a in args):
            assert not any(a in ('-u','-i','--init','--update') or a.startswith(('--init=','--update=')) for a in args), 'Concurrent Odoo upgrade'
    return handle

def extract(archive, source):
    with tarfile.open(archive) as tar:
        proof = json.loads(tar.extractfile('release.json').read())
        assert set(proof['versions']) == set(MODULES) and re.fullmatch('[a-f0-9]{40}', proof['commit'])
        names = set()
        for entry in tar.getmembers():
            path = Path(entry.name)
            assert entry.isfile() and not path.is_absolute() and '..' not in path.parts and entry.name not in names
            names.add(entry.name)
            if entry.name != 'release.json':
                assert path.parts[0] in MODULES and hashlib.sha256(tar.extractfile(entry).read()).hexdigest() == proof['files'][entry.name]
        assert names == set(proof['files']) | {'release.json'}
        source.mkdir(exist_ok=True)
        tar.extractall(source)
    return proof

def odoo(conf, user, database, paths, stage, *extra, script=None, name='odoo'):
    command = ['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin']
    if script is not None: command.append('shell')
    command += ['-c',str(conf),'-d',database,'--db-filter=^'+database+'$', '--addons-path='+paths,
                '--no-http','--workers=0','--max-cron-threads=0','--without-demo=all', '--log-level=info', '--logfile='+str(stage/(name+'.log')), *extra]
    with (stage/(name+'.stdout')).open('w') as log:
        result = subprocess.run(command, input=script, text=True, stdout=log, stderr=subprocess.STDOUT)
    assert result.returncode == 0, 'Odoo failed; inspect private '+str(stage/(name+'.log'))
    return (stage/(name+'.log')).read_text(errors='replace') + '\n' + (stage/(name+'.stdout')).read_text(errors='replace')

def verify(conf, user, db, paths, stage, proof):
    code = 'EXPECTED=' + repr(proof['versions']) + '\n' + """
for name, version in EXPECTED.items():
    module = env['ir.module.module'].search([('name','=',name)])
    assert module.state == 'installed' and module.latest_version == version, (name, module.state, module.latest_version)
admin = env.ref('base.user_admin')
assert admin.has_group('step_mobile_portal.group_step_app_manager')
menu = env.ref('step_mobile_portal.menu_step_app_root')
assert menu.id in env['ir.ui.menu'].with_user(admin)._visible_menu_ids()
for model in ('step.app.person','step.app.membership','step.app.invitation','step.app.device'):
    view = env[model].with_user(admin).get_view(view_type='form')
    assert '<form' in view['arch']
assert env['step.app.api'].health()['api_version'] == 1
print('PORTAL_VERSION_MENU_FORMS_OK')
env.cr.rollback()
"""
    log = odoo(conf, user, db, paths, stage, script=code, name='verify-'+db)
    assert 'PORTAL_VERSION_MENU_FORMS_OK' in log

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('qa','deploy','verify'))
    p.add_argument('archive', type=Path); p.add_argument('run_id')
    p.add_argument('--registry', required=True, type=Path)
    args = p.parse_args()
    assert os.geteuid() == 0 and re.fullmatch('[a-z0-9_]{1,32}', args.run_id)
    registry = json.loads(args.registry.read_text())
    assert registry['policy']['qa'] == 'development'
    target = registry['environments']['development']
    db, service, conf = target['database'], target['service'], Path(target['config'])
    assert db == 'LAB_TAREAS' and target['url'] == 'https://desarrollo.stepsapp.cl' and target['port'] == 8075
    cfg = configparser.ConfigParser(interpolation=None); cfg.read(conf); opts = cfg['options']
    assert opts['db_name'] == db and int(opts['http_port']) == target['port']
    user = subprocess.check_output(['systemctl','show','--value','--property=User',service],text=True).strip()
    assert user == 'odoo'
    held = lease()
    stage = Path('/opt/steps-validation')/('mobile_'+args.run_id)
    stage.mkdir(exist_ok=True, parents=True, mode=0o750)
    source = stage/'addons'
    proof = extract(args.archive, source)
    paths = str(source)+','+opts['addons_path']
    archive_hash = digest(args.archive)
    baseline_path = stage/'baseline.json'; certificate = stage/'qa.json'
    if args.action == 'qa':
        assert not baseline_path.exists(), 'Use a fresh run ID for QA'
        versions = installed(db)
        for m,v in proof['versions'].items():
            if m in versions: assert tuple(map(int,v.split('.'))) >= tuple(map(int,versions[m].split('.'))), 'Module downgrade'
        baseline = {'config_sha256':digest(conf), 'installed':versions, 'archive_sha256':archive_hash}
        baseline_path.write_text(json.dumps(baseline))
        clone = 'test_steps_app_'+args.run_id
        assert not query('postgres', "SELECT 1 FROM pg_database WHERE datname='%s'" % clone), 'Fresh clone required'
        with (stage/'source.dump').open('wb') as stream: run(['sudo','-u','postgres','pg_dump','-Fc',db],stdout=stream)
        run(['sudo','-u','postgres','createdb','-O',opts['db_user'],clone])
        query(clone, 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
        with (stage/'source.dump').open('rb') as stream:
            run(['sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role',opts['db_user'],'-d',clone],stdin=stream)
        before = snapshot(clone)
        query(clone, "UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;")
        if query(clone, "SELECT to_regclass('public.base_automation') IS NOT NULL") == 't': query(clone, 'UPDATE base_automation SET active=false;')
        data = stage/'data'; data.mkdir(exist_ok=True)
        store = Path(opts['data_dir'])/'filestore'/db
        if store.exists():
            dest = data/'filestore'/clone; dest.mkdir(parents=True,exist_ok=True)
            run(['rsync','-a',str(store)+'/',str(dest)+'/'])
        copy = configparser.ConfigParser(interpolation=None); copy.read(conf)
        copy['options'].update({'db_name':clone,'dbfilter':'^'+clone+'$','data_dir':str(data),'http_interface':'127.0.0.1','http_port':'0','gevent_port':'0','workers':'0','max_cron_threads':'0','list_db':'False'})
        clone_conf = stage/'clone.conf'
        with clone_conf.open('w') as out: copy.write(out)
        clone_conf.chmod(0o600)
        run(['chown','-R',user+':'+user,str(stage)])
        query(clone, "INSERT INTO ir_config_parameter (key,value) VALUES ('step_app.send_mail','0') ON CONFLICT (key) DO UPDATE SET value='0'")
        missing = [m for m in MODULES if m not in versions]
        extra = (['-i',','.join(missing)] if missing else []) + (['-u',','.join(m for m in MODULES if m not in missing)] if len(missing)<len(MODULES) else [])
        log = odoo(clone_conf,user,clone,paths,stage,*extra,'--test-enable','--test-tags','/step_mobile_portal,/step_mobile_portal_colaciones,/step_mobile_portal_mobilization','--stop-after-init',name='qa')
        summaries = re.findall(r'(\d+) failed, (\d+) error\(s\) of (\d+) tests', log)
        assert summaries and all(a == '0' and b == '0' for a,b,n in summaries) and max(int(n) for a,b,n in summaries) >= 59, 'Odoo functional tests did not pass'
        assert snapshot(clone,before['schema']) == before, 'Existing business records changed'
        verify(clone_conf,user,clone,paths,stage,proof)
        certificate.write_text(json.dumps({'commit':proof['commit'],'archive_sha256':archive_hash,'database':clone,'preserved_tables':len(before['rows']),'test_summary':[line for line in log.splitlines() if 'failed, ' in line]}))
        print('PORTAL_CLONE_QA_OK', json.dumps(json.loads(certificate.read_text())))
    elif args.action == 'deploy':
        passed = json.loads(certificate.read_text()); baseline = json.loads(baseline_path.read_text())
        assert passed['archive_sha256'] == archive_hash and passed['commit'] == proof['commit']
        assert baseline['config_sha256'] == digest(conf) and baseline['installed'] == installed(db), 'Destination changed since QA; repeat with a fresh clone'
        release = Path('/opt/steps-managed/mobile/development')/proof['commit']
        assert not release.exists(), 'Release already exists'
        release.mkdir(parents=True)
        run(['rsync','-a',str(source)+'/',str(release)+'/']); run(['chown','-R',user+':'+user,str(release)])
        before = snapshot(db)
        run(['systemctl','stop',service])
        try:
            with (stage/'pre-deploy.dump').open('wb') as stream: run(['sudo','-u','postgres','pg_dump','-Fc',db],stdout=stream)
            (stage/'pre-deploy.conf').write_bytes(conf.read_bytes()); (stage/'pre-deploy.conf').chmod(0o600)
            cfg['options']['addons_path'] = str(release)+','+opts['addons_path']
            with conf.open('w') as out: cfg.write(out)
            live_paths = cfg['options']['addons_path']
            missing = [m for m in MODULES if m not in baseline['installed']]
            extra = (['-i',','.join(missing)] if missing else []) + (['-u',','.join(m for m in MODULES if m not in missing)] if len(missing)<len(MODULES) else [])
            odoo(conf,user,db,live_paths,stage,*extra,'--stop-after-init',name='deploy')
            assert snapshot(db,before['schema']) == before, 'Existing business records changed after deployment'
            verify(conf,user,db,live_paths,stage,proof)
        finally: run(['systemctl','start',service])
        print('PORTAL_DEVELOPMENT_DEPLOY_OK', proof['commit'])
    else:
        verify(conf,user,db,opts['addons_path'],stage,proof)
        print('PORTAL_LIVE_VERIFY_OK')

if __name__ == '__main__': main()
