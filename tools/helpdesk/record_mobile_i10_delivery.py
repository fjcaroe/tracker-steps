"""Record I10 in Development internally, preserving T46 open and no sends."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('evidence',type=Path);args=parser.parse_args()
root=args.evidence
qa=json.loads((root/'qa.json').read_text(encoding='utf-8-sig'))
delivery=json.loads((root/'development.json').read_text(encoding='utf-8-sig'))
assert qa['commit']==delivery['commit'] and qa['assets']==delivery['assets'] and qa['fresh_copy']
assert all(delivery[name] for name in ('api_process_isolated','database_shared','production_api_unchanged','receiver_unchanged','cerro_frontend_unchanged'))
for filename,marker in [('app-tests.log','183 passed'),('backend-tests.log','83 passed'),('postgres.log','POSTGRES_I10_MIGRATION_OK'),('ui.log','PASSENGER_BOARDING_UI_OK'),('native.log','PASSENGER_NATIVE_OK'),('live-verify.log','I10_DEVELOPMENT_VERIFIED')]:
    assert marker in (root/filename).read_text(encoding='utf-8-sig'), filename
assert 'version=1.6.1' in (root/'native.log').read_text(encoding='utf-8-sig')
counts=json.loads((root/'live-counts.json').read_text(encoding='utf-8-sig'))
assert counts['services']==counts['events']==0 and counts['cerro_gps']==4 and counts['development_gps']==1
config=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url=config['url'].rstrip('/');assert url=='https://soporte.stepsapp.cl'
uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(config['db'],config['username'],config['api_key'],{});assert uid
rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
def call(model,method,values,kw=None):return rpc.execute_kw(config['db'],uid,config['api_key'],model,method,values,dict({'context':context},**(kw or {})))
ticket=call('helpdesk.ticket','read',[[46]],{'fields':['stage_id']})[0];assert ticket['stage_id'][0]==2
assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',46),('id','>',9922),('message_type','in',['comment','email'])]]), 'Review the newer human response before recording delivery'
author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',46)]
before={model:set(call(model,'search',[domain])) for model in ('mail.notification','mail.mail')}
body='⟦IA-EVIDENCIA⟧ I10 disponible solo en Desarrollo, Tracker 1.6.1: https://desarrollo.stepsapp.cl/truck/. En Hoy / Mi servicio, preparar la nómina con señal y registrar subida, bajada y ausencia sin conexión; buscar, filtrar o leer QR/código selecciona al pasajero y la acción se confirma aparte. Ocupación y asientos se validan; reintentos no duplican y los conflictos piden revisión. Preparación local por cuenta y por 24 horas; ubicación opcional. Perfil y aviso de salida incluyen los eventos pendientes. El viaje completo de cinco eventos pasó en PostgreSQL privado y navegador móvil/escritorio: manifiesto final coincidente, aislamiento y cero registros ficticios en el destino vivo. Cuenta existente verificada en Hoy, Perfil y mapa de PKFX47. API Development independiente en loopback 8012, sin sustituir ni reiniciar API productiva o receptor; maestros/base Tracker siguen compartidos y la migración es aditiva. Cerro y Steps compartido conservan sus interfaces. Misma entrega probada, respaldo y bloqueo; 183 pruebas app, 83 API. No se acredita cámara física, APK/IPA ni sincronización Odoo automática. T46 sigue en curso para I11 y los pendientes del plan. La instrucción reciente del usuario limita nuevas funciones a Desarrollo antes de promoverlas. Commit '+delivery['commit']+'. Respaldo '+delivery['backup']+'.'
note=call('mail.message','create',[dict(model='helpdesk.ticket',res_id=46,message_type='comment',subtype_id=subtype,author_id=author,partner_ids=[(6,0,[])],body='<p>'+html.escape(body)+'</p>')])
for model,values in before.items():assert set(call(model,'search',[domain]))==values
assert call('helpdesk.ticket','read',[[46]],{'fields':['stage_id']})[0]['stage_id'][0]==2
(root/'ticket-note.json').write_text(json.dumps(dict(ticket=46,note=note,stage=2,commit=delivery['commit'],notifications=0),indent=2),encoding='utf-8')
print('T46_I10_RECORDED development_only=True stage=2 NO_NOTIFICATIONS_OK note='+str(note))
