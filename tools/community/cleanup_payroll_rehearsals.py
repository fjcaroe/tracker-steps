"""Apply an explicit retirement plan to owned, inactive payroll rehearsals only."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

BASE=Path('/opt/steps-validation')
DB=re.compile(r'(COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+')


def query(sql):
    return subprocess.run(['sudo','-u','postgres','env','PGOPTIONS=-c default_transaction_read_only=on',
        'psql','-XAt','-v','ON_ERROR_STOP=1','-d','postgres','-c',sql],check=True,capture_output=True,text=True).stdout.strip()


def backup_path(value):
    path=Path(value)
    assert path.is_file() and not path.is_symlink()
    resolved=path.resolve();assert resolved.is_relative_to(BASE)
    assert resolved.name=='source.dump' and resolved.parent.name=='cerro-reference'
    assert re.fullmatch(r'community-(payroll|previred)-[a-zA-Z0-9_-]+',resolved.parent.parent.name)
    return resolved


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan',type=Path,required=True);parser.add_argument('--apply',action='store_true')
    a=parser.parse_args();assert os.geteuid()==0
    assert a.plan.resolve().is_relative_to(BASE)
    plan=json.loads(a.plan.read_text(encoding='utf-8'))
    names=plan['delete_databases'];assert len(names)==len(set(names))
    assert names and all(DB.fullmatch(name) for name in names)
    assert not set(names)&set(plan['keep_databases'])
    keep=[backup_path(value) for value in plan['keep_backups']]
    delete=[backup_path(value) for value in plan['delete_backups']]
    assert keep and not set(keep)&set(delete)
    report={'tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'plan_sha256':hashlib.sha256(a.plan.read_bytes()).hexdigest(),'read_only_production':True,'databases':[],'backups':[],'retained_backups':[],
        'backup_bytes_retired':0,'database_bytes_retired':0,'apply':a.apply}
    output=a.plan.with_name('cleanup-result.json')
    def save():output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    with open('/run/lock/steps-environments.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        for path in keep:
            check=subprocess.run(['pg_restore','--no-owner','--no-acl','--file=/dev/null',str(path)],capture_output=True,text=True)
            assert check.returncode==0,'Retained backup is not completely readable: '+str(path)
            report['retained_backups'].append({'path':str(path),'bytes':path.stat().st_size,
                'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'fully_decoded':True})
        for name in names:
            assert query("SELECT count(*) FROM pg_database WHERE datname='"+name+"'")=='1',name
            assert query("SELECT count(*) FROM pg_stat_activity WHERE datname='"+name+"'")=='0','Active rehearsal: '+name
        save()
        if not a.apply:print(json.dumps(report,indent=2));return
        for name in names:
            size=int(query("SELECT pg_database_size(oid) FROM pg_database WHERE datname='"+name+"'"))
            # dropdb refuses active connections; never terminate sessions or use FORCE.
            try:
                subprocess.run(['sudo','-u','postgres','dropdb',name],check=True,capture_output=True,text=True)
            except subprocess.CalledProcessError as exc:
                report['failure']={'database':name,'exit_code':exc.returncode,'reason':exc.stderr};save()
                raise
            report['databases'].append({'name':name,'bytes':size});report['database_bytes_retired']+=size;save()
        for path in delete:
            size=path.stat().st_size;path.unlink()
            report['backups'].append({'path':str(path),'bytes':size});report['backup_bytes_retired']+=size;save()
        data=Path(query('SHOW data_directory'));stat=os.statvfs(data)
        report['postgres_available_bytes_after']=stat.f_bavail*stat.f_frsize;save()
    print(json.dumps({'retired_databases':len(report['databases']),'retired_backups':len(report['backups']),
        'database_bytes_retired':report['database_bytes_retired'],'backup_bytes_retired':report['backup_bytes_retired'],
        'postgres_available_bytes_after':report['postgres_available_bytes_after']}))


if __name__=='__main__':main()
