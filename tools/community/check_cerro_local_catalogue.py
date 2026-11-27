"""Compare every catalogue object on two explicitly named local Cerro databases."""
import json
import sys

import psycopg2
from audit_cerro_original_schema import catalogue,compare,queries

SOURCE='COMMUNITY_CERRO_BOM_CONTRACTS_20261127U44M'
CANDIDATE='COMMUNITY_CERRO_BOM_CONCEPTS_20261127U45P'
PACKING='COMMUNITY_CERRO_BOM_PACKING_20261127U46A'
COLD='COMMUNITY_CERRO_BOM_PACKING_20261127U46B'
OPTS=dict(host='/work/cerro-pg/socket',port=55442,user='postgres')


def capture(before,after):
    result={}
    for part,query in queries().items():
        names,src=catalogue(before,query)
        _,dst=catalogue(after,query)
        report=compare(names,src,dst)
        assert not report['removed'] and not report['changed'],(part,report['removed'][:4],report['changed'][:2])
        result[part]=dict(source=report['source'],target=report['target'],added=report['added'])
    return result


def identities(cr):
    cr.execute("""SELECT count(*),count(*) FILTER (WHERE d.id IS NULL OR
        (s.module,s.name,s.model,s.res_id) IS DISTINCT FROM (d.module,d.name,d.model,d.res_id))
        FROM steps_cerro_studio_guard.original_ids s LEFT JOIN ir_model_data d USING(id)""")
    total,changed=cr.fetchone()
    assert total>62000 and changed==0
    cr.execute("""SELECT count(*) FROM pg_trigger t WHERE NOT t.tgisinternal AND t.tgenabled='O'
        AND (tgname LIKE 'step_anchor_%' OR tgname='steps_cerro_studio_preserve')""")
    guards,=cr.fetchone()
    cr.execute("""SELECT count(*),md5(string_agg(to_jsonb(v)::text,chr(10) ORDER BY v.id))
        FROM ir_ui_view v WHERE v.active AND EXISTS(SELECT FROM ir_model_data d
        WHERE d.module='studio_customization' AND d.model='ir.ui.view' AND d.res_id=v.id)""")
    views,digest=cr.fetchone()
    assert views==23
    cr.execute("""SELECT (SELECT md5(string_agg(to_jsonb(t)::text,chr(10) ORDER BY id)) FROM step_export_payment_concept t),
        (SELECT md5(string_agg((id::text||'|'||step_export_payment_concept_id::text),chr(10) ORDER BY id))
           FROM product_template WHERE step_export_payment_concept_id IS NOT NULL),
        (SELECT md5(string_agg(to_jsonb(a)::text,chr(10) ORDER BY a.id)) FROM ir_model_access a JOIN ir_model m
          ON m.id=a.model_id WHERE m.model='step.export.payment.concept'),
        (SELECT md5(string_agg(to_jsonb(m)::text,chr(10) ORDER BY m.id)) FROM ir_ui_menu m WHERE id IN(982,984,987,1185)),
        (SELECT md5(string_agg(to_jsonb(v)::text,chr(10) ORDER BY v.id)) FROM ir_ui_view v WHERE id IN(4372,4373,4548,4845))""")
    return dict(original_ids=total,guards=guards,studio_views=views,view_digest=digest,concept_digest=cr.fetchone())


def pointers(cr,db,expected=None):
    cr.execute("SELECT current_database(),current_user")
    assert db in (CANDIDATE,PACKING,COLD) and cr.fetchone()==(db,'postgres')
    cr.execute("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()")
    assert cr.fetchone()==(0,)
    cr.execute("SELECT schemaname,sequencename FROM pg_sequences WHERE schemaname='public' ORDER BY 1,2")
    from psycopg2 import sql
    values={}
    for schema,name in cr.fetchall():
        cr.execute(sql.SQL('SELECT last_value,is_called FROM {}').format(sql.Identifier(schema,name)))
        values[name]=list(cr.fetchone())
    if expected is None:
        return values
    assert set(expected)==set(values)
    for k in values:
        if values[k]!=expected[k]:
            cr.execute('SELECT setval(to_regclass(%s),%s,%s)',('public.'+k,*expected[k]))
    return [k for k in values if values[k]!=expected[k]]


def main():
    args=sys.argv[1:]
    source,candidate,expected=SOURCE,CANDIDATE,189
    if '--packing' in args:
        args.remove('--packing')
        source,candidate,expected=CANDIDATE,PACKING,190
    target_opts=OPTS
    if '--cold' in args:
        assert candidate==PACKING
        candidate=COLD
        args.remove('--cold')
        target_opts=dict(host='/dev/shm/steps-cerro-u46/socket',port=55443,user='postgres')
    if args and args[0] in ('sequences','restore-sequences'):
        with psycopg2.connect(dbname=candidate,**target_opts) as cx,cx.cursor() as cr:
            print(json.dumps(pointers(cr,candidate,None if args[0]=='sequences' else json.load(sys.stdin)),sort_keys=True))
        return
    with psycopg2.connect(dbname=source,**OPTS) as src,psycopg2.connect(dbname=candidate,**target_opts) as dst:
        src.set_session(readonly=True,isolation_level='REPEATABLE READ')
        dst.set_session(readonly=True,isolation_level='REPEATABLE READ')
        with src.cursor() as base,dst.cursor() as trial:
            for cr in (base,trial):
                cr.execute('SET LOCAL search_path=pg_catalog,public')
            report=capture(base,trial)
            baseline=identities(base)
            assert identities(trial)==baseline
            if candidate in (PACKING,COLD):
                field_ids=(19699,19701,16810,30763,30892,30891,30890,30889,30888)
                for query in (
                    'SELECT to_jsonb(f) FROM ir_model_fields f WHERE id IN %s ORDER BY id',
                    'SELECT to_jsonb(f) FROM ir_model_fields_selection f WHERE field_id IN %s ORDER BY id',
                ):
                    base.execute(query,(field_ids,))
                    trial.execute(query,(field_ids,))
                    assert base.fetchall()==trial.fetchall(), query
            trial.execute("""SELECT count(*), count(*) FILTER (WHERE license='OEEL-1'),
                count(*) FILTER (WHERE license IS NULL OR license NOT IN
                  ('LGPL-3','AGPL-3','GPL-2','GPL-3','GPL-3 or any later version','GPL-2 or any later version'))
                FROM ir_module_module WHERE state='installed'""")
            census=trial.fetchone()
            assert census==(expected,0,0)
            trial.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
            assert trial.fetchone()==(0,)
            print(json.dumps(dict(schema=report,identities=baseline,census=census),sort_keys=True))


if __name__=='__main__':
    main()
