"""Compare the complete original Cerro catalogue, contact/accounting metadata, and balances before and after follow-up."""
import argparse
import json

import psycopg2

from check_cerro_local_catalogue import capture, identities
from check_cerro_pack_schema import compare_rows
from check_cerro_receipt_catalogue import FLOW_TABLES, MODELS, TABLES, fingerprint

SEED='COMMUNITY_CERRO_BOM_PACKING_20261127U46D'
TRIALS=('COMMUNITY_CERRO_BOM_PACKING_20261127U46C','COMMUNITY_CERRO_BOM_PACKING_20261127U46A')
ACCOUNT_MODELS=('res.partner','account.move','account.move.line','account.account','account_followup.followup.line')
ACCOUNT_TABLES=('res_partner','account_move','account_move_line','account_account','account_followup_followup_line',
                'account_partial_reconcile','account_full_reconcile','mail_mail','mail_activity','sms_sms','ir_attachment')


def audit(trial,expected=193):
    if trial not in TRIALS or expected not in (192,193):
        raise ValueError('Unexpected Cerro follow-up trial')
    options=dict(user='postgres',port=55443,host='/dev/shm/steps-cerro-u46/socket')
    with psycopg2.connect(dbname=SEED,**options) as source,psycopg2.connect(dbname=trial,**options) as current:
        for connection in (source,current):
            connection.set_session(isolation_level='REPEATABLE READ',readonly=True)
        with source.cursor() as src,current.cursor() as dst:
            for cr in (src,dst):
                cr.execute('SET LOCAL search_path=pg_catalog,public')
            structure=capture(src,dst)
            anchors=identities(src)
            assert identities(dst)==anchors
            counted={}
            for name in dict.fromkeys((*TABLES,*FLOW_TABLES,*ACCOUNT_TABLES)):
                earlier=fingerprint(src,name)
                assert fingerprint(dst,name)==earlier, name
                counted[name]=earlier[0]
            models=tuple(dict.fromkeys((*MODELS,*ACCOUNT_MODELS)))
            model_count=compare_rows(src,dst,'SELECT id,to_jsonb(m) FROM ir_model m WHERE model IN %s',(models,))
            field_count=compare_rows(src,dst,'SELECT id,to_jsonb(f) FROM ir_model_fields f WHERE model IN %s',(models,))
            selection_count=compare_rows(src,dst,'SELECT s.id,to_jsonb(s) FROM ir_model_fields_selection s JOIN ir_model_fields f '
                                         'ON f.id=s.field_id WHERE f.model IN %s',(models,))
            dst.execute("""SELECT count(*),count(*) FILTER(WHERE license NOT IN ('LGPL-3','AGPL-3','GPL-2','GPL-3',
                        'GPL-2 or any later version','GPL-3 or any later version') OR license IS NULL)
                        FROM ir_module_module WHERE state='installed'""")
            assert dst.fetchone()==(expected,0)
            dst.execute("SELECT count(*) FROM ir_module_module WHERE name='step_cerro_contact_followup' AND state='installed'")
            assert dst.fetchone()==(expected-192,)
            dst.execute("SELECT count(*) FROM ir_module_module WHERE state IN ('to install','to upgrade','to remove')")
            assert dst.fetchone()==(0,)
            return dict(schema=structure,anchors=anchors,counts=counted,models=model_count,fields=field_count,selections=selection_count)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trial',choices=TRIALS)
    parser.add_argument('--expected',type=int,choices=(192,193),default=193)
    args=parser.parse_args()
    print(json.dumps(audit(args.trial,args.expected),sort_keys=True))
