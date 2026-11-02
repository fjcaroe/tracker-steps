"""Internal T46 setup update, not ticket closure or an outgoing message."""
import argparse,json,html
from pathlib import Path
import xmlrpc.client
p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);a=p.parse_args()
assert '187 passed' in (a.evidence/'app-tests.log').read_text(encoding='utf-8-sig')
assert 'PERSONAL_JOURNEY_UI_OK' in (a.evidence/'ui.log').read_text(encoding='utf-8-sig')
assert 'four_authorized_demo_passengers=True' in (a.evidence/'native.log').read_text(encoding='utf-8-sig')
dev=json.loads((a.evidence/'final-development-counts.json').read_text(encoding='utf-8-sig'));prod=json.loads((a.evidence/'final-production-counts.json').read_text(encoding='utf-8-sig'))
assert dev==dict(machines=1,services=1,passengers=4,hardware_copied=0) and prod==dict(production_machines=0,cerro_gps=4,development_gps=1,development_assets=1)
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'));url=c['url'].rstrip('/');assert url=='https://soporte.stepsapp.cl'
uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{});assert uid
rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object');context=dict(tracking_disable=True,mail_notrack=True,mail_create_nosubscribe=True,mail_notify_force_send=False,mail_auto_subscribe_no_notify=True)
def call(model,method,args,kw=None):return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,args,dict(context=context,**(kw or {})))
assert call('helpdesk.ticket','read',[[46]],{'fields':['stage_id']})[0]['stage_id'][0]==2
author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',46)];before={m:set(call(m,'search',[domain])) for m in ('mail.notification','mail.mail')}
body='⟦IA-EVIDENCIA⟧ Preparación personal solicitada en este chat, 02-11-2026. Tracker 1.6.2 disponible solo en Desarrollo: un vehículo personal con GPS, valores de Conducción/Interno y conductor preseleccionados. Archivadas 18 fichas antiguas, conservando registros/lecturas; retiradas 19 proyecciones sin GPS/historial, con respaldo y copia fresca. El auto inicia/cierra sin inventar horómetro o combustible; odómetro físico conservado. El conductor se resuelve por su relación nativa con el usuario, sin reutilizar un RUT legado diferente. Capacidad confirmada: cuatro pasajeros. Por autorización posterior del usuario se creó un servicio de prueba con cuatro personas/documentos ficticios y QR, sin iniciar jornadas reales durante la revisión. La operación clásica y adjuntos usan ahora tracker_steps_development y almacenamiento propios: sustituye la base compartida descrita para la primera I10. La identidad de login mantiene su ID y claves existentes; el receptor/GPS siguen en el dominio y puente originales. Catálogo productivo sin el auto personal; Cerro conserva cuatro GPS y Desarrollo uno. 187 pruebas móviles, TypeScript, API y navegador de apertura/cierre en copia, cuenta real con formulario/mapa/ficha y cuatro pasajeros comprobados. Copias, servidores y sesiones temporales retirados. Sin publicación de la UI en Cerro ni cambios a su API/receptor. No se declara completada I11 ni el consumidor automático hacia Odoo. Frontend certificado 35c2b1fda8ad037af600577410e3cf2bda847595; procedimientos versionados en docs/PREPARACION_JORNADA_PERSONAL_DESARROLLO.md. T46 continúa en curso.'
note=call('mail.message','create',[dict(model='helpdesk.ticket',res_id=46,message_type='comment',subtype_id=subtype,author_id=author,partner_ids=[(6,0,[])],body='<p>'+html.escape(body)+'</p>')])
for model,ids in before.items():assert set(call(model,'search',[domain]))==ids
(a.evidence/'ticket-note.json').write_text(json.dumps(dict(ticket=46,note=note,stage=2,notifications=0)),encoding='utf-8')
print('PERSONAL_JOURNEY_DELIVERY_RECORDED stage=2 NO_NOTIFICATIONS_OK note='+str(note))
