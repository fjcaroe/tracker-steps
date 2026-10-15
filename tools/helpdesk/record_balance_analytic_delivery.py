"""Silently close an analytic opening ticket only after matching deployment evidence."""
import argparse,hashlib,html,json,xmlrpc.client
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--commit',required=True)
a=p.parse_args()
v=json.loads((a.evidence/'visual-review.json').read_text(encoding='utf-8'))
assert v['commit']==a.commit and v['development'] and v['cerro']
for dest in ('development','cerro'):
    qa=json.loads((a.evidence/(dest+'-qa.json')).read_text(encoding='utf-8'))
    assert qa['commit']==a.commit and qa['release_sha256']==v['release_sha256']
    log=(a.evidence/(dest+'-deploy.log')).read_text(encoding='utf-8')
    assert a.commit in log and 'MANAGEMENT_DEPLOY_OK backup=' in log and 'MANAGEMENT_VERIFY_OK' in log
copy=(a.evidence/'cerro-qa.log').read_text(encoding='utf-8')
assert copy.count('"posted_in_copy_only": true')==2
assert '0 failed, 0 error(s) of 4 tests' in copy
assert 'MANAGEMENT_QA_OK cerro' in copy or 'MANAGEMENT_CERTIFY_OK cerro' in copy
for name,sha in v['files'].items():
    assert hashlib.sha256((a.evidence/name).read_bytes()).hexdigest()==sha
assert v['files'] and v['originals_remain_draft']
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
u=c['url'].rstrip('/')
uid=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
s=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/object')
def rpc(m,f,args,kw=None):return s.execute_kw(c['db'],uid,c['api_key'],m,f,args,kw or {})
t=rpc('helpdesk.ticket','read',[[88]],{'fields':['name','stage_id']})[0]
assert 'Apertura contable' in t['name'] and t['stage_id'][0] in (1,2,4)
marker='Aperturas: validación analítica corregida y verificada'
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',88),('id','>',9463),('message_type','in',['comment','email'])]],{'fields':['id','body']})
assert all(marker in (m['body'] or '') for m in recent),'Read newer human replies before closing'
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author=rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
body=('Corregido y verificado en Desarrollo y Cerro El Plomo. Las cuentas de activo, pasivo y patrimonio '
      'no exigen distribución analítica; las cuentas de ingreso y gasto conservan sus reglas y el 100 % '
      'cuando corresponde. La apertura de resultados ya tenía su analítica completa; el bloqueo provenía '
      'de líneas de balance y del ajuste bimoneda generado al publicar. Este ajuste hereda la distribución '
      'solo cuando la atribución existente es única, sin elegir entre distribuciones distintas. '
      'Se probaron las dos aperturas reales en una copia de Cerro, con contabilización '
      'y reversión de la prueba, y se verificó la instalación publicada con respaldo. Los comprobantes '
      'originales permanecen en borrador, con sus importes y distribuciones intactos. No se contabilizaron '
      'comprobantes del cliente en producción.')
old=[m for m in recent if marker in (m['body'] or '')]
msg=old[0]['id'] if old else rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':88,
    'message_type':'comment','subtype_id':note,'author_id':author,'partner_ids':[(5,0,0)],
    'body':'<h3>'+marker+'</h3><p>'+html.escape(body)+'</p>'}])
saved=rpc('mail.message','read',[[msg]],{'fields':['subtype_id','notification_ids']})[0]
assert saved['subtype_id'][0]==note and not saved['notification_ids']
rpc('helpdesk.ticket','write',[[88],{'stage_id':4}],{'context':{'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
assert rpc('helpdesk.ticket','read',[[88]],{'fields':['stage_id']})[0]['stage_id'][0]==4
print('TICKET_DELIVERY_OK id=88 internal_note='+str(msg)+' stage=solved')
