"""Inspect metadata in an accepted private registry and prove SQL preservation.

Uses no upgrade, HTTP service, business record read, compute, credential output
or Enterprise source export. The two payloads inspect only loaded field/method
metadata. Original business counters and every public table must stay exact.
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

from validate_payroll_relation_storage import connect, snapshot
from offline_process import offline_odoo


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True,help='Already accepted exact-package root')
    parser.add_argument('--mode',choices=('community','cerro-reference'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--runtime',type=Path,required=True)
    args=parser.parse_args()
    assert os.geteuid()==0
    root=args.root.resolve();output=args.output.resolve()
    for path in (root,output):assert Path('/opt/steps-validation') in path.parents
    assert root.is_dir() and not output.exists()
    stage=root/args.mode;source=root/'addons'
    accepted=json.loads((stage/'passed.json').read_text())
    database=accepted['database'];pure=args.mode=='community'
    assert accepted['mode']==args.mode and not accepted['writes_to_source']
    assert re.fullmatch(('COMMUNITY_PAYROLL_API_' if pure else 'MANAGEMENT_QA_CERRO_PAYROLL_API_')+'[A-Za-z0-9_]+',database)
    fp=json.loads((stage/'source-files.json').read_text())
    assert all(hashlib.sha256((source/name).read_bytes()).hexdigest()==digest for name,digest in fp.items())
    config_path='/etc/dev_odoo18.conf' if pure else '/etc/odoo18-cerroelplomo.conf'
    config=configparser.ConfigParser(interpolation=None);assert config.read(config_path)
    user='odoo' if pure else 'cerro_odoo18';identity=pwd.getpwnam(user)
    helpers={name:Path(__file__).with_name(name) for name in (
        'batch_registry_contract.py','caf_registry_contract.py','validate_payroll_relation_storage.py')}
    assert all(path.is_file() for path in helpers.values())
    output.mkdir(mode=0o750);os.chown(output,identity.pw_uid,identity.pw_gid)
    def dump(name,data):(output/(name+'.json')).write_text(json.dumps(data,indent=2))
    def baseline():
        with connect(database) as conn:
            with conn.cursor() as cursor:
                cursor.execute('SET TRANSACTION READ ONLY')
                cursor.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
                assert not cursor.fetchone()[0],'Pending module operations; never start the audit registry'
                values=snapshot(cursor)
        # PostgreSQL registry/cache and serial row-ID sequences are infrastructure,
        # not business numbering. Every original row ID is covered by table hashes.
        return {name:value for name,value in values.items() if 'sequence' not in value or
                re.fullmatch(r'ir_sequence_\d+(?:_\d+)?',name)}
    expression='import runpy,json; env.cr.rollback(); env.cr.execute("SET TRANSACTION READ ONLY"); '
    expression+='reports={"batch":runpy.run_path('+repr(str(helpers['batch_registry_contract.py']))+')["inspect_registry"](env)}; '
    expression+='reports["caf"]=(runpy.run_path('+repr(str(helpers['caf_registry_contract.py']))+')["inspect_registry"](env) '
    expression+='if "l10n_cl.dte.caf" in env.registry.models else {"model_present":False,"transaction_read_only":True,'
    expression+='"orm_records_accessed":False,"payloads_read":False,"provider_methods_called":False,"adoption_ready":False}); '
    if pure:
        expression+='reports["payroll_relations"]=runpy.run_path('+repr(str(helpers['validate_payroll_relation_storage.py']))+')["community_contract"](env.cr); '
    expression+='open('+repr(str(output/'registry.json'))+',"w").write(json.dumps(reports,indent=2)); env.cr.rollback()'
    (output/'payload.py').write_text(expression)
    paths=str(stage/'addons')+','+(str(args.runtime/'addons') if pure else config['options']['addons_path'])
    if pure:paths=str(stage/'consumer-addons')+','+paths
    entry=args.runtime/'odoo-bin' if pure else source/'tools/ops/run_agriculture_upgrade.py'
    command=['sudo','-u',user,'/usr/bin/python3.10',str(entry),'shell','-c',config_path,
        '-d',database,'--db-filter=^'+database+'$','--addons-path='+paths,
        '--db_host=/var/run/postgresql',
        '--data-dir='+str(stage/'data'),'--load=base,web','--workers=0','--max-cron-threads=0',
        '--no-http','--http-interface=127.0.0.1','--http-port=0','--gevent-port=0',
        '--logfile='+str(output/'registry.log')]
    with open('/run/lock/steps-environments.lock','a') as lease:
        fcntl.flock(lease,fcntl.LOCK_EX)
        before=baseline();dump('business-before',before)
        with (output/'bootstrap.log').open('w') as stream:
            status=subprocess.run(offline_odoo(command),input=expression,text=True,stdout=stream,stderr=subprocess.STDOUT)
        after=baseline();dump('business-after',after)
        assert before==after,'Registry inspection changed original table values or business counters'
        assert status.returncode==0 and (output/'registry.json').is_file()
        log=(output/'registry.log').read_text(errors='replace')
        assert not re.search(r' (ERROR|CRITICAL) ',log),'Registry probe failed'
        reports=json.loads((output/'registry.json').read_text())
        assert reports['batch']['read_only'] and not reports['batch']['business_records_read']
        assert reports['caf']['transaction_read_only'] and not any(reports['caf'][key] for key in
            ('orm_records_accessed','payloads_read','provider_methods_called','adoption_ready'))
        if pure:assert reports['payroll_relations']['read_only'] and not reports['payroll_relations']['orm_loaded']
        dump('passed',{'database':database,'mode':args.mode,'exact_tables_and_counters_preserved':len(before),
            'read_only':True,'upgraded':False,'business_records_read':False,'source_bodies_exported':False,
            'functional_conversion_certified':False,'metadata_only':True,
            'external_network_disabled':True,'postgres_unix_socket':True,
            'offline_runner_sha256':hashlib.sha256(Path(__file__).with_name('offline_process.py').read_bytes()).hexdigest(),
            'source_packet_sha256':accepted['source_files_sha256'],
            'runner_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'helpers_sha256':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in helpers.items()}})
    print('ADOPTION_REGISTRY_METADATA_OK '+args.mode)


if __name__=='__main__':main()
