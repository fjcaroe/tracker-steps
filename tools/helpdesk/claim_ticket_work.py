"""Claim a reviewed waiting Steps ticket silently; never post a message."""
import argparse
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticket',type=int)
    parser.add_argument('--reviewed-message',type=int,required=True)
    args=parser.parse_args()
    cfg=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(cfg['db'],cfg['username'],cfg['api_key'],{})
    assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kw=None):
        return rpc.execute_kw(cfg['db'],uid,cfg['api_key'],model,method,values,dict({'context':context},**(kw or {})))
    ticket=call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0]==6 and not ticket['sla_ids'] and not ticket['sla_status_ids']
    assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket),('id','>',args.reviewed_message),('message_type','in',['comment','email'])]]),'Review recent human replies'
    models=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',models),('active','=',True)]])
    domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',args.ticket)]
    before={model:set(call(model,'search',[domain])) for model in ('mail.notification','mail.mail')}
    call('helpdesk.ticket','write',[[args.ticket],{'stage_id':2}])
    for model,ids in before.items():
        assert set(call(model,'search',[domain]))==ids
    print('TICKET_CLAIMED_SILENTLY ticket='+str(args.ticket))


if __name__=='__main__':main()
