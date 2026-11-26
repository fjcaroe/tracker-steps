"""Close T240 only after its exact live correction and read-only browser proof.

Does not post a comment or send a message. Credentials and evidence stay private.
Refuses closure if newer ticket messages require review.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--last-reviewed-message', type=int, required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    evidence = args.evidence.resolve()
    assert not evidence.is_relative_to(Path(__file__).resolve().parents[2]), 'Private evidence must be outside Git'
    live = json.loads((evidence/'live-result.json').read_text())
    certificate = json.loads((evidence/'certificate.json').read_text())
    ui = json.loads((evidence/'browser/ui-result.json').read_text())
    result = live['result']
    assert live['identity'] == certificate['identity']
    assert result['rows'] == certificate['tested']['rows']
    assert result['advance_drafts'] == certificate['tested']['advance_drafts']
    assert result['database'] == 'CERRO_EL_PLOMO' and len(result['rows']) == 7
    assert result['native_menu_form_web_read'] and result['historical_rows_preserved']
    assert result['accounting_valuation_notifications_unchanged']
    assert certificate['idempotent']['already_applied'] and not certificate['idempotent']['moves']
    assert ui['nativeForms'] and ui['browserWrites'] == 0 and not ui['errors']
    assert len(ui['tags']) == 7 and ui['advanceDrafts'] == 2 and ui['receipts'] == 2
    assert {r['id']:r['kilos'] for r in ui['tags']} == {r['package_id']:r['kilos'] for r in result['rows']}
    config = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = config.get('url','https://soporte.stepsapp.cl').rstrip('/')
    assert url.startswith('https://')
    uid = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(
        config['db'], config['username'], config['api_key'], {})
    assert uid
    rpc = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')

    def call(model, method, args, kwargs=None):
        return rpc.execute_kw(config['db'],uid,config['api_key'],model,method,args,kwargs or {})

    domain = [('model','=','helpdesk.ticket'),('res_id','=',240)]
    messages = call('mail.message','search_read',[domain], {'fields':['id'],'order':'id'})
    assert max(m['id'] for m in messages) == args.last_reviewed_message, 'Review newer ticket responses before closure'
    before = call('helpdesk.ticket','read',[[240]],{'fields':['id','name','stage_id','team_id','priority']})[0]
    assert before['team_id'][0] == 2 and before['stage_id'][0] in (1,2,4,7)
    solved = call('helpdesk.stage','read',[[4]],{'fields':['id','name','fold','team_ids']})[0]
    assert solved['fold'] and 2 in solved['team_ids']
    if args.apply and before['stage_id'][0] != 4:
        call('helpdesk.ticket','write',[[240],{'stage_id':4}],{'context':{
            'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,
            'mail_auto_subscribe_no_notify':True,'mail_notify_force_send':False}})
    after = call('helpdesk.ticket','read',[[240]],{'fields':['id','stage_id']})[0]
    if args.apply:
        assert after['stage_id'][0] == 4
        after_messages = call('mail.message','search_read',[domain],{'fields':['id'],'order':'id'})
        assert messages == after_messages, 'Unexpected ticket notification; inspect before reporting'
    proof = {'ticket':240,'before':before,'after':after,'applied':args.apply,
             'last_reviewed_message':args.last_reviewed_message,'comment_posted':False,
             'verified_at':datetime.now(timezone.utc).isoformat()}
    (evidence/'ticket-closure.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    print('T240_CLOSURE_OK '+json.dumps({'stage':after['stage_id'],'applied':args.apply,'comment_posted':False}))


if __name__ == '__main__':
    main()
