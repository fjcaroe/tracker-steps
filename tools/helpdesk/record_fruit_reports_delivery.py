"""Close T70-T72 only after both live reports and shared masters pass."""
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
    result=json.loads(rows[0].split(' ',1)[1]);assert result['tickets']==[70,71,72]
    assert all(result[k] for k in ('shared_masters','species_form','menus','pivot_list_filters','source_receipts_validated','company_security'))
    assert result['versions']=={'step_producer_fruit_reports':'18.0.1.0.0'}
    assert result['totals']=={'process':{'packaging_qty':30,'kilos':150},'packed':{'packaging_qty':30,'kilos':150}}
    proof[name]=result
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
u=c.get('url','https://soporte.stepsapp.cl').rstrip('/');assert u.startswith('https://')
i=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
s=xmlrpc.client.ServerProxy(u+'/xmlrpc/2/object')
def rpc(m,f,args,k=None):return s.execute_kw(c['db'],i,c['api_key'],m,f,args,k or {})
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','in',[70,71,72]),('message_type','in',['comment','email']),('subtype_id','=',1),('id','>',9354)]],{'fields':['id','res_id']})
assert not recent,'Review new human feedback before closing: '+str(recent)
note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
author=rpc('res.users','read',[[i]],{'fields':['partner_id']})[0]['partner_id'][0]
texts={70:'Productores / Configuraciones / Fruta reúne Especie, Grupo variedad, Variedad, Grupo de calibre, Calibre de fruta, Categoría de fruta, Calidades de fruta y Color de fruta. Son los mismos maestros y acciones de Exportaciones y Packing. Especie incorpora Código SAG y Caja Base x pallet en su formulario compartido; no se asignaron valores históricos por suposición.',71:'Recepción a proceso de Productores abre la tabla dinámica de fruta a proceso. Inventario / Reportes / Informe fruta a proceso abre el mismo informe.',72:'Recepción embalada de Productores abre la tabla dinámica de fruta embalada. Inventario / Reportes / Informe fruta embalada abre el mismo informe.'}
for ticket,text in texts.items():
    marker='T%s - maestros y reportes fruta publicados %s'%(ticket,a.commit[:7])
    previous=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',ticket),('body','ilike',marker)]],{'fields':['id']})
    if previous:message=previous[0]['id']
    else:
        assert rpc('helpdesk.ticket','read',[[ticket]],{'fields':['name']})[0]['name'].startswith('T'+str(ticket))
        body='<h3>'+html.escape(marker)+'</h3><p>'+html.escape(text)+'</p>'
        if ticket in (71,72):
            body+='<p>Filtra por temporada, productor, fundo, especie, variedad y lote; agrupa por mes y semana. Producto y embalaje son dimensiones; cantidad de embalajes y kilos usan exactamente el detalle original de recepción. El filtro inicial muestra recepciones hechas; puede quitarlo para consultar pendientes o canceladas. El informe es de solo lectura y no duplica cantidades por operaciones de stock.</p>'
            key='process' if ticket==71 else 'packed'
            body+='<p><a href="https://cerroelplomo.stepsapp.cl/odoo/action-%s">Abrir informe en Cerro</a>.</p>'%proof['cerro']['actions'][key]
        body+='<p>Publicado y verificado en Desarrollo y Cerro El Plomo. Siete pruebas aprobadas en copias nuevas de ambos destinos; conservación exacta de registros. Se repitieron versión, código, formulario, menús, permisos, filtros, tabla dinámica y flujo real de recepción en los destinos publicados. Todas las muestras se revirtieron.</p>'
        body+='<p><a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T70_T72_MAESTROS_RECEPCIONES_2026-10-11.rst">Acta de entrega</a>. Código guardado y subido. Nota interna sin envío de correo.</p>'
        message=rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':ticket,'message_type':'comment','subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
    rpc('helpdesk.ticket','write',[[ticket],{'stage_id':4}],{'context':{'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}})
    saved=rpc('mail.message','read',[[message]],{'fields':['subtype_id','notification_ids']})[0]
    assert saved['subtype_id'][0]==note and not saved['notification_ids']
    assert rpc('helpdesk.ticket','read',[[ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    print('TICKET_DELIVERY_OK',ticket,'note',message,'Solved notifications=0')
