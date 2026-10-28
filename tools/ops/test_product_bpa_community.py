"""Install the exact BPA core on a new private Community-only database."""
import argparse
import ast
import configparser
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def main():
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('run_id');a=p.parse_args()
    assert os.geteuid()==0 and re.fullmatch('[a-z0-9_]{1,20}',a.run_id)
    manifest=ast.literal_eval((a.source/'step_product_bpa/__manifest__.py').read_text())
    assert manifest['depends']==['product','mail']
    with open('/run/lock/steps-environments.lock','a') as lock:
        print('BPA_COMMUNITY_WAITING_FOR_LEASE',flush=True);fcntl.flock(lock,fcntl.LOCK_EX)
        c=configparser.ConfigParser(interpolation=None);c.read('/etc/dev_odoo18.conf')
        database='BPA_COMMUNITY_'+a.run_id
        folder=Path('/opt/steps-validation')/database;folder.mkdir(mode=0o750)
        import pwd
        identity=pwd.getpwnam('odoo');os.chown(folder,identity.pw_uid,identity.pw_gid)
        run('sudo','-u','postgres','createdb','-O',c['options']['db_user'],database)
        log=folder/'tests.log'
        paths='/opt/odoo18/odoo/addons,/opt/odoo18/addons,'+str(a.source)
        run('sudo','-u','odoo','/usr/bin/python3.10','/opt/odoo18/odoo-bin','-c','/etc/dev_odoo18.conf',
            '-d',database,'--db-filter=^'+database+'$','--addons-path='+paths,'--data-dir='+str(folder/'data'),
            '--no-http','--workers=0','--max-cron-threads=0','--without-demo=all','-i','step_product_bpa',
            '--test-enable','--test-tags=/step_product_bpa','--stop-after-init','--logfile='+str(log))
        text=log.read_text(errors='replace')
        assert re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',text) and ' ERROR ' not in text,text[-3500:]
        result=run('sudo','-u','postgres','psql','-At','-d',database,'-c',"SELECT json_agg(name ORDER BY name) FROM ir_module_module WHERE state='installed'",text=True,capture_output=True)
        installed=json.loads(result.stdout)
        assert not set(installed)&{'web_enterprise','web_studio','studio_customization'}
        proof={'community_only':True,'versions':{'step_product_bpa':manifest['version']},'database':database,'installed':installed,'tests_passed':True}
        (folder/'passed.json').write_text(json.dumps(proof,indent=2))
        print('BPA_COMMUNITY_ONLY_OK '+json.dumps(proof),flush=True)

if __name__=='__main__':main()
