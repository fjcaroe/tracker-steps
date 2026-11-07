"""T176: provision a clean, independent ECOPLANTAS demo from native Odoo code.

Uses the Enterprise edition available in Development. Never copies a license
code, expiration date, UUID, client records, Studio customizations or API keys.
Existing environments and their administrative passwords remain unchanged.
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
import secrets
import shutil
import socket
import subprocess
import tempfile
import urllib.request

from manage_management import query, tree_hash


ROOT=Path('/opt/steps-demos/ecoplantas')
DB='ECOPLANTAS'
COPY='ECOPLANTAS_T176_QA'
USER='ecoplantas_odoo18'
DOMAIN='ecoplantas.stepsapp.cl'
PORT=8084
CONF=Path('/etc/odoo18-ecoplantas.conf')
SERVICE='odoo18-ecoplantas.service'
MODULES=('contacts','crm','sale_management','purchase_stock','stock_account','account_accountant','l10n_cl')


def run(*args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)


def settings(path):
    cfg=configparser.ConfigParser(interpolation=None);cfg.read(path)
    return cfg


def private_json(path,value):
    path.write_text(json.dumps(value,indent=2));path.chmod(0o600)


def conf_for(database):
    assert database in (DB,COPY)
    return CONF if database==DB else ROOT/'qa.conf'


def odoo(database,arguments,script=None):
    command=['sudo','-u',USER,'/usr/bin/python3.10','/opt/odoo18/odoo-bin']
    if script is not None:command+=['shell']
    command+=['-c',str(conf_for(database)),'-d',database,'--db-filter=^'+database+'$',
              '--no-http','--workers=0','--max-cron-threads=0','--without-demo=all']
    command+=arguments
    result=run(*command,input=script,text=True,capture_output=True)
    if script is not None:
        assert 'ECOPLANTAS_' in result.stdout,result.stderr[-2000:]
    return result


def source_options():
    cfg=settings('/etc/dev_odoo18.conf');opts=cfg['options']
    assert opts['db_name']=='LAB_TAREAS'
    return opts


def prepare():
    assert not ROOT.exists() and not CONF.exists(),'Preserve an existing preparation'
    assert not query('postgres',"SELECT 1 FROM pg_database WHERE datname IN ('ECOPLANTAS','ECOPLANTAS_T176_QA')")
    assert not query('postgres',"SELECT 1 FROM pg_roles WHERE rolname='ecoplantas_odoo18'")
    try:pwd.getpwnam(USER)
    except KeyError:pass
    else:raise AssertionError('Existing service identity must be reviewed')
    assert shutil.disk_usage('/opt').free>8*2**30
    roots=[Path(value.strip()) for value in source_options()['addons_path'].split(',')]
    resolved={}
    def resolve(name):
        if name in resolved:return
        path=next((root/name for root in roots if (root/name/'__manifest__.py').is_file()),None)
        assert path,'Missing native addon: '+name
        manifest=ast.literal_eval((path/'__manifest__.py').read_text(encoding='utf-8'))
        resolved[name]=(path,manifest)
        for dependency in manifest.get('depends',[]):resolve(dependency)
    for name in ('base','web_enterprise',*MODULES):resolve(name)
    assert not any(name.startswith(('step_','l10n_cl_simpledigital')) for name in resolved)
    run('useradd','--system','--home-dir',str(ROOT),'--no-create-home','--shell','/usr/sbin/nologin',USER)
    identity=pwd.getpwnam(USER);ROOT.mkdir(parents=True,mode=0o750);os.chown(ROOT,0,identity.pw_gid)
    logs=ROOT/'logs';logs.mkdir(mode=0o700);os.chown(logs,identity.pw_uid,identity.pw_gid)
    addons=ROOT/'addons';addons.mkdir(mode=0o750);os.chown(addons,0,identity.pw_gid)
    frozen={}
    for name,(source,manifest) in resolved.items():
        shutil.copytree(source,addons/name,ignore=shutil.ignore_patterns('__pycache__','.git','*.pyc'))
        assert tree_hash(source)==tree_hash(addons/name)
        frozen[name]={'source':str(source),'sha256':tree_hash(addons/name),'version':manifest.get('version')}
    for path in [addons,*addons.rglob('*')]:
        os.chown(path,0,identity.pw_gid)
        path.chmod(0o750 if path.is_dir() or path.stat().st_mode & 0o111 else 0o640)
    password=secrets.token_urlsafe(48)
    query('postgres',"CREATE ROLE "+USER+" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD '"+password+"'")
    for database in (COPY,DB):
        data=ROOT/('qa-data' if database==COPY else 'data');data.mkdir(mode=0o750)
        os.chown(data,identity.pw_uid,identity.pw_gid)
        cfg=configparser.ConfigParser(interpolation=None)
        cfg['options']={'admin_passwd':secrets.token_urlsafe(48),'db_name':database,'dbfilter':'^'+database+'$',
            'db_user':USER,'db_password':password,'db_host':'127.0.0.1','db_port':'5432','list_db':'False',
            'addons_path':str(addons),'data_dir':str(data),'http_interface':'127.0.0.1',
            'http_port':str(PORT if database==DB else 0),'gevent_port':'0','workers':'0','max_cron_threads':'0',
            'db_maxconn':'16','proxy_mode':'True','smtp_server':'invalid','smtp_port':'1025',
            'limit_memory_hard':str(1536*1024**2),'limit_memory_soft':str(1024**3)}
        with conf_for(database).open('w') as stream:cfg.write(stream)
        os.chown(conf_for(database),0,identity.pw_gid);conf_for(database).chmod(0o640)
    hba=Path(query('postgres','SHOW hba_file'))
    original=hba.read_bytes();(ROOT/'pg_hba_before.conf').write_bytes(original);(ROOT/'pg_hba_before.conf').chmod(0o600)
    marker='# BEGIN STEPS ECOPLANTAS T176\n'
    assert marker.encode() not in original
    block=(marker+f'local "{DB}","{COPY}",postgres {USER} md5\n'
        +f'local all {USER} reject\n'
        +f'host "{DB}","{COPY}",postgres {USER} 127.0.0.1/32 md5\n'
        +f'host all {USER} 0.0.0.0/0 reject\nhost all {USER} ::/0 reject\n'
        +'# END STEPS ECOPLANTAS T176\n')
    hba.write_bytes(block.encode()+original)
    if query('postgres','SELECT count(*) FROM pg_hba_file_rules WHERE error IS NOT NULL')!='0':
        hba.write_bytes(original);raise AssertionError('Invalid new database access rules')
    assert query('postgres','SELECT pg_reload_conf()')=='t'
    private_json(ROOT/'prepared.json',{'ticket':176,'source':'Development native code only','modules':frozen,
        'config_before_sha256':hashlib.sha256(Path('/etc/dev_odoo18.conf').read_bytes()).hexdigest(),
        'created_at':datetime.now(timezone.utc).isoformat(),'license_copied':False})
    print('ECOPLANTAS_PREPARED modules='+str(len(frozen)),flush=True)


def configure_company(database):
    # Only the source administrative identity is read. Its password hash stays
    # on the server and is never printed, reset or included in an evidence file.
    profile=json.loads(query('LAB_TAREAS',"SELECT row_to_json(profile) FROM (SELECT u.login,p.name,u.password,u.active FROM res_users u JOIN res_partner p ON p.id=u.partner_id WHERE u.id=(SELECT res_id FROM ir_model_data WHERE module='base' AND name='user_admin')) profile"))
    assert profile['active'] and profile['password']
    identity=pwd.getpwnam(USER)
    handle=tempfile.NamedTemporaryFile(mode='w',dir=ROOT,prefix='.admin-profile-',suffix='.json',delete=False)
    path=Path(handle.name)
    try:
        json.dump(profile,handle);handle.close();path.chmod(0o600);os.chown(path,identity.pw_uid,identity.pw_gid)
        script='''import json
from pathlib import Path
profile=json.loads(Path(PROFILE_PATH).read_text())
company=env.ref('base.main_company')
currency=env.ref('base.CLP');currency.active=True
company.with_context(tracking_disable=True).write({'name':'ECOPLANTAS','country_id':env.ref('base.cl').id,'currency_id':currency.id})
user=env.ref('base.user_admin')
user.with_context(no_reset_password=True,tracking_disable=True,mail_notrack=True,mail_create_nosubscribe=True).write({
    'login':profile['login'],'name':profile['name'],'email':False,'lang':'es_CL','tz':'America/Santiago'})
env.cr.execute('UPDATE res_users SET password=%s WHERE id=%s',[profile['password'],user.id])
env.cr.commit()
print('ECOPLANTAS_COMPANY_AND_EXISTING_ADMIN_READY')
'''
        result=odoo(database,['--log-level=error'],script='PROFILE_PATH='+repr(str(path))+'\n'+script)
        assert 'ECOPLANTAS_COMPANY_AND_EXISTING_ADMIN_READY' in result.stdout
    finally:
        handle.close();path.unlink(missing_ok=True)


def initialize(database,resume=False):
    assert (ROOT/'prepared.json').is_file()
    if database==DB:assert (ROOT/'copy-verified.json').is_file()
    phase=ROOT/('initializing-'+database+'.json')
    exists=bool(query('postgres',"SELECT 1 FROM pg_database WHERE datname='"+database+"'"))
    if exists:
        assert resume and phase.is_file() and not (ROOT/'published.json').exists(),'Preserve existing demo data'
        assert query('postgres',"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='"+database+"'")==USER
    else:
        private_json(phase,{'database':database,'fresh':True})
        run('sudo','-u','postgres','createdb','-O',USER,database)
        query(database,'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
    bootstrap=ROOT/'logs'/(database+'-bootstrap.log')
    odoo(database,['-i','base,web_enterprise','--load-language=es_CL','--stop-after-init','--logfile='+str(bootstrap)])
    configure_company(database)
    log=ROOT/'logs'/(database+'-applications.log')
    odoo(database,['-i',','.join(MODULES),'--stop-after-init','--logfile='+str(log)])
    odoo(database,['--log-level=error'],script='''
env['ir.cron'].search([]).write({'active':False})
env['ir.mail_server'].search([]).write({'active':False})
if 'fetchmail.server' in env:
    env['fetchmail.server'].search([]).write({'active':False})
params=env['ir.config_parameter']
params.set_param('web.base.url','https://ecoplantas.stepsapp.cl')
params.set_param('web.base.url.freeze','True')
env.cr.commit()
print('ECOPLANTAS_AUTOMATIC_DELIVERIES_DISABLED')
''')
    print('ECOPLANTAS_INITIALIZED '+database,flush=True)


def verify(database):
    copy=database==COPY
    prepared=json.loads((ROOT/'prepared.json').read_text())
    assert hashlib.sha256(Path('/etc/dev_odoo18.conf').read_bytes()).hexdigest()==prepared['config_before_sha256']
    for name,item in prepared['modules'].items():
        assert tree_hash(ROOT/'addons'/name)==item['sha256'],name
    script='''
import json
from odoo.tools import config
old=config['test_enable'];config['test_enable']=True
try:
    from odoo.tests import Form
finally:config['test_enable']=old
company=env.ref('base.main_company');user=env.ref('base.user_admin')
business=env(user=user,su=False,context=dict(env.context,allowed_company_ids=company.ids,tracking_disable=True,mail_notrack=True))
assert company.name=='ECOPLANTAS' and company.country_id==env.ref('base.cl') and company.currency_id==env.ref('base.CLP')
required=set(MODULE_NAMES)
modules=env['ir.module.module'].search([('name','in',list(required)),('state','=','installed')])
assert set(modules.mapped('name'))==required
counts={name:business[name].search_count([]) for name in ('sale.order','purchase.order','account.move','stock.picking')}
assert not any(counts.values()),counts
assert env['ir.cron'].search_count([('active','=',True)])==0
assert env['ir.mail_server'].search_count([('active','=',True)])==0
Form(business['sale.order']);Form(business['purchase.order'])
Form(business['account.move'].with_context(default_move_type='out_invoice'))
menus=business['ir.ui.menu']._visible_menu_ids()
assert env.ref('sale.sale_menu_root').id in menus and env.ref('stock.menu_stock_root').id in menus
if COPY_FLOW:
    partner=business['res.partner'].create({'name':'ECOPLANTAS validation partner'})
    product=business['product.product'].create({'name':'ECOPLANTAS validation plant','list_price':1000,'standard_price':500})
    form=Form(business['sale.order'])
    form.partner_id=partner
    with form.order_line.new() as line:
        line.product_id=product;line.product_uom_qty=2
    quotation=form.save()
    assert quotation.state=='draft' and quotation.amount_untaxed==2000
    form=Form(business['purchase.order'])
    form.partner_id=partner
    with form.order_line.new() as line:
        line.product_id=product;line.product_qty=3;line.price_unit=500
    purchase=form.save()
    assert purchase.state=='draft' and purchase.amount_untaxed==1500
    bill=business['account.move'].with_context(default_move_type='in_invoice').create({
        'move_type':'in_invoice','partner_id':partner.id,'invoice_line_ids':[(0,0,{'product_id':product.id,'quantity':1,'price_unit':500})]})
    assert bill.state=='draft' and bill.amount_untaxed==500 and not bill.posted_before
params=env['ir.config_parameter']
proof={'database':env.cr.dbname,'native_menus_and_forms':True,'copy_flow':COPY_FLOW,
       'empty_business_counts':counts,'native_trial_or_registration':params.get_param('database.expiration_reason'),
       'enterprise_code_present':bool(params.get_param('database.enterprise_code')),
       'expiration_date':params.get_param('database.expiration_date'),'source_client_data_copied':False}
env.cr.rollback()
print('ECOPLANTAS_NATIVE_VERIFY_OK '+json.dumps(proof))
'''
    result=odoo(database,['--log-level=error'],script='MODULE_NAMES='+repr(('web_enterprise',*MODULES))+'\nCOPY_FLOW='+repr(copy)+'\n'+script)
    marker='ECOPLANTAS_NATIVE_VERIFY_OK '
    lines=[line for line in result.stdout.splitlines() if line.startswith(marker)]
    assert len(lines)==1,result.stderr[-2000:]
    source_uuid=query('LAB_TAREAS',"SELECT value FROM ir_config_parameter WHERE key='database.uuid'")
    target_uuid=query(database,"SELECT value FROM ir_config_parameter WHERE key='database.uuid'")
    assert source_uuid and target_uuid and source_uuid!=target_uuid
    source_password=query('LAB_TAREAS',"SELECT password FROM res_users WHERE id=(SELECT res_id FROM ir_model_data WHERE module='base' AND name='user_admin')")
    target_password=query(database,"SELECT password FROM res_users WHERE id=(SELECT res_id FROM ir_model_data WHERE module='base' AND name='user_admin')")
    assert source_password==target_password
    # The new service credential must not open the source or another customer.
    options=settings(conf_for(database))['options']
    denied=subprocess.run(['psql','-h','127.0.0.1','-U',USER,'-d','LAB_TAREAS','-Atc','SELECT 1'],
        env=dict(os.environ,PGPASSWORD=options['db_password']),text=True,capture_output=True)
    assert denied.returncode!=0 and 'pg_hba' in denied.stderr
    if not copy:
        assert target_uuid!=query(COPY,"SELECT value FROM ir_config_parameter WHERE key='database.uuid'")
    value=json.loads(lines[0][len(marker):]);value.update(unique_uuid=True,existing_admin_preserved=True,
        license_copied=False,source_database_denied=True)
    private_json(ROOT/('copy-verified.json' if copy else 'verified.json'),value)
    print('ECOPLANTAS_VERIFIED '+json.dumps(value),flush=True)


def publish():
    assert (ROOT/'verified.json').is_file() and not (ROOT/'published.json').exists()
    assert socket.gethostbyname(DOMAIN)=='35.222.25.110','Publish the new DNS record first'
    service=Path('/etc/systemd/system')/SERVICE
    assert not service.exists(),'Do not replace another service'
    service.write_text(f'''[Unit]
Description=Odoo ECOPLANTAS demonstration T176
After=network.target postgresql.service
[Service]
Type=simple
User={USER}
Group={USER}
WorkingDirectory=/opt/odoo18
ExecStart=/usr/bin/python3.10 /opt/odoo18/odoo-bin -c {CONF}
Restart=on-failure
RestartSec=5
UMask=0027
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ReadWritePaths={ROOT}
[Install]
WantedBy=multi-user.target
''')
    run('systemctl','daemon-reload');run('systemctl','enable','--now',SERVICE)
    site=Path('/etc/nginx/sites-available')/DOMAIN;enabled=Path('/etc/nginx/sites-enabled')/DOMAIN
    marker='# Steps ECOPLANTAS demo T176\n'
    assert not site.exists() or site.read_text().startswith(marker)
    site.write_text(marker+f'''server {{
listen 80; listen [::]:80; server_name {DOMAIN};
location ^~ /.well-known/acme-challenge/ {{ root /var/www/letsencrypt; try_files $uri =404; }}
location / {{ return 503; }}
}}
''')
    if not enabled.exists():enabled.symlink_to(site)
    run('nginx','-t');run('systemctl','reload','nginx')
    run('certbot','certonly','--non-interactive','--webroot','-w','/var/www/letsencrypt','-d',DOMAIN)
    site.write_text(marker+f'''server {{
listen 80; listen [::]:80; server_name {DOMAIN}; return 301 https://$host$request_uri;
}}
server {{
listen 443 ssl http2; listen [::]:443 ssl http2; server_name {DOMAIN};
ssl_certificate /etc/letsencrypt/live/{DOMAIN}/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/{DOMAIN}/privkey.pem;
include /etc/letsencrypt/options-ssl-nginx.conf;
ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
client_max_body_size 200m;
add_header Strict-Transport-Security "max-age=31536000" always;
location ^~ /web/database {{ return 404; }}
location / {{
proxy_pass http://127.0.0.1:{PORT};
proxy_set_header Host $host;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto https;
proxy_read_timeout 300s; proxy_connect_timeout 30s;
}}
}}
''')
    run('nginx','-t');run('systemctl','reload','nginx')
    with urllib.request.urlopen('https://'+DOMAIN+'/web/login?db='+DB,timeout=60) as response:
        assert response.status==200 and b'password' in response.read()
    run('systemctl','is-active','--quiet',SERVICE)
    private_json(ROOT/'published.json',{'database':DB,'url':'https://'+DOMAIN,'service':SERVICE,
        'copy_proof':str(ROOT/'copy-verified.json'),'proof':str(ROOT/'verified.json'),'license_copied':False})
    print('ECOPLANTAS_PUBLISHED https://'+DOMAIN,flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','init-copy','verify-copy','init','verify','publish'))
    parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();assert os.geteuid()==0
    with open('/run/lock/steps-environments.lock','a') as lease:
        print('ECOPLANTAS_WAITING_SHARED_LEASE',flush=True);fcntl.flock(lease,fcntl.LOCK_EX)
        if args.action=='prepare':prepare()
        elif args.action in ('init-copy','init'):initialize(COPY if args.action=='init-copy' else DB,args.resume)
        elif args.action in ('verify-copy','verify'):verify(COPY if args.action=='verify-copy' else DB)
        else:publish()


if __name__=='__main__':main()
