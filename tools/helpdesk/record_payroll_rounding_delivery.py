"""Record T113 silently only after three-target release and private EMCA QA."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args = parser.parse_args()
    reviewed = json.loads((args.evidence/'delivery-reviewed.json').read_text())
    assert 'PAYROLL_ROUNDING_CASES_OK' in (args.evidence/'emca-cases.log').read_text(encoding='utf-8-sig')
    for target in ('development','sys','cerro'):
        proof = json.loads((args.evidence/(target+'-qa.json')).read_text())
        log = (args.evidence/(target+'-deploy.log')).read_text(encoding='utf-8-sig')
        assert proof['commit']==reviewed['commit'] and proof['release_sha256']==reviewed['sha256']
        assert all(marker in log for marker in ('MANAGEMENT_DEPLOY_OK backup=', 'MANAGEMENT_VERIFY_OK',reviewed['commit']))
        runtime = [json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in log.splitlines()
                   if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(item.get('ticket')==113 and item.get('existing_profile',1)!=1
                   and item.get('native_payroll_menu_and_form') and item.get('round_before_categories')
                   and item.get('historical_states_unchanged') and item.get('writes') is False
                   for item in runtime)
    c = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
    assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,
             'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,values,kwargs=None):
        return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,values,dict({'context':context},**(kwargs or {})))
    ticket=call('helpdesk.ticket','read',[[113]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0] not in (4,5) and not ticket['sla_ids'] and not ticket['sla_status_ids']
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',113),
        ('id','>',reviewed['reviewed_message_id']),('message_type','in',['comment','email'])]])
    body=('Corregido el redondeo de Nómina Simple Digital en Desarrollo, SyS y Cerro El Plomo. '
          'Desde octubre de 2026, los conceptos se aproximan al peso antes de acumular subtotales, '
          'descuentos y líquido. Los períodos anteriores y las liquidaciones cerradas conservan '
          'su comportamiento e importes guardados. No se recalculó ninguna liquidación real. '
          'Los dos casos de septiembre se ensayaron mediante duplicados en una copia privada de SyS, '
          'con sus indicadores originales: resultados e informe coinciden con el adjunto. '
          'El mismo paquete pasó tres pruebas y controles de preservación en copias de los tres '
          'destinos; se publicó con respaldo y bloqueo compartido y se comprobaron versión, '
          'menú, formulario y cálculo prospectivo con perfiles existentes. Commit: '+reviewed['commit']+
          '; SHA-256: '+reviewed['sha256']+'.')
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':113,'message_type':'comment',
        'subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[113],{'stage_id':4}])
    assert call('helpdesk.ticket','read',[[113]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    for model in ('mail.notification','mail.mail'):
        assert not call(model,'search_count',[[('mail_message_id','=',message)]])
    print('TICKET_DELIVERY_RECORDED ticket=113 note=%s stage=4 NO_NOTIFICATIONS_OK'%message)


if __name__=='__main__':
    main()
