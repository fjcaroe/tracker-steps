"""Apply a private approved product definition after exact-package clone proof.

This targeted operation supports Cerro only; it neither creates inventory nor
refreshes a database. The private plan identifies product_code and the reviewed
compatibility stage/deployment log. No product identifiers belong in Git.
"""
import argparse
import configparser
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import re
import subprocess


def run(*argv,**kw):return subprocess.run(argv,check=True,**kw)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('plan',type=Path);parser.add_argument('evidence',type=Path)
    args=parser.parse_args();plan=json.loads(args.plan.read_text())
    assert re.fullmatch('[A-Za-z0-9_-]+',plan['product_code'])
    stage=Path(plan['compatibility_stage']);qa=json.loads((stage/'qa_passed.json').read_text())
    assert qa['database'].startswith('MANAGEMENT_QA_CERRO_')
    flow=(stage/('verify-'+qa['database']+'.log')).read_text()
    assert 'T137_INVENTORY_DEFINITION_TESTED no_stock_created=True' in flow
    args.evidence.mkdir(mode=0o700,exist_ok=False,parents=True)
    conf=Path('/etc/odoo18-cerroelplomo.conf');c=configparser.ConfigParser();c.read(conf)
    configuration=conf.read_bytes()
    opts=c['options'];assert opts['db_name']=='CERRO_EL_PLOMO' and opts['db_user']=='cerro_odoo18'
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        assert conf.read_bytes()==configuration,'Configuration changed while waiting'
        for entry in Path('/proc').glob('[0-9]*/cmdline'):
            try:argv=entry.read_bytes().decode(errors='replace').split('\0')
            except OSError:continue
            if any(Path(arg).name=='odoo-bin' for arg in argv):
                assert not any(arg in ('-u','-i','--update','--init') or arg.startswith(('--update=','--init=')) for arg in argv),'Concurrent upgrade'
        log=Path(plan['deployment_log']).read_text()
        previous=re.findall(r'MANAGEMENT_DEPLOY_OK backup=(\S+)',log);assert len(previous)==1
        deployed=json.loads((Path(previous[0])/'deployment.json').read_text())
        assert deployed['commit']==qa['commit'] and deployed['sha256']==qa['release_sha256']
        # The live source path must still be the certified immutable overlay.
        assert opts['addons_path'].split(',')[0]=='/opt/steps-managed/releases/cerro/'+qa['commit']
        backup=Path('/opt/steps_backups')/('product_inventory_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
        backup.mkdir(mode=0o700)
        with (backup/'source.dump').open('wb') as out:run('sudo','-u','postgres','pg_dump','-Fc','CERRO_EL_PLOMO',stdout=out)
        with (backup/'source.dump').open('rb') as stream:run('sudo','-u','postgres','pg_restore','--list',stdin=stream,stdout=subprocess.DEVNULL)
        (backup/'odoo.conf').write_bytes(conf.read_bytes())
        here=Path(__file__).resolve().parent
        header='import sys\nsys.path.insert(0,'+repr(str(here))+')\nPLAN='+repr({'database':'CERRO_EL_PLOMO','product_code':plan['product_code']})+'\nCOMMIT=True\n'
        result=subprocess.run(['sudo','-u',opts['db_user'],'/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',str(conf),'-d','CERRO_EL_PLOMO','--no-http','--workers=0','--max-cron-threads=0','--log-level=critical'],input=header+(here/'enable_product_inventory.py').read_text(),text=True,capture_output=True)
        (args.evidence/'live.log').write_text(result.stdout+result.stderr)
        assert result.returncode==0,result.stdout+result.stderr
        lines=[line.split('PRODUCT_INVENTORY_ENABLED_OK ',1)[1] for line in result.stdout.splitlines() if line.startswith('PRODUCT_INVENTORY_ENABLED_OK ')]
        assert len(lines)==1
        proof=json.loads(lines[0]);proof.update(backup=str(backup),commit=qa['commit'],sha256=qa['release_sha256'])
        (args.evidence/'inventory-definition.json').write_text(json.dumps(proof,indent=2))
        print('APPROVED_INVENTORY_DEFINITION_COMPLETE backup='+str(backup))


if __name__=='__main__':main()
