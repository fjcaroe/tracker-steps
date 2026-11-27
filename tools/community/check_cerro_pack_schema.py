"""Compare all original PostgreSQL objects, security, reporting metadata and native packing rows on A and B."""
import json
import sys

import psycopg2
from psycopg2 import sql
from check_cerro_local_catalogue import capture, identities, pointers


DB='COMMUNITY_CERRO_BOM_PACKING_20261127U46A'
SOURCE='COMMUNITY_CERRO_BOM_PACKING_20261127U46B'
SOCKET='/dev/shm/steps-cerro-u46/socket'
MODELS=('step.packing.production','step.packing.order','step.packing.downtime','step.fruit.package.line','stock.quant.package')
TABLES=('step_packing_production','step_packing_order','step_packing_downtime','step_fruit_package_line','stock_quant_package',
        'step_packing_input_tag_rel','step_packing_output_tag_rel','stock_picking','step_packing_picking_tag_line','stock_quant','stock_move')


def compare_rows(src,dst,query,args=()):
    src.execute(query,args)
    dst.execute(query,args)
    before=dict(src.fetchall())
    after=dict(dst.fetchall())
    faults=[]
    for key,value in before.items():
        if after.get(key)!=value:
            current=after.get(key,{})
            faults.append((key,[field for field in value if current.get(field)!=value[field]]))
    assert not faults, faults[:30]
    return len(before)


def main():
    args=sys.argv[1:]
    database=DB
    if '--final' in args:
        args.remove('--final')
        database='COMMUNITY_CERRO_BOM_PACKING_20261127U46C'
    expected=191
    if '--at190' in args:
        args.remove('--at190')
        expected=190
    opts=dict(host=SOCKET,user='postgres',port=55443)
    if args:
        assert args in (['sequences'],['restore-sequences'])
        with psycopg2.connect(dbname=database,**opts) as conn,conn.cursor() as trial:
            print(json.dumps(pointers(trial,database,None if args[0]=='sequences' else json.load(sys.stdin)),sort_keys=True))
        return
    with psycopg2.connect(dbname=SOURCE,**opts) as source,psycopg2.connect(dbname=database,**opts) as trial:
        with source.cursor() as src,trial.cursor() as dst:
            for cr in (src,dst):
                cr.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
                cr.execute('SET LOCAL search_path=pg_catalog,public')
            schema=capture(src,dst)
            assert identities(src)==identities(dst)
            rows={}
            for table in TABLES:
                query=sql.SQL("SELECT count(*),md5(string_agg(v::text,chr(10) ORDER BY v::text)) FROM (SELECT to_jsonb(t) v FROM {} t) data").format(sql.Identifier(table))
                src.execute(query)
                dst.execute(query)
                original=src.fetchone()
                assert dst.fetchone()==original,table
                rows[table]=original[0]
            models=compare_rows(src,dst,'SELECT id,to_jsonb(m) FROM ir_model m WHERE model IN %s',(MODELS,))
            fields=compare_rows(src,dst,'SELECT id,to_jsonb(f) FROM ir_model_fields f WHERE model IN %s',(MODELS,))
            options=compare_rows(src,dst,"SELECT s.id,to_jsonb(s) FROM ir_model_fields_selection s JOIN ir_model_fields f ON f.id=s.field_id WHERE f.model IN %s",(MODELS,))
            dst.execute("SELECT count(*),count(*) FILTER(WHERE license NOT IN ('LGPL-3','AGPL-3','GPL-2','GPL-3','GPL-3 or any later version','GPL-2 or any later version') OR license IS NULL) FROM ir_module_module WHERE state='installed'")
            assert dst.fetchone()==(expected,0)
            stock_fields=compare_rows(src,dst,"SELECT f.id,to_jsonb(f) FROM ir_model_fields f WHERE f.id=ANY(%s)",([16810,19699,19701,30763,30888,30889,30890,30891,30892],))
            print(json.dumps(dict(module_count=expected,picking_fields=stock_fields,schema=schema,records=rows,fields=fields,models=models,selections=options),sort_keys=True))


if __name__=='__main__':
    main()
