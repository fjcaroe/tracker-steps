"""Close T85/T86 only with matching deployment proofs and completed visual/UI review."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import xmlrpc.client

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence', type=Path, required=True)
p.add_argument('--commit', required=True)
a = p.parse_args()
assert re.fullmatch('[0-9a-f]{40}', a.commit)
review = json.loads((a.evidence/'visual-review.json').read_text(encoding='utf-8'))
assert review['commit'] == a.commit and review['inspected'] and review['ui_development'] and review['ui_cerro']
for name in ('development', 'cerro'):
    folder = a.evidence/('final-'+name)
    qa = json.loads((folder/'qa_passed.json').read_text(encoding='utf-8'))
    assert qa['commit'] == a.commit
    log = (a.evidence/('deploy-'+name+'.log')).read_text(encoding='utf-8')
    assert 'MANAGEMENT_DEPLOY_OK backup=' in log and 'MANAGEMENT_VERIFY_OK' in log and a.commit in log
    assert '"step_export_document_revision": "18.0.1.0.1"' in log
    for filename in ('proforma-preview.pdf','invoice-preview.pdf','packing-preview.pdf','packing-preview.xlsx'):
        assert review['files'][name+'/'+filename] == hashlib.sha256((folder/filename).read_bytes()).hexdigest()

c = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url = c['url'].rstrip('/'); assert url.startswith('https://')
uid = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
s = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
def rpc(model, method, args, kwargs=None):
    return s.execute_kw(c['db'],uid,c['api_key'],model,method,args,kwargs or {})

note = rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author = rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
items = [
    (84,9440,'T85','Packing List disponible y verificado',
     'Disponible en Desarrollo y Cerro El Plomo. Packing List incorpora el encabezado y detalle solicitados y permite imprimir PDF o descargar Excel. '
     'Se reutilizan CSG del productor y fecha/planta de la OT; se agregan CSP al contacto del packing y peso bruto/termos en la tarja. '
     'El formulario usa los kilos reales de sus tarjas. POD y POL se presentan como indica el adjunto, conservando los puertos del embarque. '
     'Pasaron las pruebas del flujo, permisos y conservación de registros en copias de ambos ambientes; se revisaron PDF y Excel. '
     'Cerro no tenía Packing Lists anteriores: se probó un caso completo con reversión, sin crear documentos ficticios en producción.'),
    (85,9437,'T86','Proforma e Invoice comercial disponibles y verificados',
     'Disponible en Desarrollo y Cerro El Plomo. La nota incorpora Precio kg, desmarcado por defecto, y calcula con cajas o kilos según ese criterio. '
     'El embalaje aporta los kg por caja y la unidad se toma del producto. Proforma e Invoice comercial se imprimen en inglés, con el mismo formato y folio. '
     'Imprimirlos no crea una factura contable; esa factura sigue el ciclo estándar. Las notas anteriores conservan sus importes. '
     'Las anteriores sin confirmar pueden usar Aplicar cálculo por cajas, conservando su precio; las confirmadas mantienen su criterio. '
     'Se comprobaron cálculos, descuentos, impuestos, preparación de factura, formularios, permisos y PDF, con respaldo y conservación de registros.')]

for tid, last, prefix, title, text in items:
    marker = prefix+' - '+title
    recent = rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',tid),
        ('message_type','in',['comment','email']),('id','>',last)]],{'fields':['id','body']})
    assert not [m for m in recent if marker not in (m.get('body') or '')], 'Read new human replies before closing'
    ticket = rpc('helpdesk.ticket','read',[[tid]],{'fields':['name','stage_id']})[0]
    assert ticket['name'].startswith(prefix) and ticket['stage_id'][0] in (1,2,4)
    old = rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',tid),('body','ilike',marker)]],{'fields':['id']})
    body = '<h3>'+html.escape(marker)+'</h3><p>'+html.escape(text)+'</p>'
    msg = old[0]['id'] if old else rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':tid,
        'message_type':'comment','subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
    saved = rpc('mail.message','read',[[msg]],{'fields':['subtype_id','notification_ids']})[0]
    assert saved['subtype_id'][0] == note and not saved['notification_ids']
    rpc('helpdesk.ticket','write',[[tid],{'stage_id':4}],{'context':{'tracking_disable':True,'mail_notrack':True,
        'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
    assert rpc('helpdesk.ticket','read',[[tid]],{'fields':['stage_id']})[0]['stage_id'][0] == 4
    print('TICKET_DELIVERY_OK',tid,prefix,'stage=solved internal_note='+str(msg))
