"""Compare the original receipt identities, full physical catalogue and financial/stock data to the admitted Cerro 193 copy."""
import argparse
import json

import psycopg2

from check_cerro_followup_catalogue import ACCOUNT_MODELS, ACCOUNT_TABLES
from check_cerro_local_catalogue import capture, identities
from check_cerro_pack_schema import compare_rows
from check_cerro_receipt_catalogue import FLOW_TABLES, MODELS, TABLES, fingerprint

SOURCE='COMMUNITY_CERRO_BOM_PACKING_20261127U46A'
CANDIDATE='COMMUNITY_CERRO_BOM_PACKING_20261127U46C'
MODELS_FORM=('quality.alert','quality.point','quality.check','step.dispatch.guide','step.harvest.container.work.order',
             'l10n_latam.document.type','stock.quant.package')
TABLES_FORM=('quality_alert','quality_point','quality_check','step_dispatch_guide','step_dispatch_guide_line',
             'step_harvest_container_work_order','l10n_latam_document_type')


def audit(source,trial):
    assert source == SOURCE and trial in (CANDIDATE, 'COMMUNITY_CERRO_BOM_PACKING_20261127U46E')
    opts=dict(host='/dev/shm/steps-cerro-u46/socket',user='postgres',port=55443)
    with psycopg2.connect(dbname=source,**opts) as before,psycopg2.connect(dbname=trial,**opts) as after:
        for connection in (before,after):
            connection.set_session(isolation_level='REPEATABLE READ',readonly=True)
        with before.cursor() as src,after.cursor() as dst:
            for cr in (src,dst):
                cr.execute('SET LOCAL search_path=pg_catalog,public')
            schema=capture(src,dst)
            anchors=identities(src)
            assert identities(dst)==anchors
            totals={}
            for name in dict.fromkeys((*TABLES,*FLOW_TABLES,*ACCOUNT_TABLES,*TABLES_FORM)):
                frozen=fingerprint(src,name)
                assert fingerprint(dst,name)==frozen,name
                totals[name]=frozen[0]
            models=tuple(dict.fromkeys((*MODELS,*ACCOUNT_MODELS,*MODELS_FORM)))
            model_count=compare_rows(src,dst,'SELECT id,to_jsonb(m) FROM ir_model m WHERE model IN %s',(models,))
            field_count=compare_rows(src,dst,'SELECT id,to_jsonb(f) FROM ir_model_fields f WHERE model IN %s',(models,))
            choices=compare_rows(src,dst,'SELECT s.id,to_jsonb(s) FROM ir_model_fields_selection s JOIN ir_model_fields f ON f.id=s.field_id WHERE f.model IN %s',(models,))
            dst.execute("""SELECT count(*),count(*) FILTER(WHERE license NOT IN ('LGPL-3','AGPL-3','GPL-2','GPL-3',
                'GPL-2 or any later version','GPL-3 or any later version') OR license IS NULL)
                FROM ir_module_module WHERE state='installed'""")
            assert dst.fetchone()==(194,0)
            dst.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
            assert dst.fetchone()==(0,)
            return dict(schema=schema,anchors=anchors,counts=totals,models=model_count,fields=field_count,selections=choices)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',default=SOURCE)
    parser.add_argument('--candidate',default=CANDIDATE)
    args=parser.parse_args()
    print(json.dumps(audit(args.source,args.candidate),sort_keys=True))
