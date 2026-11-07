"""Mark a reviewed new ticket in progress, silently and without a reply."""
import argparse
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticket',type=int)
    parser.add_argument('--reviewed-message',type=int,required=True)
    args=parser.parse_args()
    config=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(config['db'],config['username'],config['api_key'],{})
    assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,
             'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kwargs=None):
        return rpc.execute_kw(config['db'],uid,config['api_key'],model,method,values,
                              dict({'context':context},**(kwargs or {})))
    ticket=call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0] in (1,2) and not ticket['sla_ids'] and not ticket['sla_status_ids']
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    new=call('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket),('id','>',args.reviewed_message)]],
             {'fields':['id','message_type','attachment_ids']})
    assert not [row['id'] for row in new if row['message_type'] in ('comment','email') or row['attachment_ids']], 'Read new replies first'
    domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',args.ticket)]
    before={name:set(call(name,'search',[domain])) for name in ('mail.notification','mail.mail')}
    call('helpdesk.ticket','write',[[args.ticket],{'stage_id':2}])
    assert call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==2
    for name in before:assert set(call(name,'search',[domain]))==before[name]
    print('TICKET_IN_PROGRESS ticket=%s NO_NOTIFICATIONS_OK'%args.ticket)


if __name__=='__main__':main()
