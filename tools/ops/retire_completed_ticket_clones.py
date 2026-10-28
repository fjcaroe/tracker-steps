"""Retire completed private test databases, retaining source dumps and evidence."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import subprocess


def main():
    p=argparse.ArgumentParser();p.add_argument('stages',nargs='+',type=Path);a=p.parse_args()
    with open('/run/lock/steps-environments.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        plans=[]
        for stage in a.stages:
            assert stage.resolve().parent == Path('/opt/steps-validation')
            proof=json.loads((stage/'qa_passed.json').read_text());database=proof['database']
            assert re.fullmatch(r'MANAGEMENT_QA_(DEVELOPMENT|CERRO|QA-CERRO)_t(125hier1|125hierc|125hierq2|126d|126e|126q)',database), 'Only completed T124-T126 copies owned by this task'
            assert (stage/'source.dump').is_file()
            subprocess.run(['pg_restore','--list',str(stage/'source.dump')],check=True,stdout=subprocess.DEVNULL)
            assert 'MANAGEMENT_REGISTRY_OK' in (stage/('verify-'+database+'.log')).read_text()
            count=subprocess.check_output(['sudo','-u','postgres','psql','-At','-d','postgres','-c',"SELECT count(*) FROM pg_stat_activity WHERE datname='"+database+"'"],text=True).strip()
            assert count=='0','Clone still in use'
            plans.append((stage,database))
        for stage,database in plans:
            subprocess.run(['sudo','-u','postgres','dropdb',database],check=True)
            (stage/'clone_retired.json').write_text(json.dumps({'database':database,'source_dump_retained':True,'proof_retained':True}))
            print('COMPLETED_CLONE_RETIRED '+database,flush=True)

if __name__=='__main__':main()
