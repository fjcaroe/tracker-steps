"""Start an accepted private registry with PostgreSQL READ ONLY from connection.

No upgrades, module installation, cron, HTTP, business record access by payload
or production databases. An unsupported readonly startup fails closed. Capture
the complete existing SQL preservation contract on both sides of the process.
"""
import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys

from offline_process import offline_odoo
from validate_community_reports import sql


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('community','cerro-reference'))
    for name in ('accepted-root','payload','output','runtime'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    assert os.geteuid()==0
    root=args.accepted_root.resolve();stage=root/args.mode;out=args.output.resolve();payload=args.payload.resolve()
    assert root.is_relative_to(Path('/opt/steps-validation')) and root.name.startswith('community-multifront-')
    assert out.is_relative_to(Path('/opt/steps-validation')) and not out.is_relative_to(root) and not out.exists()
    assert payload.is_relative_to(Path('/opt/steps-validation')) and payload.name=='original_external_references_registry.py'
    passed=json.loads((stage/'passed.json').read_text())
    pure=args.mode=='community';db=passed['database']
    assert re.fullmatch(('COMMUNITY_PAYROLL_API_' if pure else 'MANAGEMENT_QA_CERRO_PAYROLL_API_')+'[A-Za-z0-9_]+',db)
    assert passed['expected_test_count']==(637 if pure else 437) and not passed['focused_development_pass']
    assert passed['multifront'] and passed['operational_extensions'] and not passed['historical_conversion']
    assert sha(stage/'source-files.json')==passed['source_files_sha256']
    packet=json.loads((stage/'source-files.json').read_text())
    assert all(sha(root/'addons'/name)==digest for name,digest in packet.items())
    config=configparser.ConfigParser(interpolation=None)
    conf=Path('/etc/dev_odoo18.conf' if pure else '/etc/odoo18-cerroelplomo.conf');assert config.read(conf)
    identity=pwd.getpwnam('odoo' if pure else 'cerro_odoo18')
    paths=([str(stage/'consumer-addons')] if pure else [])+[str(stage/'addons'),str(args.runtime/'addons') if pure else config['options']['addons_path']]
    entry=args.runtime/'odoo-bin' if pure else root/'addons/tools/ops/run_agriculture_upgrade.py'
    command=['sudo','-u',identity.pw_name,'env','PGOPTIONS=-c default_transaction_read_only=on','/usr/bin/python3.10',str(entry),'shell',
        '-c',str(conf),'-d',db,'--db-filter=^'+db+'$','--db_host=/var/run/postgresql',
        '--addons-path='+','.join(paths),'--data-dir='+str(stage/'data'),'--load=base,web',
        '--workers=0','--max-cron-threads=0','--no-http','--logfile='+str(out/'registry.log')]
    out.mkdir(mode=0o700);os.chown(out,identity.pw_uid,identity.pw_gid)
    def snapshot():
        # Enumerate actual physical tables instead of assuming native-only
        # fleet/agricultural models exist in an official CE registry.
        tables=sql(db,"SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind IN ('r','p','S') ORDER BY c.relname").splitlines()
        assert all(re.fullmatch('[a-z_][a-z0-9_]*',name) for name in tables)
        queries=["SELECT '"+name+"' name,count(*) rows,md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')) hash FROM public.\""+name+'" t' for name in tables]
        business=json.loads(sql(db,"SET jit=off; SELECT json_object_agg(name,json_build_object('rows',rows,'hash',hash)) FROM ("+' UNION ALL '.join(queries)+') x'))
        return {'physical_tables_and_sequences':len(business),'all_raw_rows_sha256':hashlib.sha256(json.dumps(business,sort_keys=True).encode()).hexdigest()}
    expression="import runpy,json,os; env.cr.execute('SHOW transaction_read_only'); assert env.cr.fetchone()==('on',); p=runpy.run_path("+repr(str(payload))+"); result=p['inspect_registry'](env,source_packet_sha256="+repr(sha(stage/'source-files.json'))+",acceptance_sha256="+repr(sha(stage/'passed.json'))+"); f=os.open("+repr(str(out/'registry.json'))+",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); os.write(f,json.dumps(result,sort_keys=True).encode()); os.close(f); env.cr.rollback()"
    with open('/run/lock/steps-environments.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        before=snapshot()
        with (out/'bootstrap.log').open('w') as log:
            status=subprocess.run(offline_odoo(command),input=expression,text=True,stdout=log,stderr=subprocess.STDOUT)
        after=snapshot();assert after==before,'Readonly registry wrapper changed preserved SQL state'
        receipt={'schema':1,'mode':args.mode,'database':db,'postgres_readonly_from_connection':True,
            'wrapper_loaded_registry':True,'before':before,'after':after,'preservation_exact':True,
            'returncode':status.returncode,'payload_sha256':sha(payload),'acceptance_sha256':sha(stage/'passed.json'),
            'source_packet_sha256':sha(stage/'source-files.json'),'production_changed':False,'adoption_authorized':False}
        (out/'custody.json').write_text(json.dumps(receipt,indent=2));(out/'custody.json').chmod(0o600)
        assert status.returncode==0 and (out/'registry.json').is_file(),'Readonly startup unsupported; inspect private diagnostics without relaxing it'
    print('ORIGINAL_REGISTRY_READONLY_CAPTURED '+args.mode)


if __name__=='__main__':main()
