"""Fresh Cerro Odoo copy for existing native models consumed by Web Tracker.

Run as root on odoo-new. No addon install/upgrade and no production writes.
The transient database is neutralized and removed; dump and proof are retained.
"""
import argparse
import configparser
from datetime import datetime,timezone
import fcntl
import json
import os
from pathlib import Path
import subprocess


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    assert os.geteuid()==0;os.umask(0o077)
    source=args.source.resolve();script=source/'tools/qa/tracker/operations-odoo-copy.py';assert script.is_file()
    config=Path('/etc/odoo18-cerroelplomo.conf');cfg=configparser.ConfigParser(interpolation=None);cfg.read(config)
    opts=cfg['options'];assert opts['db_name']=='CERRO_EL_PLOMO'
    def run(*cmd,**kwargs):return subprocess.run([str(x) for x in cmd],check=True,**kwargs)
    def query(db,sql):return subprocess.check_output(['sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-At','-d',db,'-c',sql],text=True).strip()
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=True);root.chmod(0o755)
    commit=subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S');database='TRACKER_OPS_QA_'+stamp
        dump=root/('source-'+stamp+'.dump')
        with dump.open('wb') as output:run('sudo','-u','postgres','pg_dump','-Fc',opts['db_name'],stdout=output)
        run('pg_restore','--file=/dev/null',dump)
        run('sudo','-u','postgres','createdb','-O',opts['db_user'],database)
        try:
            query(database,'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
            with dump.open('rb') as input:run('sudo','-u','postgres','pg_restore','--no-owner','--no-acl','--no-comments','--role',opts['db_user'],'-d',database,stdin=input)
            query(database,'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
            output=root/('functional-'+stamp+'.txt')
            with script.open('rb') as stdin,output.open('wb') as log:
                run('sudo','-u','cerro_odoo18','env','PYTHONPATH=/opt/odoo18','/usr/bin/python3.10','/opt/odoo18/odoo-bin','shell','-c',config,'-d',database,'--db-filter=^'+database+'$','--no-http','--workers=0','--max-cron-threads=0','--logfile=/tmp/'+database+'.log',stdin=stdin,stdout=log,stderr=subprocess.STDOUT)
            assert 'OPERATIONS_ODOO_COPY_OK' in output.read_text(errors='replace'),'Native flow failed; review private log'
            (root/'qa.json').write_text(json.dumps({'commit':commit,'source_database':opts['db_name'],'copy':database,'neutralized':True,'native_models':True,'no_module_changes':True,'functional_log':str(output),'dump':str(dump)},indent=2))
            print('TRACKER_NATIVE_ODOO_COPY_QA_OK',flush=True)
        finally:run('sudo','-u','postgres','dropdb','--if-exists',database)


if __name__=='__main__':main()
