"""Compare the physical catalogues and permissions of isolated, restored Cerro databases."""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
import json
import os
from pathlib import Path

import psycopg2
from psycopg2 import sql


DATABASES = {
    'native': 'MANAGEMENT_QA_CERRO_CUSTODY_20261126U40Q',
    'library': 'COMMUNITY_LIBRARY_CERRO_20261126U41L',
    '172': 'COMMUNITY_CERRO_BOM_COLD_20261126U42H',
    '187': 'COMMUNITY_CERRO_BOM_QUALIFIED_20261127U43Z',
}
PAIRS = (('native','library'), ('library','172'), ('172','187'), ('library','187'), ('native','187'))
USER_SCHEMAS = "n.nspname !~ '^pg_' AND n.nspname <> 'information_schema'"


def acl(expression):
    """ACLs are sets, whose members contain the grantee, grantor and grant options."""
    return f"ARRAY(SELECT v::text FROM unnest({expression}) v ORDER BY v::text)"


def columns(relation, numbers):
    return (f"ARRAY(SELECT coalesce(a.attname,'<expression>')::text FROM unnest({numbers}) "
            f"WITH ORDINALITY AS keypart(num,pos) LEFT JOIN pg_attribute a ON a.attrelid={relation} "
            "AND a.attnum=keypart.num ORDER BY keypart.pos)")


def queries():
    relation_acl = acl("""coalesce(c.relacl,acldefault(CASE WHEN c.relkind='S'
        THEN 's'::"char" ELSE 'r'::"char" END,c.relowner))""")
    return {
        'database': f"""SELECT ARRAY['database'] AS key, pg_get_userbyid(d.datdba) AS owner,
            {acl("coalesce(d.datacl,acldefault('d',d.datdba))")} AS grants,
            pg_encoding_to_char(d.encoding) AS encoding,d.datcollate AS collation,d.datctype AS char_class,
            t.spcname AS tablespace,d.datconnlimit AS connection_limit
            FROM pg_database d JOIN pg_tablespace t ON t.oid=d.dattablespace WHERE d.datname=current_database()""",
        'schemas': f"""SELECT ARRAY[n.nspname] AS key,pg_get_userbyid(n.nspowner) AS owner,
            {acl("coalesce(n.nspacl,acldefault('n',n.nspowner))")} AS grants
            FROM pg_namespace n WHERE {USER_SCHEMAS}""",
        'relations': f"""SELECT ARRAY[n.nspname,c.relname] AS key,c.relkind AS kind,
            pg_get_userbyid(c.relowner) AS owner,
            {relation_acl} AS grants,
            c.relpersistence AS persistence,c.relrowsecurity AS row_security,c.relforcerowsecurity AS force_row_security,
            c.relispartition AS partition,c.relreplident AS replica_identity,c.reloptions AS options,
            (SELECT s.spcname FROM pg_tablespace s WHERE s.oid=c.reltablespace) AS explicit_tablespace
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE {USER_SCHEMAS} AND c.relkind IN ('r','p','v','m','S','f')""",
        'columns': f"""SELECT ARRAY[n.nspname,c.relname,a.attname] AS key,a.attnum AS position,
            format_type(a.atttypid,a.atttypmod) AS sql_type,a.attnotnull AS not_null,
            a.attndims AS dimensions,a.attidentity AS identity,a.attgenerated AS generated,
            CASE WHEN col.oid IS NOT NULL THEN format('%I.%I',cn.nspname,col.collname) END AS collation,
            md5(pg_get_expr(d.adbin,d.adrelid)) AS default_md5,{acl('a.attacl')} AS grants,
            a.attislocal AS local,a.attinhcount AS inherited
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            JOIN pg_attribute a ON a.attrelid=c.oid
            LEFT JOIN pg_attrdef d ON d.adrelid=a.attrelid AND d.adnum=a.attnum
            LEFT JOIN pg_collation col ON col.oid=a.attcollation LEFT JOIN pg_namespace cn ON cn.oid=col.collnamespace
            WHERE {USER_SCHEMAS} AND c.relkind IN ('r','p','v','m','f')
              AND a.attnum>0 AND NOT a.attisdropped""",
        'constraints': f"""SELECT ARRAY[n.nspname,c.relname,k.conname] AS key,k.contype AS kind,
            {columns('k.conrelid','k.conkey')} AS columns,
            CASE WHEN k.confrelid<>0 THEN k.confrelid::regclass::text END AS referenced_relation,
            {columns('k.confrelid','k.confkey')} AS referenced_columns,
            k.confupdtype AS on_update,k.confdeltype AS on_delete,k.confmatchtype AS match,
            k.convalidated AS validated,k.condeferrable AS deferrable,k.condeferred AS initially_deferred,
            k.connoinherit AS no_inherit,k.conislocal AS local,md5(pg_get_constraintdef(k.oid,false)) AS definition_md5
            FROM pg_constraint k JOIN pg_class c ON c.oid=k.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE {USER_SCHEMAS}""",
        'views': f"""SELECT ARRAY[n.nspname,c.relname] AS key,c.relkind AS kind,
            md5(pg_get_viewdef(c.oid,false)) AS definition_md5, c.relispopulated AS populated
            FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE {USER_SCHEMAS} AND c.relkind IN ('v','m')""",
        'indexes': f"""SELECT ARRAY[n.nspname,c.relname,i.relname] AS key,
            pg_get_userbyid(i.relowner) AS owner, am.amname AS method,
            x.indisunique AS unique,x.indisprimary AS primary,x.indisexclusion AS exclusion,
            x.indisvalid AS valid,x.indisready AS ready,x.indislive AS live,x.indimmediate AS immediate,
            x.indisclustered AS clustered,x.indisreplident AS replica_identity,x.indnkeyatts AS key_count,
            (SELECT s.spcname FROM pg_tablespace s WHERE s.oid=i.reltablespace) AS explicit_tablespace,
            {columns('x.indrelid','x.indkey::smallint[]')} AS columns,
            md5(pg_get_expr(x.indpred,x.indrelid)) AS predicate_md5,md5(pg_get_indexdef(i.oid)) AS definition_md5
            FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid
            JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_am am ON am.oid=i.relam
            WHERE {USER_SCHEMAS}""",
        'sequences': f"""SELECT ARRAY[n.nspname,c.relname] AS key,format_type(q.seqtypid,NULL) AS sql_type,
            q.seqstart AS start_value,q.seqincrement AS increment,q.seqmax AS max_value,q.seqmin AS min_value,
            q.seqcache AS cache,q.seqcycle AS cycle,
            ARRAY(SELECT format('%I.%I.%I',b.nspname,t.relname,a.attname) FROM pg_depend d
                  JOIN pg_class t ON t.oid=d.refobjid JOIN pg_namespace b ON b.oid=t.relnamespace
                  JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=d.refobjsubid
                  WHERE d.classid='pg_class'::regclass AND d.objid=c.oid
                    AND d.refclassid='pg_class'::regclass AND d.deptype IN ('a','i') ORDER BY 1) AS owned_columns
            FROM pg_sequence q JOIN pg_class c ON c.oid=q.seqrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE {USER_SCHEMAS}""",
        'triggers': f"""SELECT ARRAY[n.nspname,c.relname,t.tgname] AS key,t.tgenabled AS enabled,
            md5(pg_get_triggerdef(t.oid,false)) AS definition_md5
            FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE {USER_SCHEMAS} AND NOT t.tgisinternal""",
        'row_policies': f"""SELECT ARRAY[n.nspname,c.relname,p.polname] AS key,p.polcmd AS command,
            p.polpermissive AS permissive,
            ARRAY(SELECT CASE WHEN v=0 THEN 'PUBLIC' ELSE pg_get_userbyid(v)::text END
                  FROM unnest(p.polroles) v ORDER BY 1) AS roles,
            md5(pg_get_expr(p.polqual,c.oid)) AS using_md5,md5(pg_get_expr(p.polwithcheck,c.oid)) AS check_md5
            FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE {USER_SCHEMAS}""",
        'routines': f"""SELECT ARRAY[n.nspname,p.proname,pg_get_function_identity_arguments(p.oid)] AS key,
            p.prokind AS kind,pg_get_userbyid(p.proowner) AS owner,
            {acl("coalesce(p.proacl,acldefault('f',p.proowner))")} AS grants,
            p.prosecdef AS security_definer,p.provolatile AS volatility,
            CASE WHEN p.prokind<>'a' THEN md5(pg_get_functiondef(p.oid)) END AS definition_md5
            FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE {USER_SCHEMAS}""",
        'types': f"""SELECT ARRAY[n.nspname,t.typname] AS key,pg_get_userbyid(t.typowner) AS owner,
            {acl("coalesce(t.typacl,acldefault('T',t.typowner))")} AS grants,t.typtype AS kind,
            t.typnotnull AS not_null,CASE WHEN t.typbasetype<>0 THEN format_type(t.typbasetype,t.typtypmod) END AS base_type,
            md5(t.typdefault) AS default_md5,
            ARRAY(SELECT md5(e.enumlabel) FROM pg_enum e WHERE e.enumtypid=t.oid ORDER BY e.enumsortorder) AS enum_md5
            FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace WHERE {USER_SCHEMAS}""",
        'extensions': """SELECT ARRAY[e.extname::text] AS key,e.extversion AS version,
            pg_get_userbyid(e.extowner) AS owner,n.nspname AS schema FROM pg_extension e
            JOIN pg_namespace n ON n.oid=e.extnamespace""",
        'default_grants': f"""SELECT ARRAY[pg_get_userbyid(d.defaclrole)::text,coalesce(n.nspname::text,'*'),d.defaclobjtype::text] AS key,
            {acl('d.defaclacl')} AS grants FROM pg_default_acl d LEFT JOIN pg_namespace n ON n.oid=d.defaclnamespace
            WHERE n.oid IS NULL OR ({USER_SCHEMAS})""",
        'odoo_access': """SELECT ARRAY[a.id::text] AS key,m.model AS model,a.group_id,a.active,
            a.perm_read,a.perm_write,a.perm_create,a.perm_unlink
            FROM public.ir_model_access a JOIN public.ir_model m ON m.id=a.model_id""",
        'odoo_rules': """SELECT ARRAY[r.id::text] AS key,m.model AS model,r.active,r.global,
            r.perm_read,r.perm_write,r.perm_create,r.perm_unlink,md5(r.domain_force) AS domain_md5,
            ARRAY(SELECT g.group_id FROM public.rule_group_rel g WHERE g.rule_group_id=r.id ORDER BY g.group_id) AS groups
            FROM public.ir_rule r JOIN public.ir_model m ON m.id=r.model_id""",
        'odoo_group_users': """SELECT ARRAY[gid::text,uid::text] AS key,true AS member
            FROM public.res_groups_users_rel""",
        'odoo_field_groups': """SELECT ARRAY[field_id::text,group_id::text] AS key,true AS visible
            FROM public.ir_model_fields_group_rel""",
        'odoo_view_groups': """SELECT ARRAY[view_id::text,group_id::text] AS key,true AS visible
            FROM public.ir_ui_view_group_rel""",
        'odoo_menu_groups': """SELECT ARRAY[menu_id::text,gid::text] AS key,true AS visible
            FROM public.ir_ui_menu_group_rel""",
        'odoo_group_inheritance': """SELECT ARRAY[gid::text,hid::text] AS key, true AS implied
            FROM public.res_groups_implied_rel""",
    }


def catalogue(cursor, query):
    cursor.execute(query)
    fields = [c.name for c in cursor.description][1:]
    rows = {}
    for key, *values in cursor:
        key = tuple(key)
        if key in rows:
            raise ValueError('Ambiguous catalogue key ' + str(key))
        rows[key] = values
    return fields, rows


def compare(fields, left, right):
    changes = []
    for key in sorted(left.keys() & right.keys()):
        if left[key] == right[key]:
            continue
        properties = {field: [a,b] for field,a,b in zip(fields,left[key],right[key]) if a != b}
        changes.append({'key': key, 'properties': properties})
    return {'source':len(left),'target':len(right), 'removed':sorted(left.keys()-right.keys()),
            'added':sorted(right.keys()-left.keys()),'changed':changes}


def count_relaxed_nulls(cursors, comparisons):
    keys = set()
    for sections in comparisons.values():
        for item in sections['columns']['changed']:
            if item['properties'].get('not_null') == [True,False]:
                keys.add(tuple(item['key']))
    tables = {}
    for schema,table,column in sorted(keys):
        tables.setdefault((schema,table),[]).append(column)
    counts = {}
    for name,cursor in cursors.items():
        db = counts[name] = {}
        for (schema,table),columns in tables.items():
            cursor.execute("""SELECT a.attname FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid
                 JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relname=%s
                 AND a.attnum>0 AND NOT a.attisdropped AND a.attname=ANY(%s)""",(schema,table,columns))
            present = {r[0] for r in cursor}
            if not present:
                continue
            original = [n for n in columns if n in present]
            expressions = [sql.SQL('count(*) FILTER (WHERE {} IS NULL)').format(sql.Identifier(n)) for n in original]
            cursor.execute(sql.SQL('SELECT {} FROM {}.{}').format(sql.SQL(',').join(expressions),
                           sql.Identifier(schema),sql.Identifier(table)))
            for col,count in zip(original,cursor.fetchone()):
                db['.'.join((schema,table,col))] = count
    return counts


def capture():
    result = {'databases':DATABASES, 'census':{}, 'snapshots':{}, 'comparisons':{}}
    with ExitStack() as stack:
        cursors={}
        for name,db in DATABASES.items():
            connection = psycopg2.connect(dbname=db,host='/var/run/postgresql',application_name='cerro_schema_readonly')
            stack.callback(connection.close)
            connection.set_session(readonly=True,isolation_level='REPEATABLE READ')
            cursor=connection.cursor()
            stack.callback(cursor.close)
            cursor.execute("SET LOCAL search_path=pg_catalog,public")
            cursor.execute("SET LOCAL statement_timeout='60s'")
            cursor.execute("SELECT current_database(),current_user,current_setting('transaction_read_only')")
            assert cursor.fetchone()==(db,'postgres','on')
            cursor.execute("""SELECT count(*) FILTER (WHERE state='installed'),
                count(*) FILTER (WHERE state='installed' AND license='OEEL-1'),
                count(*) FILTER (WHERE state IN ('to install','to upgrade','to remove')) FROM public.ir_module_module""")
            result['census'][name]=cursor.fetchone()
            cursors[name]=cursor
        for section,query in queries().items():
            snapshots={}
            for name,cursor in cursors.items():
                fields,rows=catalogue(cursor,query)
                packed=json.dumps(sorted(rows.items()),ensure_ascii=True,separators=(',',':')).encode()
                result['snapshots'].setdefault(name,{})[section]={'count':len(rows),'sha256':hashlib.sha256(packed).hexdigest()}
                snapshots[name]=rows
            for a,b in PAIRS:
                result['comparisons'].setdefault(a+'_'+b,{})[section]=compare(fields,snapshots[a],snapshots[b])
        result['null_counts_for_relaxed_fields']=count_relaxed_nulls(cursors,result['comparisons'])
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    os.umask(0o077)
    with open('/run/lock/steps-environments.lock','rb') as gate:
        fcntl.flock(gate,fcntl.LOCK_SH)
        result=capture()
        data=(json.dumps(result,sort_keys=True,separators=(',',':'))+'\n').encode()
        with args.output.open('xb') as target:
            target.write(data)
        print(hashlib.sha256(data).hexdigest())


if __name__=='__main__':
    main()
