"""Close T83 only with both destination proofs and inspected native report PDFs."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import xmlrpc.client

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--commit',required=True)
p.add_argument('--last-human-message',type=int,required=True)
a=p.parse_args()
assert re.fullmatch('[0-9a-f]{40}',a.commit)
review=json.loads((a.evidence/'visual-review.json').read_text(encoding='utf-8'))
assert review['commit']==a.commit and review['inspected'] is True
required=('menus','forms','shared_folio','invoice_source','native_pdf','validation_flow',
          'fixed_documentation','fixed_freights','payment_labels','product_layout','critical_fields','legacy_data_preserved')
for name,db in (('development','LAB_TAREAS'),('cerro','CERRO_EL_PLOMO')):
    folder=a.evidence/name
    qa=json.loads((folder/'qa_passed.json').read_text(encoding='utf-8'))
    deployment=json.loads((folder/'deployment.json').read_text(encoding='utf-8'))
    assert qa['commit']==deployment['commit']==a.commit
    assert qa['release_sha256']==deployment['sha256']
    lines=(folder/('verify-'+db+'.log')).read_text(encoding='utf-8').splitlines()
    rows=[line for line in lines if line.startswith('MANAGEMENT_REGISTRY_OK ')]
    assert len(rows)==1
    flow=json.loads(rows[0].split(' ',1)[1])
    assert flow['ticket']==83 and all(flow[key] for key in required)
    assert flow['versions']['step_export_shipping_design']=='18.0.1.0.1'
    for filename in ('instruction-preview.pdf','instruction-long-preview.pdf','customer-instruction.pdf'):
        check=review['environments'][name][filename]
        assert check['inspected'] is True and check['section_boundaries'] and check['text_inside_page']
        assert check['pages']>=1 and check['red_characters']>50
        assert check['sha256']==hashlib.sha256((folder/filename).read_bytes()).hexdigest()

c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url=c.get('url','https://soporte.stepsapp.cl').rstrip('/');assert url.startswith('https://')
uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
assert uid
s=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
def rpc(model,method,values,kwargs=None):
    return s.execute_kw(c['db'],uid,c['api_key'],model,method,values,kwargs or {})
marker='T83 - formato de instructivo publicado y verificado'
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',83),
    ('message_type','in',['comment','email']),('id','>',a.last_human_message)]],{'fields':['id','body']})
assert not [m for m in recent if marker not in (m.get('body') or '')], 'Revisar respuestas nuevas antes de cerrar'
ticket=rpc('helpdesk.ticket','read',[[83]],{'fields':['name','stage_id']})[0]
assert ticket['name'].startswith('T83') and ticket['stage_id'][0] in (1,2,4)
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author=rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
body='<h3>'+html.escape(marker)+'</h3>'
body+='<p>Actualizado en Desarrollo y Cerro El Plomo. Las formas de pago son Collect y Prepaid. Producto y carga usa la distribución del adjunto y conserva los campos fundamentales en rojo. Documentación requerida imprime los cinco requisitos fijos, sin Estado ni fechas del seguimiento interno; el seguimiento del formulario se conserva.</p>'
body+='<p>El desglose imprime los trece conceptos de flete en todos los instructivos, incluidos los antiguos sin líneas. Los nuevos completan sus referencias al maestro existente. Completar listado de fletes incorpora las filas que falten a un instructivo anterior sin sobrescribir pagos. Se conservan conceptos adicionales históricos y observaciones.</p>'
body+='<p>Revisados los PDF nativos normales, con varias cargas y observaciones extensas, y de instructivos existentes. Los bloques probados permanecen completos entre páginas, con los colores solicitados. Pasaron siete pruebas en cada copia de destino y la comprobación de menú, formulario, permisos, folios y flujo. Publicado el mismo paquete probado con respaldo y conservación de los registros anteriores.</p>'
body+='<p>Paquete '+html.escape(a.commit)+'. <a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T83_IMPLEMENTACION_2026-10-14.rst">Acta técnica</a>.</p>'
old=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',83),('body','ilike',marker)]],{'fields':['id']})
message=old[0]['id'] if old else rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':83,'message_type':'comment',
    'subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
saved=rpc('mail.message','read',[[message]],{'fields':['subtype_id','notification_ids']})[0]
assert saved['subtype_id'][0]==note and not saved['notification_ids']
context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}
rpc('helpdesk.ticket','write',[[83],{'stage_id':4}],{'context':context})
assert rpc('helpdesk.ticket','read',[[83]],{'fields':['stage_id']})[0]['stage_id'][0]==4
print('TICKET_DELIVERY_OK 83 note',message,'stage=solved notifications=0')
