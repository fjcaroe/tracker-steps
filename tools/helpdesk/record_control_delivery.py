"""Record verified T89 delivery and T90 status, without sending notifications."""
import argparse,hashlib,html,json,xmlrpc.client
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--commit',required=True)
p.add_argument('--ais-verified',action='store_true')
a=p.parse_args()
v=json.loads((a.evidence/'visual-review.json').read_text(encoding='utf-8'))
assert v['commit']==a.commit
for destination in ('development','cerro'):
    assert v[destination]['documents'] and v[destination]['vessels'] and v[destination]['form']
    qa=json.loads((a.evidence/(destination+'-qa.json')).read_text(encoding='utf-8'))
    assert qa['commit']==a.commit and qa['release_sha256']==v['release_sha256']
    log=(a.evidence/(destination+'-deploy.log')).read_text(encoding='utf-8')
    assert a.commit in log and 'MANAGEMENT_DEPLOY_OK backup=' in log and 'MANAGEMENT_VERIFY_OK' in log
for name,sha in v['files'].items():
    assert (a.evidence/name).stat().st_size>0
    assert hashlib.sha256((a.evidence/name).read_bytes()).hexdigest()==sha
assert v['files']
if a.ais_verified:
    assert 'AISSTREAM_LIVE_DATA_VERIFIED' in (a.evidence/'ais-live.log').read_text(encoding='utf-8')
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url=c['url'].rstrip('/')
uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
s=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
def rpc(m,f,args,kw=None):return s.execute_kw(c['db'],uid,c['api_key'],m,f,args,kw or {})
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author=rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
for tid,last,marker in [(89,9471,'Control documental instalado y verificado'),(90,9476,'Panel de naves e integración AISStream')]:
    t=rpc('helpdesk.ticket','read',[[tid]],{'fields':['name','stage_id']})[0]
    assert t['name'].startswith('T'+str(tid))
    recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',tid),('id','>',last),('message_type','in',['comment','email'])]],{'fields':['id','body','author_id','subtype_id']})
    assert all(marker in (m['body'] or '') and m['author_id'] and m['author_id'][0]==author
               and m['subtype_id'] and m['subtype_id'][0]==note for m in recent),'Read newer human replies before recording delivery'
    if tid==89:
        body=('Publicado y verificado en Desarrollo y Cerro El Plomo. Control / Panel de documentos muestra '
            'las doce siglas, plazos configurables, fechas y semáforos. El instructivo tiene Control documentos '
            'sobre su documentación existente, sin duplicar registros. Proforma e Invoice preparan correo con '
            'sus PDF; la factura usa el envío contable nativo. El registro automático exige salida correcta '
            'del correo con adjuntos; impresión, cola y fallos no cuentan como enviados. Se admite fecha y '
            'respaldo manual. Se probaron flujo, permisos y conservación de datos; no se enviaron correos a clientes.')
        stage=4
    else:
        body=('Publicado en Desarrollo y Cerro El Plomo: A dónde va la lancha y Control / Panel de naves, '
            'temporadas, ETD/ETA, Transit time editable, estados, días al arribo/arribado, alertas y mapa '
            'teórico sobre rutas configuradas. Los puertos y naves existentes se conservan. Se implementó '
            'AISStream, proveedor gratuito, con colector del lado servidor, MMSI exacto, fecha de lectura y '
            'distinción entre dato vigente, antiguo y ausente. No se inventan coordenadas ni se asignan naves por nombre. ')
        body+=('La conexión y recepción de datos AIS reales están comprobadas.' if a.ais_verified else
               'Pendiente para cerrar el seguimiento real: autorizar/provisionar la clave de AISStream y comprobar '
               'la recepción real. La integración simulada no se presenta como conexión operativa. Los embarques '
               'deben tener nave/MMSI y rutas/fechas correspondientes para aparecer en sus mapas.')
        stage=4 if a.ais_verified else 2
    existing=[m for m in recent if marker in (m['body'] or '')]
    body_html='<h3>'+marker+'</h3><p>'+html.escape(body)+'</p>'
    message=existing[0]['id'] if existing else rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':tid,
        'message_type':'comment','subtype_id':note,'author_id':author,'partner_ids':[(5,0,0)],
        'body':body_html}])
    if existing and existing[0]['body']!=body_html:
        rpc('mail.message','write',[[message],{'body':body_html}])
    saved=rpc('mail.message','read',[[message]],{'fields':['notification_ids','subtype_id']})[0]
    assert not saved['notification_ids'] and saved['subtype_id'][0]==note
    rpc('helpdesk.ticket','write',[[tid],{'stage_id':stage}],{'context':{'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
    print('CONTROL_DELIVERY_RECORDED ticket='+str(tid)+' stage='+str(stage)+' note='+str(message))
