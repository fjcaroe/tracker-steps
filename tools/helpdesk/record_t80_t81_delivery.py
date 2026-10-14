"""Close reviewed shipment tickets only with exact QA/deployment and flow proofs."""
import argparse, html, json, re, xmlrpc.client
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--ticket',type=int,choices=(80,81),required=True)
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--commit',required=True)
a=p.parse_args();assert re.fullmatch('[0-9a-f]{40}',a.commit)
required={80:('menus','forms','new_form_onchange','posting','balanced','three_analytic_plans'),
          81:('menus','forms','shared_folio','invoice_source','documentation','freights','native_pdf','validation_flow')}[a.ticket]
for name,db in (('development','LAB_TAREAS'),('cerro','CERRO_EL_PLOMO')):
    folder=a.evidence/name
    qa=json.loads((folder/'qa_passed.json').read_text(encoding='utf-8'))
    deployment=json.loads((folder/'deployment.json').read_text(encoding='utf-8'))
    assert qa['commit']==deployment['commit']==a.commit
    assert qa['release_sha256']==deployment['sha256']
    rows=[r for r in (folder/('verify-'+db+'.log')).read_text(encoding='utf-8').splitlines() if r.startswith('MANAGEMENT_REGISTRY_OK ')]
    assert len(rows)==1
    flow=json.loads(rows[0].split(' ',1)[1])
    assert flow['ticket']==a.ticket and all(flow[k] for k in required)
if a.ticket==81:
    visual=json.loads((a.evidence/'visual-review.json').read_text(encoding='utf-8'))
    assert visual['inspected'] is True and visual['commit']==a.commit and visual['pages']>=1

c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url=c.get('url','https://soporte.stepsapp.cl').rstrip('/');assert url.startswith('https://')
uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
assert uid
s=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
def rpc(model,method,args,kwargs=None):return s.execute_kw(c['db'],uid,c['api_key'],model,method,args,kwargs or {})
marker='T%s - entrega verificada de embarques'%a.ticket
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',a.ticket),('message_type','in',['comment','email']),('id','>',9415)]],{'fields':['id','body']})
assert not [m for m in recent if marker not in (m.get('body') or '')], 'Revisar respuestas nuevas antes del cierre'
ticket=rpc('helpdesk.ticket','read',[[a.ticket]],{'fields':['name','stage_id']})[0]
assert ticket['name'].startswith('T'+str(a.ticket)) and ticket['stage_id'][0] in (1,2,4)
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author=rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
texts={80:'Corregido en Desarrollo y Cerro El Plomo el error al pulsar Nuevo en Provisión gastos embarques. Se comprobó la apertura del formulario y el flujo de validar, costear y contabilizar con un usuario de operación/contabilidad, conservando el asiento balanceado y las dimensiones analíticas.',
81:'Publicado en Desarrollo y Cerro El Plomo. Instructivo incorpora Pago flete, Booking, variedad, marca, calibre y calidad; condiciones y coordinación de carga en Notas; Seguimiento de documentos con originales, copias, instrucciones y estado; y desglose de Fletes usando conceptos existentes. En Imprimir está disponible el Instructivo de embarque, con datos de empresa, consignatario y notify, carga, transporte, observaciones, fletes y documentación.'}
body='<h3>'+html.escape(marker)+'</h3><p>'+html.escape(texts[a.ticket])+'</p>'
if a.ticket==81:
    body+='<p>Configuraciones / Folios de exportación permite mantener Folios por documento o seleccionar Folio comercial único y Número inicial por empresa. En ese modo se ingresa manualmente el folio en la nota de venta y se elige esa nota en el nuevo instructivo: Nota de venta, Proforma/Invoice comercial, instructivo y embarque usan el mismo folio. Se conservan la numeración histórica y el número del documento contable. El folio vinculado queda protegido.</p>'
body+='<p>Publicado el mismo paquete probado en copias privadas de cada destino, con respaldo y comprobación de versión, menú, formulario, permisos y flujo. Se conservaron los datos anteriores. Las pruebas usaron muestras descartadas.</p>'
body+='<p>Commit '+html.escape(a.commit)+'. <a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T80_T81_IMPLEMENTACION_2026-10-14.rst">Acta técnica</a>.</p>'
old=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',a.ticket),('body','ilike',marker)]],{'fields':['id']})
message=old[0]['id'] if old else rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':a.ticket,'message_type':'comment','subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
saved=rpc('mail.message','read',[[message]],{'fields':['subtype_id','notification_ids']})[0]
assert saved['subtype_id'][0]==note and not saved['notification_ids']
context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}
rpc('helpdesk.ticket','write',[[a.ticket],{'stage_id':4}],{'context':context})
assert rpc('helpdesk.ticket','read',[[a.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
print('TICKET_DELIVERY_OK',a.ticket,'note',message,'notifications=0')
