"""Clone, test, preserve and publish the exact WhatsApp addon. No secrets printed."""
import argparse
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

HERE=Path(__file__).parent


def run(*cmd,**kw):return subprocess.run(cmd,check=True,**kw)
def sql(db,query):return subprocess.check_output(['sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d',db,'-Atc',query],text=True).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def snapshots(db, original=None):
    output={}
    for table in ['helpdesk_ticket','mail_message','ir_attachment']:
        if not sql(db,"SELECT to_regclass('%s')"%table):continue
        maximum=original.get(table,{}).get('max_id') if original is not None else None
        maximum=maximum if maximum is not None else int(sql(db,'SELECT COALESCE(max(id),0) FROM '+table))
        digest=sql(db,"SELECT md5(COALESCE(string_agg((to_jsonb(t)-ARRAY['step_wa_conversation_id','step_wa_previous_ticket_id','step_wa_inbound'])::text,'|' ORDER BY id),'')) FROM %s t WHERE id<=%s"%(table,maximum))
        output[table]={'max_id':maximum,'digest':digest}
    return output


def unpack(package,destination):
    with tarfile.open(package) as archive:
        proof=json.loads(archive.extractfile('release.json').read())
        assert proof['module']=='step_helpdesk_whatsapp' and re.fullmatch('[a-f0-9]{40}',proof['commit'])
        seen=set()
        for item in archive.getmembers():
            path=Path(item.name)
            assert item.isfile() and not path.is_absolute() and '..' not in path.parts and item.name not in seen
            assert item.name=='release.json' or path.parts[0]=='step_helpdesk_whatsapp'
            seen.add(item.name)
            if item.name!='release.json':assert hashlib.sha256(archive.extractfile(item).read()).hexdigest()==proof['files'][item.name]
        assert seen==set(proof['files'])|{'release.json'}
        archive.extractall(destination)
    return proof


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['qa','compatibility','diagnose','deploy','verify'])
    p.add_argument('environment',choices=['development','steps'])
    p.add_argument('package',type=Path);p.add_argument('run_id');a=p.parse_args()
    assert os.geteuid()==0 and re.fullmatch('[a-z0-9_]{1,20}',a.run_id)
    assert a.action!='qa' or a.environment=='development'
    target=json.loads((HERE/'environments.json').read_text())['environments'][a.environment]
    conf=Path(target['config']);c=configparser.ConfigParser(interpolation=None);c.read(conf);opts=c['options']
    db=target['database'];assert opts['db_name']==db
    user=subprocess.check_output(['systemctl','show','--value','--property=User',target['service']],text=True).strip()
    identity=pwd.getpwnam(user)
    stage=Path('/opt/steps-validation')/('whatsapp_'+a.environment+'_'+a.run_id)
    stage.mkdir(parents=True,exist_ok=True,mode=0o750)
    addon=stage/'addons';addon.mkdir(exist_ok=True)
    proof=unpack(a.package,addon);package_sha=sha(a.package)
    for file in [stage,addon,*addon.rglob('*')]:os.chown(file,identity.pw_uid,identity.pw_gid)
    module=proof['module']
    installed=sql(db,"SELECT latest_version FROM ir_module_module WHERE name='%s' AND state='installed'"%module)
    if installed:assert tuple(map(int,proof['version'].split('.')))>=tuple(map(int,installed.split('.')))
    baseline={'config_sha256':sha(conf),'installed':installed,'source':None}
    for root in opts['addons_path'].split(','):
        source=Path(root.strip())/module
        if source.exists():
            baseline['source']={str(f.relative_to(source)):sha(f) for f in source.rglob('*') if f.is_file() and f.suffix in ['.py','.xml','.csv']};break
    base=['sudo','-u',user,'nice','-n','15','/usr/bin/python3.10','/opt/odoo18/odoo-bin']
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    clone='WHATSAPP_QA_'+a.environment.upper()+'_'+a.run_id
    def errors(text):
        known = "Some modules are not loaded, some dependencies or manifest may be missing: " + repr(['steps_api'] if a.environment=='development' else ['steps_transport'])
        return [s for s in text.splitlines() if (' ERROR ' in s or ' CRITICAL ' in s) and not s.rstrip().endswith(known)]
    def verify(database,source):
        script="import importlib,json\nfrom lxml import etree\ntry:\n m=env['ir.module.module'].search([('name','=',%r)])\n assert m.state=='installed' and m.latest_version==%r\n assert importlib.import_module('odoo.addons.'+%r).__file__.startswith(%r+'/')\n for model in ('step.helpdesk.wa.channel','step.helpdesk.wa.message','step.helpdesk.wa.compose'):\n  etree.fromstring(env[model].get_view(view_type='form')['arch'])\n assert 'action_respond_whatsapp' in env['helpdesk.ticket'].get_view(view_type='form')['arch']\n assert not env['step.helpdesk.wa.channel'].search_count([('enabled','=',True),('provider','=','meta_cloud')])\n print('WHATSAPP_REGISTRY_OK')\nfinally:env.cr.rollback()\n"%(module,proof['version'],module,str(source))
        result=subprocess.run(base+['shell','-c',str(conf),'-d',database,'--db-filter=^'+database+'$','--addons-path='+str(source)+','+opts['addons_path'],'--no-http','--workers=0','--max-cron-threads=0','--log-level=error'],input=script,text=True,capture_output=True)
        (stage/('verify-'+database+'.log')).write_text(result.stdout+result.stderr)
        assert result.returncode==0 and 'WHATSAPP_REGISTRY_OK' in result.stdout,'See private registry log'
    if a.action=='diagnose':
        assert sql('postgres',"SELECT 1 FROM pg_database WHERE datname='%s'"%clone)
        assert json.loads((stage/'baseline.json').read_text())==baseline
        with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        log=stage/('diagnose-'+stamp+'.log')
        result=subprocess.run(base+['-c',str(conf),'-d',clone,'--db-filter=^'+clone+'$','--addons-path='+str(addon)+','+opts['addons_path'],
            '--data-dir='+str(stage/'data'),'--http-interface=127.0.0.1','--http-port='+str(port),'--workers=0','--max-cron-threads=0','--without-demo=all',
            '-u',module,'--test-enable','--test-tags=/'+module,'--stop-after-init','--logfile='+str(log)])
        text=log.read_text(errors='replace')
        print('\n'.join(s for s in text.splitlines() if 'tests.result' in s or 'ERROR:' in s or 'FAIL:' in s)[-4000:],flush=True)
        assert result.returncode==0 and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',text) and not errors(text),'See private diagnostic log'
        print('WHATSAPP_DIAGNOSIS_OK; fresh clone required before promotion',flush=True);return
    if a.action in ['qa','compatibility']:
        assert not sql('postgres',"SELECT 1 FROM pg_database WHERE datname='%s'"%clone)
        (stage/'baseline.json').write_text(json.dumps(baseline))
        before=snapshots(db);(stage/'business_before.json').write_text(json.dumps(before))
        with (stage/'source.dump').open('wb') as stream:run('sudo','-u','postgres','pg_dump','-Fc',db,stdout=stream)
        run('sudo','-u','postgres','createdb','-O',opts['db_user'],clone)
        with (stage/'source.dump').open('rb') as stream:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role',opts['db_user'],'-d',clone,stdin=stream)
        sql(clone,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        data=stage/'data';store=Path(opts['data_dir'])/'filestore'/db
        if store.exists():
            destination=data/'filestore'/clone;destination.mkdir(parents=True,exist_ok=True)
            run('rsync','-a',str(store)+'/',str(destination)+'/')
        for f in [data,*data.rglob('*')]:
            if f.exists():os.chown(f,identity.pw_uid,identity.pw_gid)
        with socket.socket() as listener:listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        sql(clone,"UPDATE ir_config_parameter SET value='http://127.0.0.1:%s' WHERE key='web.base.url'"%port)
        log=stage/('qa-'+stamp+'.log')
        print('WHATSAPP_QA_BEGIN '+json.dumps({'database':clone,'log':str(log)}),flush=True)
        result=subprocess.run(base+['-c',str(conf),'-d',clone,'--db-filter=^'+clone+'$','--addons-path='+str(addon)+','+opts['addons_path'],
            '--data-dir='+str(data),'--http-interface=127.0.0.1','--http-port='+str(port),'--workers=0','--max-cron-threads=0','--without-demo=all',
            '-i',module,'--test-enable','--test-tags=/'+module,'--stop-after-init','--logfile='+str(log)])
        text=log.read_text(errors='replace')
        print('\n'.join(s for s in text.splitlines() if 'tests.result' in s or ' ERROR ' in s or ' FAIL' in s)[-4000:],flush=True)
        assert result.returncode==0 and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',text) and not errors(text),'See private QA log'
        after=snapshots(clone,before);assert all(after.get(k)==v for k,v in before.items()),'Existing support records changed'
        verify(clone,addon)
        (stage/'qa_passed.json').write_text(json.dumps({'commit':proof['commit'],'sha256':package_sha,'database':clone,'log':str(log)}))
        print('WHATSAPP_QA_OK '+a.environment,flush=True);return
    passed=json.loads((stage/'qa_passed.json').read_text());assert passed['commit']==proof['commit'] and passed['sha256']==package_sha
    release=Path('/opt/steps-managed/whatsapp')/a.environment/proof['commit']
    if a.action=='deploy':
        if a.environment=='steps':assert (Path('/opt/steps-managed/whatsapp/development')/proof['commit']/'release.json').exists()
        assert json.loads((stage/'baseline.json').read_text())==baseline,'Repeat compatibility after concurrent changes'
        with open('/run/lock/steps-environments.lock','a') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            for file in Path('/proc').glob('[0-9]*/cmdline'):
                try:argv=file.read_bytes().decode(errors='replace').split('\0')
                except OSError:continue
                if any(Path(v).name=='odoo-bin' for v in argv):assert not any(v in ['-i','-u','--init','--update'] or v.startswith(('--init=','--update=')) for v in argv),'Concurrent upgrade'
            assert not release.exists();release.mkdir(parents=True);unpack(a.package,release)
            for f in [release,*release.rglob('*')]:os.chown(f,identity.pw_uid,identity.pw_gid)
            backup=Path('/opt/steps_backups')/('whatsapp_'+a.environment+'_'+stamp);backup.mkdir(mode=0o700)
            shutil.copy2(conf,backup/'odoo.conf');run('systemctl','stop',target['service'])
            try:
                with (backup/'database.dump').open('wb') as stream:run('sudo','-u','postgres','pg_dump','-Fc',db,stdout=stream)
                before=snapshots(db)
                updated,count=re.subn(r'(?m)^\s*addons_path\s*=.*$','addons_path = '+str(release)+','+opts['addons_path'],conf.read_text());assert count==1;conf.write_text(updated)
                log=stage/('deploy-'+stamp+'.log')
                result=subprocess.run(base+['-c',str(conf),'-d',db,'--no-http','--workers=0','--max-cron-threads=0','--without-demo=all','-i',module,'--stop-after-init','--logfile='+str(log)])
                text=log.read_text(errors='replace');assert result.returncode==0 and 'Modules loaded.' in text and not errors(text),'See private deployment log'
                after=snapshots(db,before);assert all(after.get(k)==v for k,v in before.items())
                (backup/'deployment.json').write_text(json.dumps({'commit':proof['commit'],'sha256':package_sha,'before':before,'after':after}))
            finally:run('systemctl','start',target['service'])
            print('WHATSAPP_DEPLOY_OK backup='+str(backup),flush=True)
    verify(db,release);run('systemctl','is-active','--quiet',target['service'])
    with urllib.request.urlopen(target['url']+'/web/login',timeout=30) as response:assert response.status==200
    print('WHATSAPP_VERIFY_OK '+a.environment,flush=True)


if __name__=='__main__':main()
