"""T115: create an isolated, neutralized Cerro customer QA without replacing it.

Run as root on the registered host. Creation refuses an existing target; failed
work is preserved. Publishing requires DNS and a valid public TLS certificate.
No source credentials or account passwords are changed or printed.
"""
import argparse
import configparser
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import socket
import subprocess
import uuid

DB='QA-CERROELPLOMO'
USER='cerroqa_odoo18'
DOMAIN='qa-cerroelplomo.stepsapp.cl'
PORT=8083
ROOT=Path('/opt/steps-qa/cerro')
CONF=Path('/etc/odoo18-qa-cerroelplomo.conf')
SERVICE='odoo18-qa-cerroelplomo.service'
SOURCE='CERRO_EL_PLOMO'


def run(*args, **kwargs):
    return subprocess.run(args,check=True,**kwargs)


def query(db,sql):
    return run('sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-d',db,'-At',
               input=sql,text=True,capture_output=True).stdout.strip()


def firewall():
    uid=str(pwd.getpwnam(USER).pw_uid)
    for binary in ('/usr/sbin/iptables','/usr/sbin/ip6tables'):
        chain='STEPS_QA_CERRO'
        if subprocess.run([binary,'-w','-L',chain],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
            run(binary,'-w','-N',chain)
        run(binary,'-w','-F',chain)
        run(binary,'-w','-A',chain,'-m','conntrack','--ctstate','ESTABLISHED,RELATED','-j','ACCEPT')
        loopback='127.0.0.1' if binary.endswith('/iptables') else '::1'
        run(binary,'-w','-A',chain,'-d',loopback,'-p','tcp','--dport',str(PORT),'-j','ACCEPT')
        run(binary,'-w','-A',chain,'-j','REJECT')
        rule=['OUTPUT','-m','owner','--uid-owner',uid,'-j',chain]
        if subprocess.run([binary,'-w','-C',*rule],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
            run(binary,'-w','-I',*rule)


def verify():
    assert query(DB,"SELECT value FROM ir_config_parameter WHERE key='database.is_neutralized'")=='true'
    assert query(DB,'SELECT count(*) FROM ir_cron WHERE active')=='0'
    assert query(DB,"SELECT count(*) FROM ir_mail_server WHERE active AND smtp_host!='invalid'")=='0'
    assert query(DB,'SELECT count(*) FROM fetchmail_server WHERE active')=='0'
    run('systemctl','is-active','--quiet',SERVICE)
    # Read forms and menus with the copied existing business user, no saves.
    probe="""from odoo.tools import config
from native_business_profile import scoped_business_environment
try:
    # The helper recognizes the canonical source identity for this copied DB.
    company=env['res.company'].search([('vat','=','76943293-0')]);assert len(company)==1
    users=env['res.users'].search([('active','=',True),('share','=',False),('id','!=',1),('company_ids','in',company.ids)]).filtered(lambda u:u.has_group('base.group_system') and u.has_group('account.group_account_manager'))
    assert users
    scoped=env(user=users[:1],su=False,context=dict(env.context,allowed_company_ids=company.ids))
    previous=config['test_enable'];config['test_enable']=True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable']=previous
    menu=scoped.ref('step_packing_operations.menu_packing_production')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids() and menu.action.res_model=='step.packing.production'
    model=scoped['step.packing.production'];record=model.search([],limit=1)
    Form(record or model,view='step_packing_operations.view_packing_production_form')
    assert scoped['ir.config_parameter'].sudo().get_param('web.base.url')=='https://qa-cerroelplomo.stepsapp.cl'
    print('CUSTOMER_QA_NATIVE_FLOW_OK user=%s company=%s writes=False'%(scoped.uid,company.id))
finally:
    env.cr.rollback()
""".replace('from native_business_profile import scoped_business_environment','')
    result=run('sudo','-u',USER,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',str(CONF),'-d',DB,'--no-http','--log-level=critical',input=probe,text=True,capture_output=True)
    assert 'CUSTOMER_QA_NATIVE_FLOW_OK' in result.stdout
    print(result.stdout.strip(),flush=True)
    # Outbound production APIs must fail; localhost QA remains reachable.
    code="import socket; s=socket.socket(); s.settimeout(3); r=s.connect_ex(('35.222.25.110',443)); assert r!=0; print('CUSTOMER_QA_EGRESS_BLOCKED')"
    run('sudo','-u',USER,'/usr/bin/python3.10','-c',code)
    print('CUSTOMER_QA_VERIFY_OK database='+DB,flush=True)


def create():
    assert not ROOT.exists() and not CONF.exists(), 'Preserve previous work; inspect before resuming'
    assert not query('postgres',"SELECT 1 FROM pg_database WHERE datname='"+DB+"'")
    assert not query('postgres',"SELECT 1 FROM pg_roles WHERE rolname='"+USER+"'")
    try:
        pwd.getpwnam(USER)
    except KeyError:
        pass
    else:
        raise AssertionError('Existing operating-system identity must be reviewed')
    assert shutil.disk_usage('/opt').free>12*2**30
    cfg=configparser.ConfigParser(interpolation=None);cfg.read('/etc/odoo18-cerroelplomo.conf');opts=cfg['options']
    assert opts['db_name']==SOURCE and opts.get('db_host','False') in ('False','')
    paths=[Path(v.strip()) for v in opts['addons_path'].split(',')]
    installed=json.loads(query(SOURCE,"SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'"))
    resolved={name:next((path/name for path in paths if (path/name/'__manifest__.py').exists()),None) for name in installed}
    assert all(resolved.values()), 'Do not create a copy with missing addon sources'
    run('useradd','--system','--home-dir',str(ROOT),'--no-create-home','--shell','/usr/sbin/nologin',USER)
    ident=pwd.getpwnam(USER);ROOT.mkdir(parents=True,mode=0o750);os.chown(ROOT,0,ident.pw_gid)
    addons=ROOT/'addons';addons.mkdir(mode=0o750);os.chown(addons,0,ident.pw_gid)
    from manage_management import tree_hash
    hashes={}
    for name,source in resolved.items():
        shutil.copytree(source,addons/name,ignore=shutil.ignore_patterns('__pycache__','.git','*.pyc'))
        assert tree_hash(source)==tree_hash(addons/name)
        hashes[name]={'version':installed[name],'source':str(source),'hash':tree_hash(addons/name)}
    for path in [addons,*addons.rglob('*')]:
        os.chown(path,0,ident.pw_gid)
        path.chmod(0o750 if path.is_dir() or path.stat().st_mode & 0o111 else 0o640)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=Path('/opt/steps_backups')/('customer_qa_cerro_'+stamp);backup.mkdir(mode=0o700)
    dump=backup/'source.dump'
    data=ROOT/'data';store=data/'filestore'/DB;store.mkdir(parents=True)
    run('systemctl','stop','odoo18-cerroelplomo.service')
    try:
        with dump.open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc',SOURCE,stdout=out)
        run('rsync','-a',str(Path(opts['data_dir'])/'filestore'/SOURCE)+'/',str(store)+'/')
    finally:
        run('systemctl','start','odoo18-cerroelplomo.service')
    query('postgres','CREATE ROLE '+USER+' LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;')
    run('sudo','-u','postgres','createdb','-O',USER,DB)
    with dump.open('rb') as inp:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role',USER,'-d',DB,stdin=inp)
    tables=query(DB,"SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'hr_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename LIKE 'sale_%' OR tablename LIKE 'purchase_%' OR tablename IN ('res_company','res_partner','res_partner_bank','res_country','account_move','account_move_line','account_payment','account_journal','account_account','account_tax')) ORDER BY tablename").splitlines()
    def business_snapshot():
        import re
        entries=[]
        for table in tables:
            assert re.fullmatch('[a-z_][a-z0-9_]*',table)
            row="(to_jsonb(t)-'l10n_cl_dte_service_provider')" if table=='res_company' else 'to_jsonb(t)'
            entries.append("SELECT '%s' AS name,json_build_object('rows',count(*),'digest',md5(COALESCE(string_agg(%s::text,'|' ORDER BY %s::text),''))) AS value FROM %s t"%(table,row,row,table))
        return json.loads(query(DB,'SELECT json_object_agg(name,value) FROM ('+' UNION ALL '.join(entries)+') snapshots'))
    before=business_snapshot()
    run('chown','-R',USER+':'+USER,str(data))
    cfg=configparser.ConfigParser(interpolation=None);cfg['options']={'admin_passwd':secrets.token_urlsafe(48)};opts=cfg['options']
    opts['db_name']=DB;opts['dbfilter']='^'+DB+'$';opts['list_db']='False'
    opts['db_user']=USER;opts['db_host']='False';opts.pop('db_password',None)
    opts['data_dir']=str(data);opts['addons_path']=str(addons);opts.pop('logfile',None)
    opts['http_port']=str(PORT);opts['http_interface']='127.0.0.1';opts['workers']='0';opts['max_cron_threads']='0';opts['db_maxconn']='16';opts['proxy_mode']='True'
    opts['limit_memory_hard']=str(1024**3);opts['limit_memory_soft']=str(768*1024**2)
    for key in list(opts):
        if key.startswith('smtp_'):del opts[key]
    opts['smtp_server']='invalid';opts['smtp_port']='1025'
    with CONF.open('w') as out:cfg.write(out)
    os.chown(CONF,0,ident.pw_gid);CONF.chmod(0o640)
    run('sudo','-u',USER,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','neutralize','-c',str(CONF),'-d',DB,'--no-http','--log-level=critical')
    # These copy-only changes do not alter documents, users or source credentials.
    parameters={'web.base.url':'https://'+DOMAIN,'web.base.url.freeze':'True','report.url':'http://127.0.0.1:'+str(PORT),'database.uuid':str(uuid.uuid4()),'database.secret':secrets.token_urlsafe(48)}
    # Values stay on stdin, never command arguments or console output.
    sql="UPDATE ir_cron SET active=false; UPDATE mail_mail SET state='cancel' WHERE state IN ('outgoing','exception');"
    for key,value in parameters.items():
        sql+="INSERT INTO ir_config_parameter(key,value) VALUES('%s','%s') ON CONFLICT(key) DO UPDATE SET value=excluded.value;"%(key,value.replace("'","''"))
    query(DB,sql)
    assert business_snapshot()==before, 'Business history must be preserved'
    assert query(DB,"SELECT count(*) FROM res_company WHERE l10n_cl_dte_service_provider!='SIITEST'")=='0'
    (backup/'business-preserved.json').write_text(json.dumps(before))
    helper=Path('/usr/local/libexec/steps-qa-cerro');helper.mkdir(parents=True,exist_ok=True)
    shutil.copy2(Path(__file__),helper/'provision_cerro_qa.py')
    firewall()
    fwunit=Path('/etc/systemd/system/steps-qa-cerro-firewall.service')
    fwunit.write_text('[Unit]\nDescription=Isolate Cerro QA outbound traffic\nBefore='+SERVICE+'\nAfter=network-pre.target\n[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=/usr/bin/python3.10 '+str(helper/'provision_cerro_qa.py')+' firewall\n[Install]\nWantedBy=multi-user.target\n')
    unit=Path('/etc/systemd/system')/SERVICE
    unit.write_text('[Unit]\nDescription=Odoo 18 QA-CERROELPLOMO (neutralized customer copy)\nAfter=postgresql.service steps-qa-cerro-firewall.service\nRequires=steps-qa-cerro-firewall.service\n[Service]\nType=simple\nUser='+USER+'\nGroup='+USER+'\nWorkingDirectory=/opt/odoo18\nEnvironment=PYTHONPATH=/opt/odoo18\nExecStart=/usr/bin/python3.10 /opt/odoo18/odoo-bin -c '+str(CONF)+'\nRestart=on-failure\nRestartSec=5\nNoNewPrivileges=true\nProtectSystem=full\nPrivateTmp=true\nMemoryMax=1536M\nCPUQuota=75%\n[Install]\nWantedBy=multi-user.target\n')
    manifest={'database':DB,'source':SOURCE,'created_at':stamp,'backup':str(backup),'source_modules':hashes,'payroll_accounting_preserved':True,'neutralized':True}
    (ROOT/'creation.json').write_text(json.dumps(manifest,indent=2));(ROOT/'creation.json').chmod(0o640)
    run('systemctl','daemon-reload');run('systemctl','enable','--now','steps-qa-cerro-firewall.service',SERVICE)
    print('CUSTOMER_QA_CREATED database='+DB+' backup='+str(backup),flush=True)


def publish():
    assert socket.gethostbyname(DOMAIN)=='35.222.25.110', 'Wait for the requested DNS record'
    assert (ROOT/'creation.json').exists()
    run('systemctl','is-active','--quiet',SERVICE)
    site=Path('/etc/nginx/sites-available')/DOMAIN
    enabled=Path('/etc/nginx/sites-enabled')/DOMAIN
    marker='# Steps customer QA T115\n'
    if site.exists():
        assert site.read_text().startswith(marker), 'Do not replace another virtual host'
    http='''server {
    listen 80; listen [::]:80;
    server_name DOMAIN;
    location ^~ /.well-known/acme-challenge/ {
        root /var/www/letsencrypt; try_files $uri =404;
    }
    location / { return 503; }
}
'''.replace('DOMAIN',DOMAIN)
    site.write_text(marker+http)
    if not enabled.exists():enabled.symlink_to(site)
    run('nginx','-t');run('systemctl','reload','nginx')
    result=subprocess.run(['certbot','certonly','--non-interactive','--webroot','-w',
        '/var/www/letsencrypt','-d',DOMAIN],text=True,capture_output=True)
    assert result.returncode==0, 'TLS issuance failed; HTTP remains unavailable, inspect certbot log'
    static=''
    for app in ('task','cosecha'):
        source=Path('/var/www')/app
        dest=Path('/var/www/qa-cerroelplomo')/app
        if source.exists():
            if not dest.exists():shutil.copytree(source,dest)
            static+='''
    location = /APP { return 301 /APP/; }
    location ^~ /APP/ {
        alias /var/www/qa-cerroelplomo/APP/;
        try_files $uri $uri/ /APP/index.html;
        add_header Cache-Control "no-cache";
    }
'''.replace('APP',app)
    tls='''server {
    listen 443 ssl http2; listen [::]:443 ssl http2;
    server_name DOMAIN;
    ssl_certificate /etc/letsencrypt/live/DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/DOMAIN/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    client_max_body_size 200m;
    add_header Strict-Transport-Security "max-age=31536000" always;
    location ^~ /web/database { return 404; }
STATIC
    location / {
        proxy_pass http://127.0.0.1:8083;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Port 443;
        proxy_read_timeout 720s;
        proxy_redirect off;
    }
}
'''.replace('DOMAIN',DOMAIN).replace('STATIC',static)
    site.write_text(marker+http.replace('return 503','return 301 https://$host$request_uri')+tls)
    run('nginx','-t');run('systemctl','reload','nginx')
    import urllib.request
    with urllib.request.urlopen('https://'+DOMAIN+'/web/login',timeout=45) as response:
        assert response.status==200 and b'password' in response.read()
    (ROOT/'published.json').write_text(json.dumps({'url':'https://'+DOMAIN,'tls':True}))
    print('CUSTOMER_QA_HTTPS_OK https://'+DOMAIN,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=('create','verify','publish','firewall'))
    args=parser.parse_args();assert os.geteuid()==0
    if args.action=='firewall':firewall();return
    with open('/run/lock/steps-environments.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if args.action=='create':create()
        elif args.action=='publish':publish()
        else:verify()


if __name__=='__main__':main()
