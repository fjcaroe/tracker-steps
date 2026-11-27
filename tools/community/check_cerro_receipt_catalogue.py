"""Compare Cerro receipt stock, permissions and ORM identity with the 189-module seed and the real SQL catalogue."""
import argparse
import json

import psycopg2
from psycopg2 import sql
from check_cerro_local_catalogue import capture, identities
from check_cerro_pack_schema import TABLES, compare_rows


MODELS = ('stock.picking','stock.move','stock.move.line','stock.quant','stock.quant.package','stock.lot',
          'step.fruit.package.line','step.packing.picking.tag.line','step.packing.production','step.packing.order',
          'step.packing.downtime','step.management.fruit.caliber','step.scale.profile','step.fruit.reception.import',
          'step.harvest.container.transfer','step.harvest.container.transfer.line','res.company','res.config.settings',
          'product.product','product.template','product.packaging')


SEED = 'COMMUNITY_CERRO_BOM_CONCEPTS_20261127U45P'
TRIAL = 'COMMUNITY_CERRO_BOM_PACKING_20261127U46C'
RUNTIME = '/dev/shm/steps-cerro-u46'
FLOW_TABLES = ('stock_move_line','stock_lot','step_harvest_container_transfer','step_harvest_container_transfer_line',
               'step_export_export_stock_quant_package_rel','step_scale_profile','ir_model_access','ir_rule')


def fingerprint(cursor, table):
    cursor.execute(sql.SQL("SELECT count(*),md5(string_agg(v::text,chr(10) ORDER BY v::text)) FROM "
                           "(SELECT to_jsonb(t) v FROM {} t) content").format(sql.Identifier(table)))
    return cursor.fetchone()


def audit(expected, trial=TRIAL):
    assert trial in (TRIAL,'COMMUNITY_CERRO_BOM_PACKING_20261127U46A','COMMUNITY_CERRO_BOM_PACKING_20261127U46D')
    with psycopg2.connect(dbname=SEED,host='/work/cerro-pg/socket',port=55442,user='postgres') as src, \
            psycopg2.connect(dbname=trial,host=RUNTIME+'/socket',port=55443,user='postgres') as dst:
        for connection in (src,dst):
            connection.set_session(readonly=True,isolation_level='REPEATABLE READ')
        with src.cursor() as before,dst.cursor() as after:
            for cursor in (before,after):
                cursor.execute('SET LOCAL search_path=pg_catalog,public')
            schema=capture(before,after)
            assert identities(before)==identities(after)
            tables={}
            for table in (*TABLES,*FLOW_TABLES):
                rows=fingerprint(before,table)
                assert rows==fingerprint(after,table), table
                tables[table]=rows
            fields=compare_rows(before,after,'SELECT id,to_jsonb(f) FROM ir_model_fields f WHERE model IN %s',(MODELS,))
            models=compare_rows(before,after,'SELECT id,to_jsonb(m) FROM ir_model m WHERE model IN %s',(MODELS,))
            selections=compare_rows(before,after,'SELECT s.id,to_jsonb(s) FROM ir_model_fields_selection s JOIN ir_model_fields f '
                                   'ON f.id=s.field_id WHERE f.model IN %s',(MODELS,))
            after.execute("""SELECT count(*), count(*) FILTER (WHERE license NOT IN
                ('LGPL-3','AGPL-3','GPL-2','GPL-3','GPL-2 or any later version','GPL-3 or any later version') OR license IS NULL)
                FROM ir_module_module WHERE state='installed'""")
            assert after.fetchone()==(expected,0)
            after.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
            assert after.fetchone()==(0,)
            if expected==192:
                after.execute("SELECT license FROM ir_module_module WHERE name='step_cerro_receipt_flow'")
                assert after.fetchone()==('AGPL-3',)
            return dict(census=expected,fields=fields,models=models,selections=selections,rows=tables,original_schema=schema)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',type=int,choices=[191,192])
    p.add_argument('--trial',default=TRIAL)
    args=p.parse_args()
    print(json.dumps(audit(args.stage,args.trial),sort_keys=True))
