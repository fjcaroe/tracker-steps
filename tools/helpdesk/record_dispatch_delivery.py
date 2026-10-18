"""Close T91 only with matching copy, publication and visual evidence; no mail."""
import argparse,hashlib,html,json,xmlrpc.client
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence',type=Path,required=True)
a=p.parse_args()
proof=json.loads((a.evidence/'visual-review.json').read_text(encoding='utf-8'))
for target in ('development','cerro'):
    assert all(proof[target][k] for k in ('dispatch_menu','inspections','instruction','guide','packing_list'))
    qa=json.loads((a.evidence/(target+'-qa.json')).read_text(encoding='utf-8'))
    assert qa['commit']==proof['commit'] and qa['release_sha256']==proof['release_sha256']
    log=(a.evidence/(target+'-deploy.log')).read_text(encoding='utf-8')
    assert proof['commit'] in log and 'MANAGEMENT_DEPLOY_OK backup=' in log and 'MANAGEMENT_VERIFY_OK' in log
assert proof['files']
for name,sha in proof['files'].items():
    assert (a.evidence/name).stat().st_size and hashlib.sha256((a.evidence/name).read_bytes()).hexdigest()==sha
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
u=c['url'].rstrip('/');uid=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
s=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/object')
def rpc(m,f,args,kw=None):return s.execute_kw(c['db'],uid,c['api_key'],m,f,args,kw or {})
t=rpc('helpdesk.ticket','read',[[91]],{'fields':['name','stage_id']})[0]
assert t['name'].startswith('T91 ')
author=rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
marker='T91 Despacho de Packing instalado y verificado'
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',91),('id','>',9499),('message_type','in',['comment','email'])]],{'fields':['id','body','author_id','subtype_id']})
assert all(marker in (m['body'] or '') and m['author_id'] and m['author_id'][0]==author and m['subtype_id'] and m['subtype_id'][0]==note for m in recent),'Read newer human replies first'
body=('Publicado en Desarrollo y Cerro El Plomo. Packing / Despacho contiene Instructivo de despacho, Despacho, '
      'Packing List y la función original Traslado lotes. Inspecciones SAG e internas están en Packing / Inspecciones. '
      'El instructivo enlaza el embarque existente y muestra carga, totales y camiones. La guía nativa incorpora '
      'Número instructivo despacho y Folio Pallet: lectura de código, escritura o selección de tarjas vigentes '
      'filtradas por carga, empresa, temporada y especie. Rechaza duplicados entre guías vigentes y exceso de '
      'capacidad. El packing list toma exactamente las tarjas de su guía. Se probaron cálculos, lector, guía '
      'confirmada, packing list, filtros y permisos en copias aisladas; se revisaron formularios y menús en vivo. '
      'Se conservaron los datos anteriores y se respaldó cada destino. No se emitieron DTE ni despachos reales de clientes.')
body='<h3>'+marker+'</h3><p>'+html.escape(body)+'</p>'
existing=[m for m in recent if marker in (m['body'] or '')]
message=existing[0]['id'] if existing else rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':91,
    'message_type':'comment','subtype_id':note,'author_id':author,'partner_ids':[(5,0,0)],'body':body}])
if existing:rpc('mail.message','write',[[message],{'body':body}])
assert not rpc('mail.message','read',[[message]],{'fields':['notification_ids']})[0]['notification_ids']
rpc('helpdesk.ticket','write',[[91],{'stage_id':4}],{'context':{'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
print('T91_DELIVERY_RECORDED stage=4 note='+str(message))
