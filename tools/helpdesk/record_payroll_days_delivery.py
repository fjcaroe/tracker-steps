"""Record T138 prospective payroll correction internally without notifications."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args();root=a.evidence
    expected=json.loads((root/'delivery.json').read_text());assert expected['tests']==28
    for target in ('development','sys','demo-sys','cerro'):
        qa=json.loads((root/(target+'-qa.json')).read_text());d=json.loads((root/(target+'-deployment.json')).read_text())
        assert qa['commit']==d['commit']==expected['commit'] and qa['release_sha256']==d['sha256']==expected['sha256']
        assert re.search(r'0 failed, 0 error\(s\) of 7 tests',(root/(target+'-qa.log')).read_text(encoding='utf-8-sig'))
        live=(root/(target+'-live.log')).read_text(encoding='utf-8-sig')
        assert 'MANAGEMENT_VERIFY_OK' in live and expected['commit'] in live
        payloads=[json.loads(line.split('MANAGEMENT_REGISTRY_OK ',1)[1]) for line in live.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(x.get('ticket')==138 and x.get('existing_profile',1)!=1 and x.get('native_payroll_menu_and_form') and x.get('writes') is False for x in payloads)
        if target=='demo-sys':assert 'DEMO_SYS_SCOPE_OK' in live
    assert 'T138_NATIVE_CASES_OK one_absence=29 two_absences=28 paid_history_unchanged=True rollback_required=True' in (root/'sys-flow.log').read_text(encoding='utf-8-sig')
    body=('T138: corregido el cálculo de inasistencias en contratos mensuales que cubren todo el mes: '
        'base de 30 días menos faltas. Se reconoce el maestro nativo de permisos no pagados vinculado a LEAVECL130, '
        'conservando sus relaciones, códigos y registros; no se confunde con las licencias médicas reales. '
        'Calcular hoja actualiza la asistencia afectada en recibos borrador/en espera y aplica los atrasos existentes una sola vez. '
        'Se conservan ausencias e inputs; licencias, contratos parciales y recibos pagados/listos no se modifican. '
        'Los dos casos reportados pasaron el cálculo nativo en copia de SyS: una falta = 29 días; dos faltas = 28, '
        'con sueldo base comprobado y hashes de liquidaciones pagadas, contratos, asistencias y contabilidad conservados. '
        'Esos cálculos fueron revertidos. Publicado y verificado el mismo paquete en Desarrollo, SyS, Demo-SYS y Cerro, '
        'con 28 pruebas, respaldo y bloqueo. Demo-SYS recibió solo el módulo de Nómina ya instalado en SyS. '
        'No se recalcularon liquidaciones reales al publicar: para actualizar un borrador existente, usar Calcular hoja. '
        'Referencia DT: https://www.dt.gob.cl/portal/1628/w3-article-60221.html . '
        'Commit: '+expected['commit']+'; SHA-256: '+expected['sha256']+'.')
    c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'));url='https://soporte.stepsapp.cl'
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{});assert uid
    rpc=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object');context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_notify_force_send':False,'mail_auto_subscribe_no_notify':True}
    def call(m,f,v,kw=None):return rpc.execute_kw(c['db'],uid,c['api_key'],m,f,v,dict({'context':context},**(kw or {})))
    ticket=call('helpdesk.ticket','read',[[138]],{'fields':['stage_id','sla_ids','sla_status_ids']})[0]
    assert ticket['stage_id'][0] not in (4,5) and not ticket['sla_ids'] and not ticket['sla_status_ids']
    model=call('ir.model','search',[[('model','=','helpdesk.ticket')]])
    assert not call('base.automation','search_count',[[('model_id','in',model),('active','=',True)]])
    assert not call('mail.message','search_count',[[('model','=','helpdesk.ticket'),('res_id','=',138),('id','>',expected['reviewed_message_id']),('message_type','in',['comment','email'])]])
    author=call('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    subtype=call('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    domain=[('mail_message_id.model','=','helpdesk.ticket'),('mail_message_id.res_id','=',138)]
    deliveries={m:set(call(m,'search',[domain])) for m in ('mail.notification','mail.mail')}
    message=call('mail.message','create',[{'model':'helpdesk.ticket','res_id':138,'message_type':'comment','subtype_id':subtype,'author_id':author,'partner_ids':[(6,0,[])],'body':'<p>'+html.escape(body)+'</p>'}])
    call('helpdesk.ticket','write',[[138],{'stage_id':4}]);assert call('helpdesk.ticket','read',[[138]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    for m,ids in deliveries.items():assert set(call(m,'search',[domain]))==ids
    print('T138_DELIVERY_RECORDED note=%s NO_NOTIFICATIONS_OK'%message)


if __name__=='__main__':main()
