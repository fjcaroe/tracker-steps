"""Record verified T74-T75 delivery as internal notes with zero notifications."""
import argparse,html,json,re,xmlrpc.client
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('evidence',type=Path);p.add_argument('--commit',required=True)
a=p.parse_args();assert re.fullmatch('[0-9a-f]{40}',a.commit)
proof={}
for name,db in [('development','LAB_TAREAS'),('cerro','CERRO_EL_PLOMO')]:
    folder=a.evidence/name;qa=json.loads((folder/'qa_passed.json').read_text());assert qa['commit']==a.commit
    rows=[line for line in (folder/('verify-'+db+'.log')).read_text(encoding='utf-8').splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
    assert len(rows)==1
    result=json.loads(rows[0].split(' ',1)[1]);assert result['tickets']==[74,75]
    assert all(result[k] for k in ('menus','forms','historical_formulas','weekly_report','version_flow'))
    assert result['versions']=={'step_producer_estimate_revision':'18.0.1.0.0'}
    assert result['groups']['bins']['export_boxes']==20000 and result['groups']['pallet']['export_pallets']==500
    proof[name]=result
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
u=c.get('url','https://soporte.stepsapp.cl').rstrip('/');assert u.startswith('https://')
i=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
s=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/object')
def rpc(m,f,args,k=None):return s.execute_kw(c['db'],i,c['api_key'],m,f,args,k or {})
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','in',[74,75]),('message_type','in',['comment','email']),('subtype_id','=',1),('id','>',9374)]],{'fields':['id','res_id']})
assert not recent,'Review new human feedback before closing: '+str(recent)
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author=rpc('res.users','read',[[i]],{'fields':['partner_id']})[0]['partner_id'][0]
texts={74:'Envases de traslado incorpora Grupo paquete (Bins, Pallet, A piso) y Pallet por avión. Cajas por pallet ahora se llama Cajas por pallet/bins. Packing / Maestros / Tipos de pallets y Productores / Maestros / Tipos de pallet abren el mismo maestro existente. Los campos están también al abrir el envase desde una estimación.',
       75:'Bins y Pallets proceso dividen Kilos a proceso por Cajas por pallet/bins del envase, según su Grupo paquete. Cajas exportación divide Kilos exportación por Kg Caja Base de Especie; Pallets exportación divide Kilos exportación por Caja Base x pallet de Especie. El informe semanal usa los mismos cálculos. Pallets proceso queda calculado y de solo lectura.'}
for ticket,text in texts.items():
    marker='T%s - entrega verificada de envases y estimaciones'%ticket
    previous=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',ticket),('body','ilike',marker)]],{'fields':['id']})
    if previous:message=previous[0]['id']
    else:
        current=rpc('helpdesk.ticket','read',[[ticket]],{'fields':['name','write_date']})[0]
        assert current['name'].startswith('T'+str(ticket))
        expected_date={74:'2026-10-12 18:48:10',75:'2026-10-12 18:50:34'}[ticket]
        assert current['write_date']==expected_date,'Ticket changed; reread the current scope before closure'
        body='<h3>'+html.escape(marker)+'</h3><p>'+html.escape(text)+'</p>'
        body+='<p>Publicado y verificado en Desarrollo y Cerro El Plomo. Ocho pruebas aprobadas en copias nuevas de ambos destinos. Se comprobaron menús, formularios, fórmulas de las líneas existentes, informe semanal y creación y activación de nuevas versiones. Se conservaron los kilos, semanas y demás datos originales; las muestras de comprobación se revirtieron.</p>'
        body+='<p>Los grupos y capacidades existentes no se asignaron por su nombre. Configure Grupo paquete y las capacidades en Envases de traslado, y Kg Caja Base y Caja Base x pallet en Especie. Si falta un divisor positivo o el grupo no corresponde, la cantidad calculada es cero.</p>'
        body+='<p><a href="https://cerroelplomo.stepsapp.cl/odoo/action-%s">Abrir Envases de traslado en Cerro</a>. <a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T73_T75_REVISION_FRUTA_2026-10-12.rst">Acta interna de verificación</a>.</p>'%proof['cerro']['package_action']
        message=rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':ticket,'message_type':'comment','subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
    rpc('helpdesk.ticket','write',[[ticket],{'stage_id':4}],{'context':{'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
    saved=rpc('mail.message','read',[[message]],{'fields':['subtype_id','notification_ids','body']})[0]
    assert saved['subtype_id'][0]==note and not saved['notification_ids'] and '<p>' in saved['body'] and '&lt;p&gt;' not in saved['body']
    assert rpc('helpdesk.ticket','read',[[ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    print('TICKET_DELIVERY_OK',ticket,'note',message,'Solved notifications=0')

marker='T73 - decisión pendiente de migración entre maestros'
previous=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',73),('body','ilike',marker)]],{'fields':['id']})
if not previous:
    current=rpc('helpdesk.ticket','read',[[73]],{'fields':['write_date']})[0]
    assert current['write_date']=='2026-10-12 14:26:19','Reread T73 feedback before holding it'
    body='<h3>'+marker+'</h3><p>Se revisaron el documento y los maestros efectivos de Desarrollo y Cerro El Plomo. En Cerro hay una recepción con la clase antigua A proceso cuya categoría homónima pertenece a otra empresa.</p><p>Se consultó a Fernando si debe migrarse a una categoría A proceso de la misma empresa o asociarse a Materia Prima. La elección define el significado de esa recepción; no se asignará una categoría de otra empresa ni se supondrá una equivalencia. Las relaciones y registros existentes se conservan. Ticket en espera de esa decisión.</p>'
    message=rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':73,'message_type':'comment','subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
    rpc('helpdesk.ticket','write',[[73],{'stage_id':6}],{'context':{'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
    saved=rpc('mail.message','read',[[message]],{'fields':['subtype_id','notification_ids']})[0]
    assert saved['subtype_id'][0]==note and not saved['notification_ids']
    assert rpc('helpdesk.ticket','read',[[73]],{'fields':['stage_id']})[0]['stage_id'][0]==6
    print('TICKET_WAITING_DECISION_OK 73 note',message,'notifications=0')
