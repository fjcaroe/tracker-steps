"""Record T117 internally only after immutable-package functional delivery."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args();root=args.evidence
    args.ticket=117
    expected=json.loads((root/'delivery-reviewed.json').read_text())['117']
    for target in ('development','cerro'):
        proof=json.loads((root/(target+'-qa.json')).read_text())
        log=(root/(target+'-deploy.log')).read_text(encoding='utf-8-sig')
        assert proof['commit']==expected['commit'] and proof['release_sha256']==expected['sha256']
        assert all(marker in log for marker in ('MANAGEMENT_DEPLOY_OK backup=','MANAGEMENT_VERIFY_OK',expected['commit']))
        checks=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in log.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(item.get('ticket')==117 and item.get('existing_profile',1)!=1
                   and all(item.get(key) for key in ('native_menu_and_form','two_decimals','native_pallet_weight'))
                   and item.get('writes') is False for item in checks)
    body=('T117 publicado y verificado en Desarrollo y Cerro El Plomo. En Packing / Maestros, '
          'Embalajes incorpora Tara de embalaje y Tipos de pallets muestra Tara de pallet, ambos con dos decimales. '
          'La tara del pallet reutiliza el peso nativo del envase vacío y conserva sus valores anteriores; '
          'no se duplicaron maestros ni relaciones. Las pruebas de edición y persistencia se realizaron '
          'en copias frescas de ambos destinos; se verificaron origen, versión, menú y formulario '
          'con perfiles existentes después de publicar. No se guardaron pruebas en producción. '
          'Publicación del mismo paquete con respaldo y bloqueo. Commit: '+expected['commit']+
          '; SHA-256: '+expected['sha256']+'.')
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url='https://soporte.stepsapp.cl';uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
    assert uid;rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,
             'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kwargs=None):
        return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,values,dict({'context':context},**(kwargs or {})))
    ticket=call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0] not in (4,5) and not ticket['sla_ids'] and not ticket['sla_status_ids']
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket),
        ('id','>',expected['reviewed_message_id']),('message_type','in',['comment','email'])]])
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':args.ticket,'message_type':'comment',
        'subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[args.ticket],{'stage_id':4}])
    assert call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    for model in ('mail.notification','mail.mail'):
        assert not call(model,'search_count',[[('mail_message_id','=',message)]])
    print('TICKET_DELIVERY_RECORDED ticket=%s note=%s stage=4 NO_NOTIFICATIONS_OK'%(args.ticket,message))


if __name__=='__main__':main()
