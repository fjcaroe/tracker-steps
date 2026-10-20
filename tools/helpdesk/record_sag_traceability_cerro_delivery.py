"""Record both approved Cerro deliveries only after exact-copy and live UI evidence."""
import argparse
import hashlib
import html
import json
import re
from pathlib import Path
import xmlrpc.client

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--evidence',type=Path,required=True)
args=parser.parse_args()
proof=json.loads((args.evidence/'cerro-visual-review.json').read_text(encoding='utf-8-sig'))
assert proof['environment']=='cerro'
assert all(proof[k] for k in ('sag_menu','sag_form','sag_services','trace_menu','trace_list'))
for filename in ('development-qa.json','cerro-qa.json'):
    tested=json.loads((args.evidence/filename).read_text(encoding='utf-8-sig'))
    assert tested['commit']==proof['commit'] and tested['release_sha256']==proof['release_sha256']
log=(args.evidence/'cerro-deploy.log').read_text(encoding='utf-8-sig')
assert 'MANAGEMENT_DEPLOY_OK backup=' in log
verified=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('MANAGEMENT_VERIFY_OK ')]
assert any(v['environment']=='cerro' and v['commit']==proof['commit'] for v in verified)
flows=[json.loads(line.split(' ',1)[1]) for line in log.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
assert {v['ticket']:v['cases'] for v in flows}=={93:8,94:3}
for filename in ('development-native.log','cerro-native.log'):
    results=re.findall(r'0 failed, 0 error\(s\) of (\d+) tests when loading database',
        (args.evidence/filename).read_text(encoding='utf-8-sig'))
    assert results and int(results[-1])==proof['test_count']
assert proof['files']
for filename,sha in proof['files'].items():
    assert hashlib.sha256((args.evidence/filename).read_bytes()).hexdigest()==sha

cfg=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url=cfg['url'].rstrip('/')
uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(cfg['db'],cfg['username'],cfg['api_key'],{})
server=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
def rpc(model,method,arguments,keywords=None):
    return server.execute_kw(cfg['db'],uid,cfg['api_key'],model,method,arguments,keywords or {})
author=rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
for ticket_id,approval_id in ((93,9521),(94,9518)):
    ticket=rpc('helpdesk.ticket','read',[[ticket_id]],{'fields':['name']})[0]
    assert ticket['name'].startswith(f'T{ticket_id} ')
    marker=f'T{ticket_id} Actualización aprobada publicada en Cerro El Plomo'
    recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',ticket_id),
        ('id','>',approval_id),('message_type','in',['comment','email'])]],{'fields':['id','body','author_id','subtype_id']})
    assert all(marker in (m['body'] or '') and m['author_id'] and m['author_id'][0]==author
        and m['subtype_id'] and m['subtype_id'][0]==note for m in recent),'Read newer human replies first'
    body=('Se publicó en Cerro El Plomo la aplicación aprobada en Desarrollo, con los mismos archivos y versiones. '
        f'El conjunto pasó {proof["test_count"]} pruebas y 11 comprobaciones funcionales en Desarrollo y en una copia privada de Cerro. '
        'Se respaldó el destino, se conservaron los registros y se verificaron los flujos y la navegación después de actualizar. ')
    if ticket_id==93:
        body+=('Disponible en Packing / Inspecciones / Inspección SAG: lotes de una especie con varias OT/productores, '
            'filtros, lectura de folios, tipos de servicio, cinco archivos SAG y anexos Excel/PDF. '
            'La solicitud y certificación oficiales siguen siendo externas; no se registraron resultados SAG ficticios en los datos operativos.')
    else:
        body+=('Disponible en Exportaciones / Recibidor / Trazabilidad: consulta por folio, siete etapas, '
            'listado exportable y enlaces a procesos/documentos originales. Cerro no tiene tarjas E registradas '
            'en este momento; el listado aparecerá con las tarjas generadas por las operaciones normales, sin datos de prueba permanentes.')
    body='<h3>'+marker+'</h3><p>'+html.escape(body)+'</p>'
    message=recent[0]['id'] if recent else rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':ticket_id,
        'message_type':'comment','subtype_id':note,'author_id':author,'partner_ids':[(5,0,0)],'body':body}])
    assert not rpc('mail.message','read',[[message]],{'fields':['notification_ids']})[0]['notification_ids']
    rpc('helpdesk.ticket','write',[[ticket_id],{'stage_id':4}],{'context':{'tracking_disable':True,'mail_notrack':True,
        'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
    assert rpc('helpdesk.ticket','read',[[ticket_id]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    print(f'T{ticket_id}_CERRO_DELIVERY_RECORDED stage=4 note={message}')
