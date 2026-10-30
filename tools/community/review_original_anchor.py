"""Read-only review of a guarded original-cohort trial, never an acceptance flag.

Literal byte hashes remain literal. Any difference is reported as a blocker;
technical additions or numeric representation changes require their own proof.
No production database connection or update operation is provided.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re

import run_original_anchor as anchor
import validate_agriculture_core as preservation
import validate_community_reports as reports
import payroll_configuration_adoption_preflight as gate
from original_anchor_readonly_sql import ReadOnlyReviewSQL


column_snapshot, original_columns = anchor.column_snapshot, anchor.original_columns
sql = reports.sql


@contextmanager
def readonly_bindings(executor):
    """Bind only this isolated review process; always restore real helpers."""
    global sql
    old = [(module, module.sql) for module in (anchor, preservation, reports)]
    original = sql
    try:
        sql = executor
        for module, previous in old:
            module.sql = executor
        yield
    finally:
        sql = original
        for module, previous in old:
            module.sql = previous


def physical_schema(database, tables):
    names=','.join(gate.literal(name) for name in tables)
    query=("SELECT jsonb_build_object('columns',(SELECT jsonb_agg(to_jsonb(x) ORDER BY table_name,column_name) "
        "FROM (SELECT c.relname AS table_name,a.attname AS column_name,format_type(a.atttypid,a.atttypmod) AS sql_type,"
        "a.attnotnull AS not_null,md5(pg_get_expr(d.adbin,d.adrelid)) AS default_md5 FROM pg_attribute a "
        "JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum WHERE n.nspname='public' "
        "AND a.attnum>0 AND NOT a.attisdropped AND c.relname IN ("+names+")) x),"
        "'constraints',(SELECT jsonb_agg(to_jsonb(x) ORDER BY table_name,\"name\") FROM (SELECT c.relname AS table_name,"
        "k.conname AS \"name\",k.contype AS kind,k.convalidated AS \"valid\",md5(pg_get_constraintdef(k.oid)) AS definition_md5 "
        "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
        "WHERE n.nspname='public' AND c.relname IN ("+names+")) x))")
    return json.loads(sql(database,query))


def _compare(stage, database):
    stage = Path(stage).resolve()
    assert re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_[A-Za-z0-9_]+', database)
    plan = json.loads((stage/'handover-plan.json').read_text())
    assert plan['database'] == database and stage.parent.parent == Path('/opt/steps-validation')
    columns = json.loads((stage/'original-columns.json').read_text())
    reference=plan['reference_database']
    assert reference==database.replace('_HANDOVER_','_REFERENCE_')
    # The preserved native control was cloned from the exact fresh restore,
    # before any provider or cohort write. Include the two banking tables
    # covered by the normal acceptance's accelerated snapshot as well.
    bank_columns=original_columns(reference,('res_bank','res_partner_bank'))
    assert not (set(columns)&set(bank_columns))
    columns.update(bank_columns)
    views=json.loads(sql(reference,"SELECT coalesce(json_agg(viewname ORDER BY viewname),'[]'::json) FROM pg_views WHERE schemaname='public'"))
    new_views=sorted(set(views)-set(columns))
    view_columns=original_columns(reference,new_views) if new_views else {}
    columns.update(view_columns)
    actual_columns=original_columns(database, columns)
    before = json.loads((stage/'business-before.json').read_text())
    before.update(column_snapshot(reference,bank_columns))
    if view_columns:before.update(column_snapshot(reference,view_columns))
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
    source_schema=physical_schema(reference,columns)
    target_schema=physical_schema(database,columns)
    schema_differences={}
    for section,key in (('columns','column_name'),('constraints','name')):
        current={(row['table_name'],row[key]):row for row in target_schema[section]}
        schema_differences[section]=[{'before':row,'after':current.get((row['table_name'],row[key]))}
            for row in source_schema[section] if current.get((row['table_name'],row[key]))!=row]
    original_constraint_keys={(row['table_name'],row['name']) for row in source_schema['constraints']}
    added_constraints=[row for row in target_schema['constraints'] if
        (row['table_name'],row['name']) not in original_constraint_keys]
    result={'schema':1,'database':database,'read_only':True,'production_changed':False,
        'original_business_entries':len(before),'literal_business_entries_exact':len(before)-len(changed),
        'business_differences_requiring_review':changed,'original_identity_losses_or_retargets':missing,
        'original_aliases':len(original_aliases),'original_counters':len(counters),
        'counters_exact':counters==original_counters,'new_columns':{
            table:sorted(set(names)-set(columns[table])) for table,names in actual_columns.items()
            if set(names)!=set(columns[table])},
        'all_products_operational':False,'financial_certified':False,'integral_conversion':False,
        'deadline_resolved':False,'acceptance_authorized_by_this_review':False,
        'bank_baseline_from_untouched_same_restore_control':True,
        'extra_original_view_projections_from_same_control':len(view_columns),
        'original_columns_missing_after':{table:sorted(set(names)-set(actual_columns[table]))
            for table,names in columns.items() if not set(names)<=set(actual_columns[table])},
        'history_and_expiration_exact':preservation.history_contract(reference)==preservation.history_contract(database),
        'original_physical_schema_differences_requiring_review':schema_differences,
        'added_constraints_requiring_review':added_constraints,
        'source_dump_sha256':plan['source_dump_sha256']}
    return result


def compare(stage, database):
    stage = Path(stage).resolve()
    plan = json.loads((stage/'handover-plan.json').read_text())
    executor = ReadOnlyReviewSQL(database, plan['reference_database'])
    with readonly_bindings(executor):
        result = _compare(stage, database)
    result['postgresql_readonly_execution'] = executor.proof()
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
