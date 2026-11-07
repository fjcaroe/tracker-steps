"""Run an immutable T175 candidate on an existing disposable Development copy.

This diagnostic does not certify a release. Final QA must restore a fresh copy
from each destination with manage_management before any publication.
"""
import argparse
import configparser
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess

from manage_management import extract, query
import manage_management


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release',type=Path)
    parser.add_argument('--database',required=True)
    parser.add_argument('--scope', choices=('advance','all'), default='advance')
    args=parser.parse_args()
    assert os.geteuid()==0
    assert re.fullmatch('MANAGEMENT_QA_DEVELOPMENT_t175[a-z0-9_]*',args.database)
    assert query(args.database,"SELECT count(*) FROM ir_cron WHERE active")=='0'
    assert query(args.database,"SELECT count(*) FROM ir_mail_server WHERE active")=='0'
    root=Path('/opt/steps-validation/t175-weekly-advances/debug')
    root.mkdir(parents=True,exist_ok=True)
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        manage_management.MODULES=('step_packing_fruit_proforma','step_producer_advances')
        proof=extract(args.release,root/'candidate')
        assert set(proof['versions'])=={'step_packing_fruit_proforma','step_producer_advances'}
        cfg=configparser.ConfigParser(interpolation=None);cfg.read('/etc/dev_odoo18.conf');opts=cfg['options']
        assert opts['db_name']=='LAB_TAREAS'
        user=subprocess.check_output(['systemctl','show','--value','--property=User','odoo18-dev.service'],text=True).strip()
        identity=pwd.getpwnam(user)
        for path in [root,*root.rglob('*')]:os.chown(path,identity.pw_uid,identity.pw_gid)
        installed=set(query(args.database,"SELECT name FROM ir_module_module WHERE state='installed' AND name IN ('step_packing_fruit_proforma','step_producer_advances')").splitlines())
        data=Path('/opt/steps-validation/management_development_'+args.database.removeprefix('MANAGEMENT_QA_DEVELOPMENT_'))/'data'
        assert data.is_dir()
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        command=['sudo','-u',user,'/usr/bin/python3.10','/opt/odoo18/odoo-bin','-c','/etc/dev_odoo18.conf',
            '-d',args.database,'--db-filter=^'+args.database+'$','--http-interface=127.0.0.1',
            '--http-port='+str(port),'--gevent-port=0','--workers=0','--max-cron-threads=0','--without-demo=all',
            '--addons-path='+str(root/'candidate')+','+opts['addons_path'],'--data-dir='+str(data),
            '--test-enable','--test-tags='+('/step_packing_fruit_proforma,/step_producer_advances' if args.scope=='all' else '/step_producer_advances'),'--stop-after-init']
        for flag,names in [('-u',installed),('-i',set(proof['versions'])-installed)]:
            if names:command += [flag,','.join(sorted(names))]
        log=root/(proof['commit']+'.log')
        command += ['--logfile='+str(log)]
        print('T175_DIAGNOSTIC_BEGIN '+str(log),flush=True)
        result=subprocess.run(command)
        text=log.read_text(errors='replace')
        print('\n'.join(line for line in text.splitlines() if ' ERROR ' in line or 'tests.result' in line)[-6000:])
        assert result.returncode==0 and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',text),str(log)
        print('T175_DIAGNOSTIC_OK FRESH_FINAL_QA_REQUIRED',flush=True)


if __name__=='__main__':main()
