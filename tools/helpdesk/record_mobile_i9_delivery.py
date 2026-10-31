"""Record verified I9 progress internally, keeping T46 open without notifications."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('evidence',type=Path);a=p.parse_args()
    proof=json.loads(a.evidence.read_text())
    assert proof['ticket']==46 and proof['iteration']=='I9' and proof['backend_tests']==68 and proof['app_tests']==165
    assert all(proof[key] is True for key in ('postgres_rehearsal','effective_source_matches','live_auth_required','ui375_reviewed'))
    assert proof['live_fake_records']==0
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'));url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{});assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(model,method,args,kwargs=None):
        return rpc.execute_kw(c['db'],uid,c['api_key'],model,method,args,dict({'context':context},**(kwargs or {})))
    ticket=call('helpdesk.ticket','read',[[46]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0]==2 and not ticket['sla_ids'] and not ticket['sla_status_ids']
    assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',46),('id','>',proof['reviewed_message']),('message_type','in',['comment','email'])]])
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',46)]
    before={model:set(call(model,'search',[domain])) for model in ('mail.notification','mail.mail')}
    body='⟦IA-EVIDENCIA⟧ I9 completada en Tracker 1.3.0, https://stepsapp.cl/truck/. Arquitectura confirmada por el usuario en este chat el 31-10: servicios/pasajeros en PostgreSQL de Tracker y contrato hacia Odoo. Hoy incluye Mi servicio, de consulta, con ruta, vehículo, conductor, capacidad, paradas y nómina. Solo el conductor asignado o un administrador puede consultar; no se guarda la nómina en el teléfono. Se reutilizan maestros existentes. La capacidad real debe configurarse en el vehículo antes de programar. Probadas creación de tres pasajeros, conservación de capacidad histórica, aislamiento e idempotencia en copia PostgreSQL; 68 pruebas backend y 165 app, revisión móvil 375 px. Datos antiguos conservados, sin registros ficticios en producción. La sincronización automática Odoo no se instala en I9: el contrato queda documentado para su consumidor. Ticket abierto para I10/I11 y los pendientes nativos/terreno del plan; no se certifica GPS físico ni APK/IPA. Commit '+proof['commit']+'; JS '+proof['asset']+' SHA-256 '+proof['asset_sha256']+'. Respaldo '+proof['backup']+'.'
    note=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':46,'message_type':'comment','subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    for model,ids in before.items():assert set(call(model,'search',[domain]))==ids
    assert call('helpdesk.ticket','read',[[46]],{'fields':['stage_id']})[0]['stage_id'][0]==2
    print('T46_I9_DELIVERY_RECORDED note='+str(note)+' stage=2 NO_NOTIFICATIONS_OK')


if __name__=='__main__':main()
