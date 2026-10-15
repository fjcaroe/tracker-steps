"""Close the new contract-mode ticket only after matching QA, deployment and UI proofs."""
import argparse,hashlib,html,json,xmlrpc.client
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--evidence',type=Path,required=True)
p.add_argument('--commit',required=True)
a=p.parse_args()
review=json.loads((a.evidence/'visual-review.json').read_text(encoding='utf-8'))
assert review['commit']==a.commit and review['development'] and review['cerro']
for dest in ('development','cerro'):
    qa=json.loads((a.evidence/(dest+'-qa.json')).read_text(encoding='utf-8'))
    assert qa['commit']==a.commit
    log=(a.evidence/(dest+'-deploy.log')).read_text(encoding='utf-8')
    assert a.commit in log and 'MANAGEMENT_DEPLOY_OK backup=' in log and 'MANAGEMENT_VERIFY_OK' in log
    assert qa['release_sha256']==review['release_sha256']
    for kind in ('contract','estimate','report'):
        f=a.evidence/(dest+'-'+kind+'.png')
        assert hashlib.sha256(f.read_bytes()).hexdigest()==review['files'][f.name]
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
u=c['url'].rstrip('/')
uid=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
s=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/object')
def rpc(model,method,args,kwargs=None):
    return s.execute_kw(c['db'],uid,c['api_key'],model,method,args,kwargs or {})
t=rpc('helpdesk.ticket','read',[[86]],{'fields':['name','stage_id']})[0]
assert 'Contrato de productores' in t['name'] and t['stage_id'][0] in (1,2,4)
marker='Modalidad de compra disponible y verificada'
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',86),('id','>',9452),('message_type','in',['comment','email'])]],{'fields':['id','body']})
assert all(marker in (m['body'] or '') for m in recent),'Read new human replies before closing'
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author=rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
text=('Disponible en Desarrollo y Cerro El Plomo: Modalidad de compra ofrece A firme y Consignación '
    'en el encabezado de contratos y estimaciones. La explicación visible indica precio final sin '
    'liquidación para A firme y precio referencial sujeto al ciclo de Liquidación de productor '
    'para Consignación. Ambos informes incorporan la modalidad para consultar, filtrar y agrupar. '
    'Los históricos conservan sus importes y quedan sin modalidad hasta elegirla explícitamente; '
    'las revisiones heredan la elección. Se probaron formularios, menús, informes, versiones y '
    'permisos por empresa en copias nuevas de ambos destinos y después de publicar con respaldo. '
    'El campo no genera liquidaciones ni asientos automáticamente.')
old=[m for m in recent if marker in (m['body'] or '')]
msg=old[0]['id'] if old else rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':86,
    'message_type':'comment','subtype_id':note,'author_id':author,'partner_ids':[(5,0,0)],
    'body':'<h3>'+marker+'</h3><p>'+html.escape(text)+'</p>'}])
saved=rpc('mail.message','read',[[msg]],{'fields':['subtype_id','notification_ids']})[0]
assert saved['subtype_id'][0]==note and not saved['notification_ids']
rpc('helpdesk.ticket','write',[[86],{'stage_id':4}],{'context':{'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
assert rpc('helpdesk.ticket','read',[[86]],{'fields':['stage_id']})[0]['stage_id'][0]==4
print('TICKET_DELIVERY_OK id=86 internal_note='+str(msg)+' stage=solved')
