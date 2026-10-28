"""Install the exact BPA core on a new private Community-only database."""
import argparse
import ast
import configparser
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import subprocess


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('run_id');p.add_argument('--runtime',type=Path,default=Path('/opt/steps-validation/community-foundation-20261027/community-runtime'));a=p.parse_args()
    assert os.geteuid()==0 and re.fullmatch('[a-z0-9_]{1,20}',a.run_id)
    manifest=ast.literal_eval((a.source/'step_product_bpa/__manifest__.py').read_text())
    assert manifest['depends']==['product','mail']
    assert run('git','-C',str(a.runtime),'remote','get-url','origin',text=True,capture_output=True).stdout.strip()=='https://github.com/odoo/odoo.git'
    assert not run('git','-C',str(a.runtime),'status','--porcelain',text=True,capture_output=True).stdout.strip()
    runtime_commit=run('git','-C',str(a.runtime),'rev-parse','HEAD',text=True,capture_output=True).stdout.strip()
    with open('/run/lock/steps-environments.lock','a') as lock:
        print('BPA_COMMUNITY_WAITING_FOR_LEASE',flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
        c=configparser.ConfigParser(interpolation=None);c.read('/etc/dev_odoo18.conf')
        database='BPA_COMMUNITY_'+a.run_id
        folder=Path('/opt/steps-validation')/database;folder.mkdir(mode=0o750)
        import pwd
        identity=pwd.getpwnam('odoo');os.chown(folder,identity.pw_uid,identity.pw_gid)
        run('sudo','-u','postgres','createdb','-O',c['options']['db_user'],database)
        log=folder/'tests.log'
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        # The server's addons directory mixes Community and commercial addons.
        # Expose only modules with an explicit open-source manifest license.
        clean=folder/'community-addons';clean.mkdir()
        licenses={}
        for parent in (a.runtime/'odoo/addons',a.runtime/'addons'):
            for module in parent.iterdir():
                file=module/'__manifest__.py'
                if not file.is_file(): continue
                info=ast.literal_eval(file.read_text(encoding='utf-8'))
                license=info.get('license','LGPL-3')
                if license in ('LGPL-3','AGPL-3','GPL-3','GPL-2','MIT','BSD-3','Other OSI approved licence') and not (clean/module.name).exists():
                    (clean/module.name).symlink_to(module,target_is_directory=True)
                    licenses[module.name]=license
        paths=str(clean)+','+str(a.source)
        run('sudo','-u','odoo','/usr/bin/python3.10',str(a.runtime/'odoo-bin'),'-c','/etc/dev_odoo18.conf',
            '-d',database,'--db-filter=^'+database+'$','--addons-path='+paths,'--data-dir='+str(folder/'data'),
            '--no-http','--http-interface=127.0.0.1','--http-port='+str(port),'--gevent-port=0','--workers=0','--max-cron-threads=0','--without-demo=all','-i','step_product_bpa',
            '--test-enable','--test-tags=/step_product_bpa','--stop-after-init','--logfile='+str(log))
        text=log.read_text(errors='replace')
        assert re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',text) and ' ERROR ' not in text,text[-3500:]
        result=run('sudo','-u','postgres','psql','-At','-d',database,'-c',"SELECT json_agg(name ORDER BY name) FROM ir_module_module WHERE state='installed'",text=True,capture_output=True)
        installed=json.loads(result.stdout)
        assert not set(installed)&{'web_enterprise','web_studio','studio_customization'}
        assert all(name=='step_product_bpa' or name in licenses for name in installed)
        proof={'community_only':True,'official_runtime_commit':runtime_commit,'versions':{'step_product_bpa':manifest['version']},'database':database,'installed':installed,'licenses':{name:licenses.get(name,'AGPL-3') for name in installed},'tests_passed':True}
        (folder/'passed.json').write_text(json.dumps(proof,indent=2))
        print('BPA_COMMUNITY_ONLY_OK '+json.dumps(proof),flush=True)

if __name__=='__main__':main()
