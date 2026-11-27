"""Locate changed original rows across the complete Steps backup after adopting Documentos and printing."""
import argparse
from collections import Counter
import fcntl
import gzip
import json
import re

from audit_steps_sales_schema import ANCHOR
from restore_converted_sys_cohort import full_snapshot, verify_same
from restore_native_product_backup import query
from restore_steps_sales_backup import SEALED
from restore_sys_previred_pair import LOCK, require


DESTINATIONS = ('COMMUNITY_STEPS_CRM_DOC_20261127U43X','COMMUNITY_STEPS_CRM_DOC_20261127U44P')
META = {'ir_act_window','ir_act_window_view','ir_cron_trigger','ir_model','ir_model_access','ir_model_constraint',
        'ir_model_data','ir_model_fields','ir_model_fields_selection','ir_module_module','ir_module_module_dependency',
        'ir_rule','ir_ui_menu','ir_ui_view'}
EXTRA_FIELDS = {'step_original_url_hash','step_portal_reference_hash','step_portal_reference_prefix','step_portal_reference_suffix'}
REFLECTED = {
    'ir_model': {'is_mail_activity','is_mail_thread','name','order'},
    'ir_model_fields': {'copied','field_description','help','index','on_delete','readonly','required',
                        'size','tracking','ttype'},
    'ir_model_fields_selection': {'name','sequence'},
    'ir_module_module': {'description','write_date'},
    'ir_ui_menu': {'action','write_date'},
    'ir_ui_view': {'write_date'},
}


def excluded_columns(table, extras):
    names = sorted(key.split('.',1)[1] for key in extras if key.startswith(table+'.'))
    require(all(re.fullmatch('[a-z0-9_]+',name) for name in names),'invalid-column-name')
    return ''.join(" - '"+name+"'" for name in names)


def signatures(db, table, projection):
    require(re.fullmatch('[a-z0-9_]+',table),'invalid-table-name')
    return json.loads(query(db,f"""SET TIME ZONE 'UTC'; SELECT coalesce(json_object_agg(id,
        encode(sha256(convert_to(({projection})::text,'UTF8')),'hex')),'{{}}') FROM ONLY public.{table} r"""))


def selected(db, table, projection, ids):
    if not ids:
        return {}
    pks = ','.join(str(int(pk)) for pk in ids)
    return json.loads(query(db,f"""SET TIME ZONE 'UTC'; SELECT coalesce(json_object_agg(id,({projection})),'{{}}')
        FROM ONLY public.{table} r WHERE id IN ({pks})"""))


def is_generated_asset(row):
    return (row['res_model']=='ir.ui.view' and not row['res_id'] and not row['res_field']
            and row['public'] and re.match(r'^/web/assets/[^/]+/.+\.(?:css|js)$',row.get('url') or '')
            and row['type']=='binary')


def observe(target):
    require(target in DESTINATIONS,'private-documents-target-required')
    frozen = json.loads(gzip.decompress((SEALED/'source-snapshot.json.gz').read_bytes()))
    verify_same(frozen,full_snapshot(ANCHOR))
    current = full_snapshot(target)
    before,after = frozen['public_tables'],current['public_tables']
    require(before.keys()<=after.keys(),'original-table-missing')
    extras = current['columns'].keys()-frozen['columns'].keys()
    changed = {table for table in before if before[table]!=after[table]}
    require(changed<=META|{'ir_attachment','documents_document'},'changed-business-tables-'+str(sorted(changed-META)))
    report = {}
    for table in sorted(changed):
        original = signatures(ANCHOR,table,'to_jsonb(r)')
        projection = 'to_jsonb(r)' + excluded_columns(table, extras)
        updated = signatures(target,table,projection)
        missing = original.keys()-updated.keys()
        require(table=='ir_attachment' or not missing, 'missing-original-'+table)
        if missing:
            require(all(is_generated_asset(row) for row in selected(ANCHOR,table,'to_jsonb(r)',missing).values()),
                    'missing-original-business-attachment')
        altered = {key for key in original.keys() & updated.keys() if original[key]!=updated[key]}
        oldrows = selected(ANCHOR,table,'to_jsonb(r)',altered)
        newrows = selected(target,table,projection,altered)
        by_field = Counter(name for key in altered for name in oldrows[key] if oldrows[key][name]!=newrows[key][name])
        require(by_field.keys()<=REFLECTED.get(table,set()),'changed-original-fields-'+table)
        if table=='ir_attachment':
            additions = updated.keys()-original.keys()
            require(all(is_generated_asset(row) for row in selected(target,table,projection,additions).values()),
                    'unexpected-new-attachment')
        report[table] = {'original':len(original), 'added':len(updated.keys()-original.keys()),
                         'removed':len(missing), 'changed':len(altered), 'changed_columns':dict(sorted(by_field.items()))}
        if table in ('documents_document','ir_model_access','ir_rule','ir_attachment'):
            require(not altered,'original-document-permission-or-attachment-changed')
        if table=='documents_document':
            require(original.keys()==updated.keys()
                    and {name.split('.',1)[1] for name in extras if name.startswith(table+'.')}==EXTRA_FIELDS,
                    'unexpected-document-field')
        if table in ('ir_model','ir_model_fields'):
            report[table]['by_model'] = dict(Counter(row['model'] for row in oldrows.values()))
    return {'source':ANCHOR,'target':target,'unchanged_tables':len(before)-len(changed),'changes':report}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',choices=DESTINATIONS)
    args=parser.parse_args()
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        print(json.dumps(observe(args.target)),flush=True)
