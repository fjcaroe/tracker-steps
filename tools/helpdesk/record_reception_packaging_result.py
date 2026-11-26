"""Record verified T241 status without posting comments or sending messages.

Missing references keep the ticket in progress. Evidence and credentials are
private. New responses require review before any status change.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    parser.add_argument('--last-reviewed-message',type=int,required=True)
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args();root=args.evidence.resolve()
    assert not root.is_relative_to(Path(__file__).resolve().parents[2])
    live=json.loads((root/'live.json').read_text())
    certificate=json.loads((root/'certificate.json').read_text())
    ui=json.loads((root/'browser/ui-result.json').read_text())
    result=live['result'];tested=certificate['tested']
    assert live['identity']==certificate['identity']
    for key in ('receipts','tags','drafts','missing_receipts'):
        assert result[key]==tested[key]
    assert result['ticket']==241 and result['database']=='CERRO_EL_PLOMO'
    assert result['stock_quantities_ledger_lots_boxes_preserved']
    assert result['prices_amounts_taxes_exchange_preserved'] and result['notifications_unchanged']
    assert result['native_menu_form_web_read']
    assert certificate['idempotent']['already_applied'] and not certificate['idempotent']['updated_rows']
    assert set(ui['receipts'])=={r['id'] for r in result['receipts']}
    assert ui['transactionallyVerifiedTags']==len(result['tags'])
    assert ui['draftAdvances']==len(result['drafts']) and not ui['browserWrites'] and not ui['errors']
    config=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url=config.get('url','https://soporte.stepsapp.cl').rstrip('/');assert url.startswith('https://')
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(config['db'],config['username'],config['api_key'],{})
    assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    def call(model,method,args,kwargs=None):
        return rpc.execute_kw(config['db'],uid,config['api_key'],model,method,args,kwargs or {})
    domain=[('model','=','helpdesk.ticket'),('res_id','=',241)]
    messages=call('mail.message','search_read',[domain],{'fields':['id'],'order':'id'})
    assert max(m['id'] for m in messages)==args.last_reviewed_message,'Review newer responses'
    before=call('helpdesk.ticket','read',[[241]],{'fields':['id','name','stage_id','team_id','priority']})[0]
    assert before['team_id'][0]==2 and before['stage_id'][0] in (1,2,6,7)
    desired=2 if result['missing_receipts'] else 4
    if args.apply and before['stage_id'][0]!=desired:
        call('helpdesk.ticket','write',[[241],{'stage_id':desired}],{'context':{
            'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,
            'mail_auto_subscribe_no_notify':True,'mail_notify_force_send':False}})
    after=call('helpdesk.ticket','read',[[241]],{'fields':['id','stage_id']})[0]
    if args.apply:
        assert after['stage_id'][0]==desired
        assert messages==call('mail.message','search_read',[domain],{'fields':['id'],'order':'id'})
    proof={'ticket':241,'applied':args.apply,'before':before,'after':after,
           'corrected_receipts':len(result['receipts']),'corrected_tags':len(result['tags']),
           'missing_receipts':result['missing_receipts'],'comment_posted':False,
           'verified_at':datetime.now(timezone.utc).isoformat()}
    (root/'ticket-status.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print('T241_STATUS_OK '+json.dumps({'stage':after['stage_id'],'corrected_receipts':len(result['receipts']),
                                     'missing':result['missing_receipts'],'applied':args.apply}))


if __name__=='__main__':main()
