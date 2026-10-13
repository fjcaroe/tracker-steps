"""T77-T79: guarded progress/closure with internal notes and no notifications."""
import argparse,html,json,re,xmlrpc.client
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('action',choices=('start','close'))
p.add_argument('--ticket',type=int,choices=(77,78,79))
p.add_argument('--evidence',type=Path)
p.add_argument('--commit')
a=p.parse_args()
if a.action=='close':
    assert a.ticket and a.evidence and a.commit and re.fullmatch('[0-9a-f]{40}',a.commit)
    envs=('development',) if a.ticket==77 else ('development','cerro')
    required={77:('menus','forms','pruning_formula','hectare_scaling','approval_revision','summary','real_season_months'),
              78:('menus','forms','daily_5_6_7','manual_preserved','versions_preserved'),
              79:('menus','forms','posting','balanced','daily_rate','three_analytic_plans','duplicate_prevented')}[a.ticket]
    for name in envs:
        folder=a.evidence/name
        qa=json.loads((folder/'qa_passed.json').read_text(encoding='utf-8'));assert qa['commit']==a.commit
        db='LAB_TAREAS' if name=='development' else 'CERRO_EL_PLOMO'
        rows=[r for r in (folder/('verify-'+db+'.log')).read_text(encoding='utf-8').splitlines() if r.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert len(rows)==1
        result=json.loads(rows[0].split(' ',1)[1]);assert result['ticket']==a.ticket and all(result[k] for k in required)
        deployment=json.loads((folder/'deployment.json').read_text(encoding='utf-8'))
        assert deployment['commit']==a.commit and deployment['sha256']==qa['release_sha256']
c=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
url=c.get('url','https://soporte.stepsapp.cl').rstrip('/');assert url.startswith('https://')
uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(c['db'],c['username'],c['api_key'],{})
assert uid
s=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
def rpc(model,method,args,kwargs=None):return s.execute_kw(c['db'],uid,c['api_key'],model,method,args,kwargs or {})
context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}
tickets=[a.ticket] if a.ticket else [77,78,79]
recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','in',tickets),('message_type','in',['comment','email']),('id','>',9402)]],{'fields':['id','res_id','body']})
recent=[m for m in recent if ('T%s - entrega verificada de presupuesto y planificación'%m['res_id']) not in (m.get('body') or '')]
assert not recent,'Review new human feedback before changing tickets: '+str([(m['id'],m['res_id']) for m in recent])
if a.action=='start':
    for ticket in rpc('helpdesk.ticket','read',[tickets],{'fields':['id','name','stage_id']}):
        assert ticket['name'].startswith('T'+str(ticket['id']))
        if ticket['stage_id'][0]==1:rpc('helpdesk.ticket','write',[[ticket['id']],{'stage_id':2}],{'context':context})
        print('TICKET_IN_PROGRESS',ticket['id'])
else:
    note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    author=rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    marker='T%s - entrega verificada de presupuesto y planificación'%a.ticket
    texts={77:'Presupuestos corregidos en Desarrollo: plantilla por temporada con datos, cantidades y valores; unidad de cálculo, rendimiento y Unitario UdM; distribución completa; aplicación por hectáreas; carga de plantilla Excel y carga normalizada; montos directos para centros generales; presupuesto de maquinaria e informes. Se reutilizan los maestros de temporada, especie, variedad, actividad, productos, categorías y estado fenológico BPA. Se conservan documentos, importes y auditoría originales.',
           78:'Publicado en Desarrollo y Cerro El Plomo. Agrónomo conserva el maestro de usuarios y Autoriza el de empleados. Tipo fruta y Mercado se incorporan al registro y al informe semanal. Mercados es el mismo maestro en Productores, Packing y Exportaciones. Estimación diaria (six week) distribuye las próximas tres semanas en cinco, seis o siete días, permite ajustes manuales y conserva versiones y cantidades semanales. Repetir la distribución mantiene los ajustes existentes.',
           79:'Publicado en Desarrollo y Cerro El Plomo: Exportaciones / Gastos exportación / Provisión gastos embarques. Flujo Creado, Validado, Costeado y Contabilizado. Usa maestros existentes y exige coincidencia de programa y embarque. Costea CLP y USD con la tasa diaria de la fecha. Genera un asiento balanceado con cuenta del producto/categoría, cuenta de provisión del diario general y dimensiones analíticas de temporada, especie y embarque. Impide duplicar el asiento y conserva el costeo revisado.'}
    body='<h3>'+html.escape(marker)+'</h3><p>'+html.escape(texts[a.ticket])+'</p>'
    body+='<p>Verificados versión y código instalado, menús y formularios efectivos, permisos, flujo funcional y preservación de los registros. El paquete publicado es el mismo probado en las copias privadas. Las muestras de comprobación se descartaron; no se contabilizaron gastos reales del cliente.</p>'
    if a.ticket==79:body+='<p>Antes de costear, configurar cuenta de gasto en producto o categoría y cuenta de provisión en el diario general. Usar las cuentas analíticas de los maestros de temporada y especie, y seleccionar la cuenta del embarque en su formulario; deben pertenecer a tres planes distintos. Las tasas diarias CLP/USD deben existir para la fecha.</p>'
    if a.ticket==77:body+='<p>Desarrollo es el destino de revisión autorizado. Las plantillas nuevas usan las fechas del maestro Temporada y el dólar estimado de cada mes. Las categorías de fruta, grupos y unidades se seleccionan de sus maestros; no se rellenan registros históricos por suposiciones.</p>'
    body+='<p>Commit '+html.escape(a.commit)+'. <a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T77_T79_IMPLEMENTACION_2026-10-13.rst">Acta técnica de entrega</a>.</p>'
    previous=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',a.ticket),('body','ilike',marker)]],{'fields':['id']})
    if previous:message=previous[0]['id']
    else:message=rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':a.ticket,'message_type':'comment','subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
    saved=rpc('mail.message','read',[[message]],{'fields':['subtype_id','notification_ids']})[0]
    assert saved['subtype_id'][0]==note and not saved['notification_ids']
    rpc('helpdesk.ticket','write',[[a.ticket],{'stage_id':4}],{'context':context})
    assert rpc('helpdesk.ticket','read',[[a.ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
    print('TICKET_DELIVERY_OK',a.ticket,'note',message,'notifications=0')
