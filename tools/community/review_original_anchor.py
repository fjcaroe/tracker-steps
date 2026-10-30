"""Read-only review of a guarded original-cohort trial, never an acceptance flag.

Literal byte hashes remain literal. Any difference is reported as a blocker;
technical additions or numeric representation changes require their own proof.
No production database connection or update operation is provided.
"""
import argparse
import json
import os
from pathlib import Path
import re

from run_original_anchor import column_snapshot, original_columns
import validate_agriculture_core as preservation
from validate_community_reports import sql
import payroll_configuration_adoption_preflight as gate


def compare(stage, database):
    stage = Path(stage).resolve()
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+', database)
    plan = json.loads((stage/'handover-plan.json').read_text())
    assert plan['database'] == database and stage.parent.parent == Path('/opt/steps-validation')
    columns = json.loads((stage/'original-columns.json').read_text())
    actual_columns=original_columns(database, columns)
    assert all(set(names) <= set(actual_columns[table]) for table,names in columns.items())
    before = json.loads((stage/'business-before.json').read_text())
    after = column_snapshot(database, columns)
    changed = {table:{'before':value,'after':after[table]} for table,value in before.items() if after[table]!=value}
    preservation.MODULES=('step_cosecha','step_labor_operations_core')
    identity = preservation.identity_contract(database)
    source = json.loads((stage/'identity-before.json').read_text())
    missing = {}
    for name in ('ir_model','ir_model_fields','original_xmlids'):
        current={row['id']:row for row in identity[name]}
        keys=('id','module','name','model','res_id','noupdate') if name=='original_xmlids' else (
            ('id','model','state') if name=='ir_model' else ('id','model','name','state'))
        missing[name]=[row['id'] for row in source[name] if row['id'] not in current or
            any(row[key]!=current[row['id']][key] for key in keys)]
    original_counters = json.loads((stage/'counters-before.json').read_text())
    counters={}
    for table in original_counters:
        assert re.fullmatch(r'ir_sequence_[0-9]+(_[0-9]+)?',table)
        counters[table]=json.loads(sql(database,"SELECT json_build_object('rows',1,'hash',to_jsonb(t)::text) FROM "
            +gate.identifier(table)+' t'))
    original_aliases={row['id'] for row in source['original_xmlids']}
    result={'schema':1,'database':database,'read_only':True,'production_changed':False,
        'original_business_entries':len(before),'literal_business_entries_exact':len(before)-len(changed),
        'business_differences_requiring_review':changed,'original_identity_losses_or_retargets':missing,
        'original_aliases':len(original_aliases),'original_counters':len(counters),
        'counters_exact':counters==original_counters,'new_columns':{
            table:sorted(set(names)-set(columns[table])) for table,names in actual_columns.items()
            if set(names)!=set(columns[table])},
        'all_products_operational':False,'financial_certified':False,'integral_conversion':False,
        'deadline_resolved':False,'acceptance_authorized_by_this_review':False,
        'source_dump_sha256':plan['source_dump_sha256']}
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',type=Path,required=True);parser.add_argument('--database',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    assert args.output.resolve().parent == args.stage.resolve() and not args.output.exists()
    result=compare(args.stage,args.database)
    with os.fdopen(os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out:
        json.dump(result,out,indent=2)
    print('ORIGINAL_COHORT_READONLY_REVIEW',result['literal_business_entries_exact'],
        '/',result['original_business_entries'],'literal entries; differences:',
        len(result['business_differences_requiring_review']))
