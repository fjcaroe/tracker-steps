"""Silent T128/T135 closure after exact-package payroll tests and native flow verification."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('evidence',type=Path);parser.add_argument('--ticket',type=int,choices=(128,135),required=True)
    args=parser.parse_args();root=args.evidence
    expected=json.loads((root/'delivery.json').read_text());expected['reviewed_message_id']=expected['tickets'][str(args.ticket)]
    for target in ('development','sys'):
        proof=json.loads((root/(target+'-qa.json')).read_text())
        deployment=json.loads((root/(target+'-deployment.json')).read_text())
        assert proof['commit']==deployment['commit']==expected['commit']
        assert proof['release_sha256']==deployment['sha256']==expected['sha256']
        assert re.search(r'0 failed, 0 error\(s\) of 13 tests',(root/(target+'-qa.log')).read_text(encoding='utf-8-sig'))
        live=(root/(target+'-live.log')).read_text(encoding='utf-8-sig')
        assert 'MANAGEMENT_VERIFY_OK' in live and expected['commit'] in live
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in live.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(p.get('existing_profile',1)!=1 and p.get('native_forms_and_menu') and p.get('review_action') and p.get('writes') is False for p in payloads)
    assert 'T135_NATIVE_OCTOBER_BATCH_OK employees=2 september_conflicts_preserved=True historical_payslips_unchanged=True rollback_required=True' in (root/'sys-clone-flow.log').read_text(encoding='utf-8-sig')
    bodies={
        128:'T128: el bloqueo por revisión de Simple Digital identifica ahora todos los trabajadores y contratos afectados, indica los parámetros faltantes y explica cómo confirmar la revisión. Se conserva el permiso del responsable y el control de compañía; no se confirmaron contratos ni se recalculó nómina histórica.',
        135:'T135: corregida la validación del período del lote. Los conflictos del 30 de septiembre ya no bloquean octubre; se usa la zona horaria del calendario. Los conflictos reales del mes mantienen su bloqueo y se muestran para todos los trabajadores con horas locales e ID de entrada. En copia de SyS se generó el lote de octubre para los dos trabajadores informados, manteniendo las asistencias de septiembre y los recibos existentes sin cambios. La transacción de prueba se revirtió; no se generaron lotes en producción.'}
    body=(bodies[args.ticket]+' Publicado en Desarrollo y SyS con el mismo paquete probado en copias frescas, respaldo y bloqueo compartido. Trece pruebas por copia y verificación de menú/formularios con usuarios existentes. Commit: '+expected['commit']+'; SHA-256: '+expected['sha256']+'.')
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
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
    related=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',args.ticket)]
    original_messages=set(call('mail.message','search',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket)]]))
    original_delivery={m:set(call(m,'search',[related])) for m in ('mail.notification','mail.mail')}
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':args.ticket,'message_type':'comment',
        'subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[args.ticket],{'stage_id':4}])
    assert call('helpdesk.ticket','read',[[args.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    for model in ('mail.notification','mail.mail'):
        assert not call(model,'search_count',[[('mail_message_id','=',message)]])
    assert set(call('mail.message','search',[[('model','=','helpdesk.ticket'),('res_id','=',args.ticket)]]))==original_messages|{message}
    for model,identifiers in original_delivery.items():
        assert set(call(model,'search',[related]))==identifiers, 'Unexpected stage/template notification'
    print('TICKET_DELIVERY_RECORDED ticket=%s note=%s stage=4 NO_NOTIFICATIONS_OK'%(args.ticket,message))


if __name__=='__main__':main()
