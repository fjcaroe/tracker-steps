"""Classify the actual S7 preservation differences with readonly witnesses.

No difference is accepted here. Original UI memberships, row hashes, cache
metadata and expiration values are compared explicitly; no financial values,
message bodies or attachment content leave PostgreSQL in this report.
"""
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path

from original_anchor_readonly_sql import ReadOnlyReviewSQL
import payroll_configuration_adoption_preflight as gate
import validate_agriculture_core as preservation


HISTORY = ('mail_message', 'mail_tracking_value', 'mail_followers', 'mail_activity', 'ir_attachment')


def require(value, code):
    if not value: raise ValueError(code)


def sha(body): return hashlib.sha256(body).hexdigest()


def canonical(row): return json.dumps(row, sort_keys=True, separators=(',', ':'))


def classify_menu_rows(before, after, original_menu_ids):
    require(all(set(row) == {'menu_id', 'gid'} and all(type(value) is int for value in row.values())
        for row in before + after), 'original-menu-relation-schema-differs')
    left = {canonical(row): row for row in before}; right = {canonical(row): row for row in after}
    require(len(left) == len(before) and len(right) == len(after), 'duplicate-menu-membership')
    missing = [left[key] for key in sorted(left.keys() - right.keys())]
    extra = [right[key] for key in sorted(right.keys() - left.keys())]
    return {'original_rows': len(before), 'current_rows': len(after), 'all_original_pairs_preserved': not missing,
        'missing_original_pairs': missing, 'added_pairs_on_original_menus': [row for row in extra if row['menu_id'] in original_menu_ids],
        'added_pairs_on_new_menus': [row for row in extra if row['menu_id'] not in original_menu_ids],
        'membership_equivalence_inferred': False, 'new_menu_visibility_certified': False,
        'classification_accepted': False}


def classify_history_rows(before, after, changed_columns):
    left = {row['id']: row for row in before}; right = {row['id']: row for row in after}
    require(len(left) == len(before) and len(right) == len(after), 'duplicate-history-identity')
    removed = [left[ident] for ident in sorted(left.keys() - right.keys())]
    added = [right[ident] for ident in sorted(right.keys() - left.keys())]
    changed = []
    for ident in sorted(left.keys() & right.keys()):
        if left[ident]['sha256'] != right[ident]['sha256']:
            old, new = left[ident], right[ident]
            columns = changed_columns[ident]
            cache = old['generated_asset_cache'] and new['generated_asset_cache']
            icon = old['menu_web_icon'] and new['menu_web_icon']
            category = ('generated_asset_cache_candidate' if cache else
                'menu_icon_write_metadata_only' if icon and set(columns) <= {'write_date', 'write_uid'} else
                'menu_icon_content_or_other_metadata_requires_review' if icon else 'original_history_change_blocker')
            changed.append({'id': ident, 'before': old, 'after': new, 'changed_columns': columns, 'classification': category})
    def category(row):
        return ('generated_asset_cache_candidate' if row['generated_asset_cache'] else
            'menu_web_icon_candidate' if row['menu_web_icon'] else 'unclassified_history_row')
    return {'original_rows': len(before), 'current_rows': len(after), 'original_rows_removed': removed,
        'original_rows_changed': changed, 'rows_added': [dict(row, classification=category(row)) for row in added],
        'all_original_rows_literal_exact': not removed and not changed,
        'new_rows_by_classification': dict(Counter(category(row) for row in added)),
        'original_noncache_nonicon_rows_preserved': not any(not (row['generated_asset_cache'] or row['menu_web_icon']) for row in removed)
            and not any(item['classification'] == 'original_history_change_blocker' for item in changed),
        'technical_rows_equivalent_by_classification': False, 'classification_accepted': False}


def menu_snapshot(sql, database):
    return json.loads(sql(database, "SELECT json_build_object('rows',count(*),'hash',md5(coalesce(string_agg(to_jsonb(t)::text,E'\\n' ORDER BY to_jsonb(t)::text),'')),"
        "'data',coalesce(json_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::json)) FROM ir_ui_menu_group_rel t"))


def history_rows(sql, database, table):
    require(table in HISTORY, 'fixed-history-table-required')
    if table == 'ir_attachment':
        asset = 'coalesce(' + preservation.GENERATED_ASSET_CACHE + ',false)'
        icon = "coalesce(t.res_model='ir.ui.menu' AND t.res_field='web_icon_data',false)"
        metadata = "jsonb_build_object('res_model',t.res_model,'res_field',t.res_field,'type',t.type,'mimetype',t.mimetype)"
    else:
        asset, icon, metadata = 'false', 'false', "'{}'::jsonb"
    return json.loads(sql(database, "SELECT coalesce(json_agg(jsonb_build_object('id',t.id,'sha256',encode(sha256(convert_to(to_jsonb(t)::text,'UTF8')),'hex'),"
        "'generated_asset_cache'," + asset + ",'menu_web_icon'," + icon + ",'technical_metadata'," + metadata + ") ORDER BY t.id),'[]'::json) FROM " + gate.identifier(table) + ' t'))


def column_hashes(sql, database, table, ids):
    require(table in HISTORY and ids and all(type(ident) is int and ident > 0 for ident in ids), 'explicit-changed-history-identities-required')
    return json.loads(sql(database, "SELECT coalesce(json_object_agg(id,fields),'{}'::json) FROM (SELECT t.id,"
        "(SELECT jsonb_object_agg(k,encode(sha256(convert_to(v::text,'UTF8')),'hex')) FROM jsonb_each(to_jsonb(t)) x(k,v)) fields "
        'FROM ' + gate.identifier(table) + ' t WHERE id IN (' + ','.join(str(ident) for ident in ids) + ')) q'))


def constraint_catalog(sql, database, keys):
    if not keys: return []
    where = ' OR '.join('(c.relname=' + gate.literal(table) + ' AND k.conname=' + gate.literal(name) + ')' for table, name in sorted(keys))
    query = "SELECT coalesce(json_agg(jsonb_build_object('table_name',c.relname,'name',k.conname,'kind',k.contype,'valid',k.convalidated,"
    query += "'definition',pg_get_constraintdef(k.oid),'columns',(SELECT jsonb_agg(a.attname ORDER BY x.ord) FROM unnest(k.conkey) WITH ORDINALITY x(attnum,ord) "
    query += "JOIN pg_attribute a ON a.attrelid=k.conrelid AND a.attnum=x.attnum),'referenced_schema',rn.nspname,'referenced_table',rc.relname,"
    query += "'referenced_columns',(SELECT jsonb_agg(a.attname ORDER BY x.ord) FROM unnest(k.confkey) WITH ORDINALITY x(attnum,ord) "
    query += "JOIN pg_attribute a ON a.attrelid=k.confrelid AND a.attnum=x.attnum),'on_delete',k.confdeltype,'on_update',k.confupdtype,"
    query += "'match',k.confmatchtype,'deferrable',k.condeferrable,'deferred',k.condeferred) ORDER BY c.relname,k.conname),'[]'::json) "
    query += "FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace "
    query += "LEFT JOIN pg_class rc ON rc.oid=k.confrelid LEFT JOIN pg_namespace rn ON rn.oid=rc.relnamespace "
    query += "WHERE n.nspname='public' AND (" + where + ')'
    return json.loads(sql(database, query))


def classify(stage, review_path):
    stage, review_path = Path(stage).resolve(), Path(review_path).resolve()
    body = review_path.read_bytes(); review = json.loads(body)
    require(review['read_only'] is True and review['acceptance_authorized_by_this_review'] is False,
        'actual-unaccepted-readonly-review-required')
    plan = json.loads((stage / 'handover-plan.json').read_text())
    target, source = review['database'], plan['reference_database']
    require(target == plan['database'], 'exact-reviewed-private-pair-required')
    sql = ReadOnlyReviewSQL(target, source)
    menu_before, menu_after = menu_snapshot(sql, source), menu_snapshot(sql, target)
    delta = review['business_differences_requiring_review'].get('ir_ui_menu_group_rel')
    if delta:
        require({key: menu_before[key] for key in ('rows', 'hash')} == delta['before']
            and {key: menu_after[key] for key in ('rows', 'hash')} == delta['after'], 'menu-state-drifted-since-review')
    original_menu_ids = set(json.loads(sql(source, 'SELECT coalesce(json_agg(id ORDER BY id),\'[]\'::json) FROM ir_ui_menu')))
    menus = classify_menu_rows(menu_before['data'], menu_after['data'], original_menu_ids)
    history = {}
    for table in HISTORY:
        before, after = history_rows(sql, source, table), history_rows(sql, target, table)
        left, right = {r['id']:r for r in before}, {r['id']:r for r in after}
        changed = [ident for ident in left.keys() & right.keys() if left[ident]['sha256'] != right[ident]['sha256']]
        fields = {}
        if changed:
            old, new = column_hashes(sql, source, table, changed), column_hashes(sql, target, table, changed)
            for ident in changed:
                keys = old[str(ident)].keys() | new[str(ident)].keys()
                fields[ident] = sorted(name for name in keys if old[str(ident)].get(name) != new[str(ident)].get(name))
        history[table] = classify_history_rows(before, after, fields)
    expiration_query = "SELECT coalesce(json_object_agg(key,value),'{}'::json) FROM ir_config_parameter WHERE key IN ('database.expiration_date','database.expiration_reason')"
    expiration_before, expiration_after = json.loads(sql(source, expiration_query)), json.loads(sql(target, expiration_query))
    added = {(row['table_name'], row['name']) for row in review['added_constraints_requiring_review']}
    modified = {(row['before']['table_name'], row['before']['name']) for row in review['original_physical_schema_differences_requiring_review']['constraints']}
    catalog = {'source': constraint_catalog(sql, source, added | modified), 'target': constraint_catalog(sql, target, added | modified)}
    actual_added = {(row['table_name'], row['name']) for row in catalog['target']} - {(row['table_name'], row['name']) for row in catalog['source']}
    require(actual_added == added, 'new-constraint-catalog-differs-from-review')
    return {'schema':1,'database':target,'source_database':source,'review_sha256':sha(body),
        'tool_sha256':sha(Path(__file__).read_bytes()),'read_only':True,'database_writes':False,'orm_loaded':False,
        'menus':menus,'history':history,'expiration':{'before':expiration_before,'after':expiration_after,
            'exact':expiration_before == expiration_after,'changed_keys':sorted(k for k in expiration_before.keys() | expiration_after.keys()
                if expiration_before.get(k) != expiration_after.get(k)), 'differences_accepted':False},
        'constraint_catalog':catalog,'added_constraint_keys':sorted([list(row) for row in added]),
        'modified_constraint_keys':sorted([list(row) for row in modified]),
        'constraint_changes_classified_or_accepted':False,'financial_certified':False,'integral_conversion':False,
        'deadline_resolved':False,'acceptance_authorized':False,'postgresql_readonly_execution':sql.proof()}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('stage','review','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    require(not args.output.exists() and args.output.resolve().is_relative_to(Path('/opt/steps-validation')), 'new-private-output-required')
    result=classify(args.stage,args.review)
    with os.fdopen(os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:json.dump(result,stream,indent=2)
    print('S7_PRESERVATION_CLASSIFIED_READONLY',result['menus']['all_original_pairs_preserved'],
        result['expiration']['exact'],'acceptance=False')
