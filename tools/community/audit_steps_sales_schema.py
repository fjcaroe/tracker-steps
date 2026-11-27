"""Verify that installing a Steps sales extension preserves every original column, constraint and SQL definition."""
import argparse
import fcntl
import gzip
import json
import subprocess

from restore_converted_sys_cohort import full_snapshot
from restore_native_product_backup import pg, query
from restore_steps_sales_backup import SEALED
from restore_sys_previred_pair import LOCK, require
from verify_converted_sql_schema import schema


ANCHOR = 'COMMUNITY_STEPS_CRM_RECOVERY_20261127U42T'
TARGETS = ('COMMUNITY_STEPS_CRM_DOC_20261127U43X','COMMUNITY_STEPS_CRM_PRINT_20261127U43Y',
           'COMMUNITY_STEPS_CRM_DOC_20261127U44P','COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H',
           'COMMUNITY_STEPS_CRM_SUPPORT_20261127U44H2')


def objects(db, read_query=query):
    return json.loads(read_query(db,"""SET search_path=pg_catalog,public;
        WITH definitions AS (
            SELECT 'index/'||c.relname AS key, json_build_array(pg_get_indexdef(c.oid),i.indisvalid,i.indisready,
                    i.indislive,i.indisclustered,i.indisreplident,pg_get_userbyid(c.relowner),c.relacl,c.reloptions) AS body
              FROM pg_class c JOIN pg_index i ON i.indexrelid=c.oid WHERE c.relnamespace='public'::regnamespace
            UNION ALL SELECT 'sequence-owner/'||s.relname,json_build_array(t.relname,a.attname,d.deptype)
              FROM pg_class s JOIN pg_depend d ON d.objid=s.oid AND d.classid='pg_class'::regclass
              JOIN pg_class t ON t.oid=d.refobjid AND d.refclassid='pg_class'::regclass
              JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=d.refobjsubid
              WHERE s.relnamespace='public'::regnamespace AND s.relkind='S' AND d.deptype IN ('a','i')
            UNION ALL SELECT 'column-order/'||c.relname||'/'||a.attname,
                    json_build_array(row_number() over (PARTITION BY c.oid ORDER BY a.attnum),
                        col.collnamespace::regnamespace::text,col.collname,a.attacl)
              FROM pg_class c JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped
              LEFT JOIN pg_collation col ON col.oid=a.attcollation
              WHERE c.relnamespace='public'::regnamespace AND c.relkind IN ('r','p')
            UNION ALL SELECT 'view/'||c.relname, json_build_array(c.relkind,pg_get_viewdef(c.oid,false),
                    pg_get_userbyid(c.relowner),c.relacl,c.reloptions)
              FROM pg_class c WHERE c.relkind IN ('v','m') AND c.relnamespace='public'::regnamespace
            UNION ALL SELECT 'rule/'||c.relname||'/'||r.rulename,json_build_array(pg_get_ruledef(r.oid),r.ev_enabled)
              FROM pg_rewrite r JOIN pg_class c ON c.oid=r.ev_class WHERE c.relnamespace='public'::regnamespace
            UNION ALL SELECT 'trigger/'||c.relname||'/'||t.tgname,json_build_array(pg_get_triggerdef(t.oid),t.tgenabled)
              FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
              WHERE c.relnamespace='public'::regnamespace AND NOT t.tgisinternal
            UNION ALL SELECT 'routine/'||p.oid::regprocedure::text,
                    json_build_array(pg_get_functiondef(p.oid),pg_get_userbyid(p.proowner),p.proacl)
              FROM pg_proc p WHERE p.pronamespace='public'::regnamespace AND p.prokind IN ('f','p','w')
        ) SELECT json_object_agg(key,encode(sha256(convert_to(body::text,'UTF8')),'hex')) FROM definitions"""))


def definitions(target, frozen, after):
    require(target in TARGETS,'private-steps-extension-required')
    source_schema = pg('pg_dump','--schema-only','--no-tablespaces',ANCHOR,readonly=True,stdout=subprocess.PIPE).stdout
    expected = json.loads((SEALED.parent/'schema-proof.json').read_bytes())['archive_schema_sha256']
    require(schema(source_schema)==expected, 'original-sales-schema-no-longer-matches-the-archive')
    protected = ('columns','constraints','relation_owner_and_acl','sequence_definitions')
    before = {key:frozen[key] for key in protected}
    current = {key:after[key] for key in protected}
    before['sql_objects'],current['sql_objects'] = objects(ANCHOR),objects(target)
    changes = {section:[name for name,value in items.items() if current[section].get(name)!=value]
               for section,items in before.items()}
    return {'target':target,'schema_changes':changes,
            'retained':{section:len(values)-len(changes[section]) for section,values in before.items()},
            'additions':{section:len(current[section].keys()-values.keys()) for section,values in before.items()}}


def audit(target, frozen, after):
    result = definitions(target, frozen, after)
    counters = []
    for name,(last,called) in frozen['sequence_values'].items():
        value = after['sequence_values'].get(name)
        if value == [last, called]:
            continue
        definition = frozen['sequence_definitions'][name]
        require(value and value[1] and value[0]>=last and definition[4]>0 and not definition[5],
                'original-counter-went-backward-'+name)
        counters.append(name)
    business = ('sale_order','crm_lead','account_move','account_payment','helpdesk_ticket',
                'stock_move','stock_picking','purchase_order','documents_document')
    require(not any(name.startswith(business) for name in counters),'installation-advanced-business-counter')
    return dict(result, advanced_counters=sorted(counters))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('target',choices=TARGETS)
    parser.add_argument('--schema-only',action='store_true',help='Compare definitions after user trials that allocated IDs.')
    args = parser.parse_args()
    with open(LOCK,'rb') as lock:
        fcntl.flock(lock,fcntl.LOCK_SH)
        frozen = json.loads(gzip.decompress((SEALED/'source-snapshot.json.gz').read_bytes()))
        result = (definitions if args.schema_only else audit)(args.target,frozen,full_snapshot(args.target))
    print(json.dumps(result),flush=True)
    if any(result['schema_changes'].values()):
        raise SystemExit(2)
