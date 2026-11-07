"""Certify and enable native greenhouse apps in the standalone ECOPLANTAS demo."""
import argparse
import configparser
from contextlib import contextmanager
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
import urllib.request

from provision_ecoplantas_demo import ROOT, DB, USER, CONF, SERVICE, PRIVATE_BIN, query, tree_hash, private_json

APPS=('mrp','mrp_workorder','quality_control','quality_mrp','quality_mrp_workorder','maintenance','mrp_maintenance','project')
TABLES=('res_partner','product_template','product_product','purchase_order','purchase_order_line',
        'sale_order','sale_order_line','stock_picking','stock_move','stock_move_line','stock_quant',
        'account_move','account_move_line','stock_lot','mrp_production','project_project','project_task','maintenance_request')
SCENARIO=Path(__file__).with_name('ecoplantas_greenhouse_scenario.py')


def run(*args,**kwargs):return subprocess.run(args,check=True,**kwargs)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def installed(db):
    return json.loads(query(db,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"))


def baseline():
    prepared=json.loads((ROOT/'prepared.json').read_text())
    assert tree_hash(ROOT/'runtime')==prepared['core_sha256']
    files={name:tree_hash(ROOT/'addons'/name) for name in APPS}
    assert all(value==prepared['modules'][name]['sha256'] for name,value in files.items())
    assert query(DB,"SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")=='0'
    return {'config':sha(CONF),'prepared':sha(ROOT/'prepared.json'),'apps':files,'installed':installed(DB),
            'scenario':sha(SCENARIO),'operation':sha(Path(__file__))}


def snapshot(db,previous=None):
    if previous is None:
        previous={}
        for table in TABLES:
            cols=query(db,"SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='"+table+"' ORDER BY ordinal_position").splitlines()
            if cols:
                previous[table]={'columns':cols,'max_id':int(query(db,'SELECT coalesce(max(id),0) FROM '+table))}
    result={}
    for table,data in previous.items():
        assert table in TABLES and all(re.fullmatch(r'[a-zA-Z0-9_]+',col) for col in data['columns'])
        cols=','.join('"'+col+'"' for col in data['columns'])
        sql="SELECT count(*)::text||':'||md5(coalesce(string_agg(to_jsonb(t)::text,'' ORDER BY t.id),'')) FROM (SELECT %s FROM %s WHERE id<=%d) t"%(cols,table,data['max_id'])
        result[table]=dict(data,rows=query(db,sql))
    return result


def credentials(db):
    return query(db,"SELECT md5(string_agg(id::text||coalesce(password,''),'' ORDER BY id)) FROM res_users")


def deliveries(db):
    return query(db,"SELECT (SELECT count(*) FROM mail_mail WHERE state IN ('outgoing','sent'))::text||':'||(SELECT count(*) FROM mail_notification)::text")


@contextmanager
def copy_access(db,stage):
    hba=Path(query('postgres','SHOW hba_file'));before=hba.read_bytes()
    block=('# STEPS ECOPLANTAS GREENHOUSE '+db+'\nhost "'+db+'" '+USER+' 127.0.0.1/32 md5\n').encode()
    assert block not in before
    backup=stage/'pg_hba_before.conf';backup.write_bytes(before);backup.chmod(0o600)
    try:
        hba.write_bytes(block+before)
        assert query('postgres','SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL')=='0'
        assert query('postgres','SELECT pg_reload_conf()')=='t'
        yield
    finally:
        current=hba.read_bytes();assert current.count(block)==1
        hba.write_bytes(current.replace(block,b'',1));assert query('postgres','SELECT pg_reload_conf()')=='t'


def odoo(db,conf,stage,action,script=None,arguments=()):
    command=['sudo','-u',USER,'/usr/bin/python3.10',str(PRIVATE_BIN)]
    if script is not None:command.append('shell')
    command+=['-c',str(conf),'-d',db,'--db-filter=^'+db+'$','--no-http','--max-cron-threads=0','--workers=0','--without-demo=all']
    command+=arguments
    result=subprocess.run(command,input=script,text=True,capture_output=True)
    log=stage/(action+'.log');log.write_text(result.stdout+'\n'+result.stderr);log.chmod(0o600)
    assert result.returncode==0 and 'Some modules have inconsistent states' not in result.stderr,str(log)
    return result.stdout


def configure(db,conf,stage,user,active_crons,*,create=False,exercise=False):
    action='exercise' if exercise else 'configure' if create else 'verify'
    script=SCENARIO.read_text(encoding='utf-8')
    script+='\nresult=scenario(env,%d,create=%r,exercise=%r)\n'%(user,create,exercise)
    if create:
        script+="env['ir.cron'].search([('active','=',True),('id','not in',%r)]).write({'active':False})\n"%active_crons
        script+="assert set(env['ir.cron'].search([('active','=',True)]).ids)==set(%r)\n"%active_crons
    script+="assert not env['ir.mail_server'].search_count([('active','=',True)])\n"
    script+='env.cr.commit()\n' if create else 'env.cr.rollback()\n'
    script+="import json\nprint('GREENHOUSE_SCENARIO_OK '+json.dumps(result))\n"
    text=odoo(db,conf,stage,action,script)
    line,=[line for line in text.splitlines() if line.startswith('GREENHOUSE_SCENARIO_OK ')]
    return json.loads(line.split(' ',1)[1])


def install(db,conf,stage):
    missing=[name for name in APPS if name not in installed(db)]
    if missing:odoo(db,conf,stage,'install',arguments=['-i',','.join(missing),'--stop-after-init'])
    versions=installed(db)
    assert set(APPS)<=set(versions)
    assert query(db,"SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")=='0'
    return versions


def backup(db,path):
    path.mkdir(mode=0o700)
    with (path/'database.dump').open('wb') as stream:run('sudo','-u','postgres','pg_dump','-Fc',db,stdout=stream)
    shutil.copy2(CONF,path/'odoo.conf');(path/'odoo.conf').chmod(0o600)
    store=ROOT/'data/filestore'/db
    if store.exists():run('rsync','-a',str(store)+'/',str(path/'filestore')+'/')


def qa(stage,db,user):
    identity=pwd.getpwnam(USER);stage.mkdir(mode=0o750);os.chown(stage,0,identity.pw_gid)
    source=baseline();saved=stage/'source';backup(DB,saved)
    cfg=configparser.ConfigParser(interpolation=None);cfg.read(CONF)
    data=stage/'data';data.mkdir(mode=0o750);os.chown(data,identity.pw_uid,identity.pw_gid)
    cfg['options'].update({'db_name':db,'dbfilter':'^'+db+'$','data_dir':str(data),'max_cron_threads':'0'})
    conf=stage/'copy.conf'
    with conf.open('w') as stream:cfg.write(stream)
    conf.chmod(0o640);os.chown(conf,0,identity.pw_gid)
    assert not query('postgres',"SELECT 1 FROM pg_database WHERE datname='"+db+"'")
    with copy_access(db,stage):
        run('sudo','-u','postgres','createdb','-O',USER,db)
        query(db,'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
        with (saved/'database.dump').open('rb') as stream:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role',USER,'-d',db,stdin=stream)
        if (saved/'filestore').exists():
            store=data/'filestore'/db;store.mkdir(parents=True)
            run('rsync','-a',str(saved/'filestore')+'/',str(store)+'/')
            for path in (data,*data.rglob('*')):os.chown(path,identity.pw_uid,identity.pw_gid)
        before=snapshot(db);passwords=credentials(db);mail=deliveries(db)
        query(db,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        odoo(db,conf,stage,'neutralize',"env['ir.config_parameter'].init(force=True)\nenv.cr.commit()\n")
        assert query(db,"SELECT value FROM ir_config_parameter WHERE key='database.uuid'")!=query(DB,"SELECT value FROM ir_config_parameter WHERE key='database.uuid'")
        versions=install(db,conf,stage)
        configure(db,conf,stage,user,[],create=True)
        assert snapshot(db,before)==before and credentials(db)==passwords and deliveries(db)==mail
        flow=configure(db,conf,stage,user,[],exercise=True)
        assert flow['finished_units']==100 and flow['quality_passed'] and flow['traceable_input_output']
        configure(db,conf,stage,user,[])
    private_json(stage/'qa-passed.json',{'baseline':source,'versions':versions,'flow':flow,'user_id':user})
    print('ECOPLANTAS_GREENHOUSE_QA_OK '+json.dumps(flow),flush=True)


def deploy(stage,user):
    proof=json.loads((stage/'qa-passed.json').read_text())
    assert proof['user_id']==user and proof['baseline']==baseline()
    assert proof['flow']['copy_flow'] and proof['flow']['traceable_input_output']
    backup_path=ROOT/('greenhouse-backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    run('systemctl','stop',SERVICE)
    try:
        backup(DB,backup_path);before=snapshot(DB);passwords=credentials(DB);mail=deliveries(DB)
        active=[int(value) for value in query(DB,'SELECT id FROM ir_cron WHERE active ORDER BY id').splitlines()]
        assert install(DB,CONF,backup_path)==proof['versions']
        native=configure(DB,CONF,backup_path,user,active,create=True)
        assert snapshot(DB,before)==before and credentials(DB)==passwords and deliveries(DB)==mail
    finally:run('systemctl','start',SERVICE)
    run('systemctl','is-active','--quiet',SERVICE)
    with urllib.request.urlopen('https://ecoplantas.stepsapp.cl/web/login?db=ECOPLANTAS',timeout=60) as response:
        assert response.status==200 and b'password' in response.read()
    native.update(backup=str(backup_path),credentials_preserved=True,existing_business_preserved=True)
    private_json(stage/'deployed.json',native)
    print('ECOPLANTAS_GREENHOUSE_DEPLOYED '+json.dumps(native),flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('qa','deploy'))
    parser.add_argument('run_id');args=parser.parse_args()
    assert os.geteuid()==0 and re.fullmatch('[a-z0-9_]{1,16}',args.run_id)
    assert (ROOT/'published.json').exists()
    access=json.loads((ROOT/'review-access-verified.json').read_text())
    assert access['https_authenticated'] and access['live']['internal_user']
    user=access['live']['user_id'];stage=Path('/opt/steps-validation/ecoplantas-greenhouse_'+args.run_id)
    with open('/run/lock/steps-environments.lock','a') as lease:
        print('ECOPLANTAS_GREENHOUSE_WAITING_LEASE',flush=True);fcntl.flock(lease,fcntl.LOCK_EX)
        if args.action=='qa':qa(stage,'ECOPLANTAS_GH_QA_'+args.run_id,user)
        else:deploy(stage,user)


if __name__=='__main__':main()
