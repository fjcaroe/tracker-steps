"""Targeted real-payroll preflight on an already private Cerro diagnostic clone.

Not an acceptance proof: full fresh-clone validation remains mandatory.
"""
import argparse
import fcntl
import os
from pathlib import Path
import pwd
import re
import socket
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--database',required=True)
    parser.add_argument('--data',type=Path,required=True)
    args=parser.parse_args()
    assert os.geteuid()==0 and re.fullmatch('MANAGEMENT_QA_CERRO_AGRICULTURE_HR_[A-Za-z0-9_]+',args.database)
    assert str(args.root.resolve()).startswith('/opt/steps-validation/')
    assert str(args.data.resolve()).startswith('/opt/steps-validation/')
    addons=args.root/'addons';stage=args.root/'payroll-preflight'
    assert not stage.exists() and (addons/'step_labor_payroll_wizards/__manifest__.py').is_file()
    stage.mkdir(mode=0o750)
    identity=pwd.getpwnam('cerro_odoo18');os.chown(stage,identity.pw_uid,identity.pw_gid)
    with open('/run/lock/steps-environments.lock','a') as lock:
        print('PAYROLL_PREFLIGHT_WAITING_FOR_SHARED_LEASE',flush=True)
        fcntl.flock(lock,fcntl.LOCK_EX)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        opts=['-c','/etc/odoo18-cerroelplomo.conf','-d',args.database,'--db-filter=^'+args.database+'$',
              '--data-dir='+str(args.data),'--load=base,web','--workers=0','--max-cron-threads=0',
              '--http-interface=127.0.0.1','--http-port='+str(port),'--gevent-port=0','--without-demo=all']
        # Read the effective source paths without printing credentials/configuration.
        import configparser
        conf=configparser.ConfigParser(interpolation=None);assert conf.read('/etc/odoo18-cerroelplomo.conf')
        opts+=['--addons-path='+str(addons)+','+conf['options']['addons_path']]
        log=stage/'tests.log'
        with (stage/'bootstrap.log').open('w') as stream:
            status=subprocess.run(['sudo','-u','cerro_odoo18','/usr/bin/python3.10',
                str(addons/'tools/ops/run_agriculture_upgrade.py')]+opts+[
                '-u','step_labor_payroll_wizards,step_hr_payroll_bridge','--test-enable',
                '--test-tags=/step_labor_payroll_wizards,/step_hr_payroll_bridge',
                '--logfile='+str(log),'--stop-after-init'],stdout=stream,stderr=subprocess.STDOUT)
        text=log.read_text(errors='replace')
        print('\n'.join(line for line in text.splitlines() if 'tests.result' in line or ' ERROR ' in line or ' CRITICAL ' in line)[-7000:],flush=True)
        assert status.returncode==0 and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',text)
        assert not re.search(r' (ERROR|CRITICAL) ',text)
        print('PAYROLL_PREFLIGHT_OK diagnostic only; fresh full validation still required',flush=True)


if __name__=='__main__':main()
