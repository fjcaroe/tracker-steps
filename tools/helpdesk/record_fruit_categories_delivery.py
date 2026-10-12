"""Close T73 only after both published destinations and the latest client response are checked."""
import argparse,html,json,re,xmlrpc.client
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('evidence',type=Path);p.add_argument('--commit',required=True)
p.add_argument('--ticket-snapshot',type=Path,required=True)
a=p.parse_args();assert re.fullmatch('[0-9a-f]{40}',a.commit)
proof={}
for name,db in [('development','LAB_TAREAS'),('cerro','CERRO_EL_PLOMO')]:
    folder=a.evidence/name;qa=json.loads((folder/'qa_passed.json').read_text());assert qa['commit']==a.commit
    rows=[line for line in (folder/('verify-'+db+'.log')).read_text(encoding='utf-8').splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
    assert len(rows)==1
    result=json.loads(rows[0].split(' ',1)[1]);assert result['tickets']==[73]
    assert all(result[k] for k in ('shared_categories','class_menus','forms','receipt_validated','contract_price','company_security','legacy_relations_retired'))
    assert result['versions']=={'step_fruit_category_unification':'18.0.1.0.0'}
    proof[name]=result
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
u=c.get('url','https://soporte.stepsapp.cl').rstrip('/');assert u.startswith('https://')
i=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
s=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/object')
def rpc(m,f,args,k=None):return s.execute_kw(c['db'],i,c['api_key'],m,f,args,k or {})
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',73),('message_type','in',['comment','email']),('subtype_id','=',1),('id','>',9378)]],{'fields':['id']})
assert not recent,'Read new human feedback before closing T73'
answer=rpc('mail.message','read',[[9378]],{'fields':['res_id','model','body']})[0]
assert answer['model']=='helpdesk.ticket' and answer['res_id']==73 and 'Actualizar el maestro' in answer['body']
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author=rpc('res.users','read',[[i]],{'fields':['partner_id']})[0]['partner_id'][0]
marker='T73 - categorías y clases compartidas verificadas'
previous=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',73),('body','ilike',marker)]],{'fields':['id']})
if previous:message=previous[0]['id']
else:
    snapshot=json.loads(a.ticket_snapshot.read_text(encoding='utf-8'))
    current=rpc('helpdesk.ticket','read',[[73]],{'fields':['name','write_date','stage_id']})[0]
    assert current['name']==snapshot['name'] and current['write_date']==snapshot['write_date'] and current['stage_id'][0]==2,'Ticket scope changed; reread it before closure'
    body='<h3>'+html.escape(marker)+'</h3><p>Se incorporó su respuesta y se comprobó que A proceso ya no está relacionado con la recepción de prueba. Se actualizó el maestro en Desarrollo y Cerro El Plomo.</p>'
    body+='<p>Categoría de fruta de Packing, recepciones y contratos usa ahora el maestro general de Gestión y costos. Las relaciones existentes se migraron mediante su equivalencia explícita, conservando registros, kilos e importes. No se creó una categoría por suposición ni se asignó una relación a otra empresa.</p>'
    body+='<p>Clase de fruta de Gestión está disponible en Configuraciones / Fruta de Exportaciones, Packing y Productores. Las aplicaciones comparten los mismos registros, con formularios y permisos por empresa. Inventario puede consultar las clases; la edición conserva los permisos de Gestión.</p>'
    body+='<p>Se aprobaron seis pruebas en copias nuevas de ambos destinos y se repitieron versión, menús, formularios, validación real de recepción y selección del precio contractual después de publicar. Los datos originales se preservaron; las muestras se revirtieron.</p>'
    body+='<p><a href="https://cerroelplomo.stepsapp.cl/odoo/action-%s">Abrir Categorías en Cerro</a>. <a href="https://cerroelplomo.stepsapp.cl/odoo/action-%s">Abrir Clases en Cerro</a>. <a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T73_CATEGORIAS_COMPARTIDAS_2026-10-12.rst">Acta interna de verificación</a>.</p>'%(proof['cerro']['category_action'],proof['cerro']['class_action'])
    message=rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':73,'message_type':'comment','subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
rpc('helpdesk.ticket','write',[[73],{'stage_id':4}],{'context':{'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
saved=rpc('mail.message','read',[[message]],{'fields':['subtype_id','notification_ids','body']})[0]
assert saved['subtype_id'][0]==note and not saved['notification_ids'] and '<p>' in saved['body'] and '&lt;p&gt;' not in saved['body']
assert rpc('helpdesk.ticket','read',[[73]],{'fields':['stage_id']})[0]['stage_id'][0]==4
print('TICKET_DELIVERY_OK 73 note',message,'Solved notifications=0')
