"""Compare original group bindings from the private backup with the tested clone."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

TABLES={'res_groups_users_rel':('gid','uid'),'res_groups_implied_rel':('gid','hid')}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dump',type=Path,required=True);p.add_argument('--database',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert str(a.dump.resolve()).startswith('/opt/steps-validation/') and a.dump.is_file()
    assert str(a.output.resolve()).startswith('/opt/steps-validation/')
    assert re.fullmatch('MANAGEMENT_QA_CERRO_PAYROLL_API_[A-Za-z0-9_]+',a.database)
    reports={}
    for table,columns in TABLES.items():
        text=subprocess.run(['pg_restore','--data-only','--table='+table,'--file=-',str(a.dump)],
            check=True,capture_output=True,text=True).stdout
        match=re.search(r'COPY public\.'+table+r' \(([^)]+)\) FROM stdin;\n(.*?)\n\\\.',text,re.S)
        assert match,'Missing original binding table: '+table
        names=[name.strip().strip('"') for name in match[1].split(',')]
        indexes=[names.index(name) for name in columns]
        original=sorted(tuple(int(values[index]) for index in indexes) for line in match[2].splitlines() if line for values in [line.split('\t')])
        query='SELECT '+','.join(columns)+' FROM '+table+' ORDER BY '+','.join(columns)
        actual=subprocess.run(['sudo','-u','postgres','env','PGOPTIONS=-c default_transaction_read_only=on',
            'psql','-XAt','-v','ON_ERROR_STOP=1','-d',a.database,'-c',query],check=True,capture_output=True,text=True).stdout
        current=sorted(tuple(map(int,line.split('|'))) for line in actual.splitlines() if line)
        reports[table]={'original_rows':len(original),'current_rows':len(current),
            'identical':original==current,'original_sha256':hashlib.sha256(json.dumps(original).encode()).hexdigest(),
            'current_sha256':hashlib.sha256(json.dumps(current).encode()).hexdigest()}
    result={'database':a.database,'read_only':True,'writes_to_source':False,
        'backup_sha256':hashlib.sha256(a.dump.read_bytes()).hexdigest(),
        'verifier_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'bindings':reports}
    a.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    assert all(row['identical'] for row in reports.values()),'Original user/group permissions changed'
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
