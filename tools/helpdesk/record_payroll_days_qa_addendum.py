"""Append the explicitly authorized T138 QA-Cerro alignment, silently."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args();root=a.evidence
    qa=json.loads((root/'qa.json').read_text());d=json.loads((root/'deployment.json').read_text())
    assert qa['commit']==d['commit'] and qa['release_sha256']==d['sha256']
    assert re.search(r'0 failed, 0 error\(s\) of 7 tests',(root/'qa.log').read_text(encoding='utf-8-sig'))
    live=(root/'live.log').read_text(encoding='utf-8-sig');assert 'MANAGEMENT_VERIFY_OK' in live and qa['commit'] in live
    pair=json.loads((root/'pair.json').read_text())
    for key in ('version','sha256'):
        assert pair['cerro']['step_hr_contract_days'][key]==pair['qa-cerro']['step_hr_contract_days'][key]
    assert pair['cerro']['step_hr_contract_days']['version']=='18.0.1.2.0'
    isolation=(root/'isolation.log').read_text()
    assert all(marker in isolation for marker in ('CUSTOMER_QA_VERIFY_OK','CUSTOMER_QA_EGRESS_BLOCKED','CUSTOMER_QA_SOURCE_DB_DENIED'))
    body=('Ampliación de T138 autorizada por el usuario en este chat: QA-Cerro actualizado al mismo paquete '
        'y versión 18.0.1.2.0 de Cerro producción. Siete pruebas adicionales en copia fresca y verificación '
        'de menú/formulario con usuario existente, respaldo y bloqueo. Comprobadas versión y huella del '
        'código efectivo iguales en ambos ambientes. Se conservaron capacitación, datos y aislamiento; '
        'no se refrescó la base ni se recalcularon recibos reales. La política canónica registra que las '
        'entregas aplicables a Cerro deben incluir QA-Cerro y verificar paridad de los módulos afectados. '
        'El cliente ya había respondido VERIFICADO OK y el ticket permanece resuelto. Commit del paquete: '
        +qa['commit']+'; SHA-256: '+qa['release_sha256']+'.')
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'));url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{});assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object');context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_notify_force_send':False}
    def call(m,f,v,kw=None):return rpc.execute_kw(c['db'],uid,c['api_key'],m,f,v,dict({'context':context},**(kw or {})))
    assert call('helpdesk.ticket','read',[[138]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',138),('id','>',9844),('message_type','in',['comment','email'])]])
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    related=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',138)]
    before={m:set(call(m,'search',[related])) for m in ('mail.notification','mail.mail')}
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':138,'message_type':'comment','subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    for model,values in before.items():assert set(call(model,'search',[related]))==values
    print('T138_QA_ADDENDUM_RECORDED note=%s NO_NOTIFICATIONS_OK'%message)


if __name__=='__main__':main()
