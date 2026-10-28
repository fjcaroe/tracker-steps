"""Read-only migration map between private payroll rehearsals. Never a conversion."""
import argparse
import json
from pathlib import Path
import re
import subprocess


SCOPE = "model LIKE 'hr.pay%' OR model LIKE 'hr.salary.%' OR model LIKE 'hr.contract%' OR model LIKE 'hr.work.entry%' OR model LIKE 'step.previred.%' OR model LIKE 'step.remuneration.%'"


def query(database, statement):
    return subprocess.run(['sudo','-u','postgres','env','PGOPTIONS=-c default_transaction_read_only=on',
        'psql','-XAt','-v','ON_ERROR_STOP=1','-d',database,'-c',statement],
        check=True,capture_output=True,text=True).stdout.strip()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--community-db',required=True)
    parser.add_argument('--reference-db',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert re.fullmatch('COMMUNITY_PAYROLL_API_[A-Za-z0-9_]+',args.community_db)
    assert re.fullmatch('MANAGEMENT_QA_CERRO_PAYROLL_API_[A-Za-z0-9_]+',args.reference_db)
    assert str(args.output.resolve()).startswith('/opt/steps-validation/')
    fields={}
    for label,db in [('community',args.community_db),('reference',args.reference_db)]:
        assert query(db,'SHOW default_transaction_read_only')=='on'
        fields[label]=json.loads(query(db,"SELECT coalesce(jsonb_agg(jsonb_build_object('id',id,'model',model,'name',name,'ttype',ttype,'relation',relation,'store',store,'required',required,'modules',modules) ORDER BY model,name),'[]'::jsonb) FROM ir_model_fields WHERE "+SCOPE))
    target={(f['model'],f['name']):f for f in fields['community']}
    differences=[]
    for original in fields['reference']:
        key=(original['model'],original['name']);candidate=target.get(key)
        changed=['missing'] if candidate is None else [attr for attr in ('ttype','relation','store','required') if candidate[attr]!=original[attr]]
        if changed:
            differences.append({'model':key[0],'field':key[1],'source_identity':original,
                'candidate':candidate,'differences':changed,'migration_accepted':False})
    counts={attr:sum(attr in row['differences'] for row in differences) for attr in ('missing','ttype','relation','store','required')}
    vendor=json.loads(query(args.community_db,"SELECT json_build_object('simpledigital_installed',EXISTS(SELECT 1 FROM ir_module_module WHERE name='l10n_cl_simpledigital_payroll' AND state='installed'),'enterprise',count(*) FILTER (WHERE license='OEEL-1' AND state='installed')) FROM ir_module_module"))
    result={'read_only':True,'community':args.community_db,'reference':args.reference_db,
        'source_fields':len(fields['reference']),'candidate_fields':len(fields['community']),
        'counts':counts,'differences':differences,'vendor':vendor,
        'preserve_ids_requires_in_place_adoption':True,'identity_migration_accepted':False,
        'simpledigital_certified':False,'full_cerro_conversion':False}
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='differences'},indent=2))


if __name__=='__main__':main()
