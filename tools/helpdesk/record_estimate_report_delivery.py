"""Close T68 only after both live destination checks, without external notifications."""
import argparse,html,json,re,xmlrpc.client
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('evidence',type=Path);p.add_argument('--commit',required=True)
a=p.parse_args();assert re.fullmatch('[0-9a-f]{40}',a.commit)
proof={}
for name,db in [('development','LAB_TAREAS'),('cerro','CERRO_EL_PLOMO')]:
    folder=a.evidence/name;qa=json.loads((folder/'qa_passed.json').read_text())
    assert qa['commit']==a.commit
    rows=[s for s in (folder/('verify-'+db+'.log')).read_text(encoding='utf-8').splitlines() if s.startswith('MANAGEMENT_REGISTRY_OK ')]
    assert len(rows)==1
    result=json.loads(rows[0].split(' ',1)[1]);assert result['ticket']==68
    assert all(result[k] for k in ('menu_visible','views','gantt','pivot','company_security_tested'))
    assert result['quantities']==100 and result['amount_usd']==200
    assert result['versions']=={'step_producer_estimate_report':'18.0.1.0.0'}
    proof[name]=result
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
u=c.get('url','https://soporte.stepsapp.cl').rstrip('/');assert u.startswith('https://')
i=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
s=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/object')
def rpc(m,f,args,k=None):return s.execute_kw(c['db'],i,c['api_key'],m,f,args,k or {})
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',68),('message_type','in',['comment','email']),('subtype_id','=',1),('id','>',9336)]],{'fields':['id','body']})
assert not recent,'Review new human feedback before closing: '+str([x['id'] for x in recent])
assert rpc('helpdesk.ticket','read',[[68]],{'fields':['name']})[0]['name'].startswith('T68')
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author=rpc('res.users','read',[[i]],{'fields':['partner_id']})[0]['partner_id'][0]
marker='T68 - informe estimaciones publicado '+a.commit[:7]
existing=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',68),('body','ilike',marker)]],{'fields':['id']})
if existing:message=existing[0]['id']
else:
    body='<h3>'+html.escape(marker)+'</h3><p>Publicado y verificado en Desarrollo y Cerro El Plomo. Productores / Planificación / Informe estimaciones de cosecha incluye Gantt, tabla dinámica y detalle semanal, con filtros por temporada, especie, variedad, Delivery Kind y productor. Cantidades: kilos exportación, kilos a proceso, cajas, pallets y bins. Vigentes es el filtro inicial; puede consultar creadas/validadas e historial por separado.</p>'
    body+='<p>El valor FOB estimado USD usa los precios de preliquidación existentes por fruta y semana. Sin precio, con precios ambiguos, unidad incompatible o tipo de cambio ausente, la semana queda señalada sin valorizar; el contador permite reconocer totales parciales. El informe consulta los originales sin copiar ni modificar estimaciones.</p>'
    body+='<p>Cinco pruebas funcionales aprobadas en copias nuevas de ambos destinos; conservación exacta de los registros originales. Después de publicar se verificaron versiones, menú, vistas, filtros, datos nativos del Gantt, agrupación semanal, cantidades, USD y separación por empresa. Las muestras se revirtieron.</p>'
    body+='<p><a href="https://cerroelplomo.stepsapp.cl/odoo/action-%s">Abrir informe en Cerro</a>. <a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T68_INFORME_ESTIMACIONES_2026-10-11.rst">Acta de entrega</a>. Código guardado y subido. Nota interna sin envío de correo.</p>'%proof['cerro']['action_id']
    message=rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':68,'message_type':'comment','subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
rpc('helpdesk.ticket','write',[[68],{'stage_id':4}],{'context':{'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
saved=rpc('mail.message','read',[[message]],{'fields':['subtype_id','notification_ids']})[0]
assert saved['subtype_id'][0]==note and not saved['notification_ids']
assert rpc('helpdesk.ticket','read',[[68]],{'fields':['stage_id']})[0]['stage_id'][0]==4
print('TICKET_DELIVERY_OK 68 note',message,'Solved notifications=0')
