"""Validate pinned real OCA payroll in a fresh official Community database only."""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess

PIN='4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e'


def run(*args,**kwargs):
    return subprocess.run(args,check=True,**kwargs)


def git(path,*args):
    return run('git','-C',str(path),*args,text=True,capture_output=True).stdout.strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,required=True)
    parser.add_argument('--oca',type=Path,required=True)
    parser.add_argument('--database',required=True)
    args=parser.parse_args()
    assert os.geteuid()==0
    assert re.fullmatch('COMMUNITY_PAYROLL_CANDIDATE_[A-Za-z0-9_]+',args.database)
    assert str(args.root.resolve()).startswith('/opt/steps-validation/') and not args.root.exists()
    assert git(args.runtime,'remote','get-url','origin')=='https://github.com/odoo/odoo.git'
    assert git(args.oca,'remote','get-url','origin')=='https://github.com/OCA/payroll.git'
    assert git(args.oca,'rev-parse','HEAD')==PIN
    assert not git(args.runtime,'status','--porcelain') and not git(args.oca,'status','--porcelain')
    config=configparser.ConfigParser(interpolation=None);assert config.read('/etc/dev_odoo18.conf')
    args.root.mkdir(mode=0o755)
    data=args.root/'data';data.mkdir()
    run('chown','odoo:odoo',str(data))
    files={str(p.relative_to(args.oca)):hashlib.sha256(p.read_bytes()).hexdigest()
        for name in ('payroll','payroll_account') for p in sorted((args.oca/name).rglob('*'))
        if p.is_file() and '__pycache__' not in p.parts}
    (args.root/'source-files.json').write_text(json.dumps(files,indent=2))
    with open('/run/lock/steps-environments.lock','a') as lock:
        print('PAYROLL_CANDIDATE_WAITING_FOR_SHARED_LEASE',flush=True)
        fcntl.flock(lock,fcntl.LOCK_EX)
        existing=run('sudo','-u','postgres','psql','-XAt','-d','postgres','-c',
            "SELECT 1 FROM pg_database WHERE datname='"+args.database+"'",text=True,capture_output=True).stdout.strip()
        assert not existing
        run('sudo','-u','postgres','createdb','--owner='+config['options']['db_user'],args.database)
        with socket.socket() as listener:
            listener.bind(('127.0.0.1',0));port=listener.getsockname()[1]
        base=['sudo','-u','odoo','/usr/bin/python3.10',str(args.runtime/'odoo-bin')]
        opts=['-c','/etc/dev_odoo18.conf','-d',args.database,
              '--addons-path='+str(args.oca)+','+str(args.runtime/'addons'),'--data-dir='+str(data),
              '--load=base,web','--workers=0','--max-cron-threads=0','--without-demo=all',
              '--http-interface=127.0.0.1','--http-port='+str(port),'--gevent-port=0']
        # Root-owned logs: capture stdout instead of giving Odoo write access to the source evidence.
        with (args.root/'tests.log').open('w') as log:
            status=subprocess.run(base+opts+['-i','payroll_account','--test-enable',
                '--test-tags=/payroll,/payroll_account','--stop-after-init'],stdout=log,stderr=subprocess.STDOUT)
        text=(args.root/'tests.log').read_text(errors='replace')
        assert status.returncode==0 and re.search(r'0 failed, 0 error\(s\) of [1-9][0-9]* tests',text)
        assert not re.search(r' (ERROR|CRITICAL) ',text),'Candidate tests logged errors'
        check=Path(__file__).with_name('verify_payroll_engine.py').read_text()
        native=subprocess.run(base+['shell']+opts+['--no-http','--log-level=critical'],
            input=check,text=True,capture_output=True)
        (args.root/'verify.log').write_text(native.stdout+native.stderr)
        assert native.returncode==0 and 'PAYROLL_ENGINE_NATIVE_OK ' in native.stdout,native.stderr[-3000:]
        evidence=json.loads(next(line.split('PAYROLL_ENGINE_NATIVE_OK ',1)[1] for line in native.stdout.splitlines() if 'PAYROLL_ENGINE_NATIVE_OK ' in line))
        assert not git(args.runtime,'status','--porcelain') and not git(args.oca,'status','--porcelain')
        proof={'database':args.database,'official_community':git(args.runtime,'rev-parse','HEAD'),
            'oca_revision':PIN,'engine_native':evidence,'writes_to_source':False,
            'source_files_sha256':hashlib.sha256((args.root/'source-files.json').read_bytes()).hexdigest(),
            'tests':[line for line in text.splitlines() if 'tests.result' in line],
            'validator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'verifier_sha256':hashlib.sha256(check.encode()).hexdigest()}
        (args.root/'passed.json').write_text(json.dumps(proof,indent=2))
        print('PAYROLL_CANDIDATE_OK '+json.dumps(proof),flush=True)


if __name__=='__main__':main()
