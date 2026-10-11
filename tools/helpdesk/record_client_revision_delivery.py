"""Close T63-T67 only after exact-package live checks, using internal notes without mail."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('evidence',type=Path);p.add_argument('--commit',required=True)
    args=p.parse_args();assert re.fullmatch('[0-9a-f]{40}',args.commit)
    proof={}
    for environment,db in [('development','LAB_TAREAS'),('cerro','CERRO_EL_PLOMO')]:
        folder=args.evidence/environment
        qa=json.loads((folder/'qa_passed.json').read_text())
        assert qa['commit']==args.commit
        log=(folder/('verify-'+db+'.log')).read_text(encoding='utf-8')
        rows=[line for line in log.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert len(rows)==1
        result=json.loads(rows[0].split(' ',1)[1]);assert result['tickets']==[63,64,65,66,67]
        assert all(result[k] for k in ('quality_shared','color_crud','program_transport','gantt_pivot_list','current_version_only','role_domains','native_incoterm_and_sale_mode'))
        assert result['report_quantities_usd']==10000 and result['pdf_titles']==['Sales Order','Invoice']
        proof[environment]=result
    config=json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url=config.get('url','https://soporte.stepsapp.cl').rstrip('/');assert url.startswith('https://')
    uid=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(config['db'],config['username'],config['api_key'],{})
    assert uid;obj=xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    def rpc(model,method,a,k=None):return obj.execute_kw(config['db'],uid,config['api_key'],model,method,a,k or {})
    recent=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','in',[63,64,65,66,67]),('subtype_id','=',1),('message_type','in',['comment','email']),('id','>',9322)]],{'fields':['id','res_id']})
    assert not recent, 'New human feedback requires review before closing: '+str(recent)
    note=rpc('ir.model.data','search_read',[[('module','=','mail'),('name','=','mt_note')]],{'fields':['res_id']})[0]['res_id']
    author=rpc('res.users','read',[[uid]],{'fields':['partner_id']})[0]['partner_id'][0]
    descriptions={
        63:'Calidades de fruta usa el mismo maestro de Gestión y Costos desde Configuraciones / Fruta de Exportaciones y Packing. Color de fruta tiene un único maestro nuevo accesible desde ambos módulos, con permisos por empresa.',
        64:'Tipo de embarque está debajo de Empresa en el encabezado del programa de ventas: marítimo, aéreo y terrestre. Se conserva al crear nuevas versiones. Los históricos solo se completan desde relaciones inequívocas.',
        65:'Informe programa de ventas está en Exportaciones / Planificación, con Gantt, tabla dinámica y detalle. Permite filtrar especie, tipo de embarque, programa y temporada; agrupar por mes o semana; consultar contenedores, pallets, cajas, kilos y venta USD. El filtro inicial Vigentes evita sumar versiones reemplazadas. Para revisar borradores, quite Vigentes y seleccione Creados / validados.',
        66:'La hoja Exportación de Contactos incluye naviera/aerolínea, consignatario, notify, agencia de carga y agente de aduana. Cada selector del instructivo filtra por su rol; un contacto puede tener varios. Se conservaron las relaciones anteriores.',
        67:'Incoterm se trasladó desde Otra información al encabezado y Modalidad de venta usa el maestro existente. Los títulos impresos son Sales Order para Nota de venta e Invoice para Proforma.',
    }
    context={'tracking_disable':True,'mail_notrack':True,'mail_create_nosubscribe':True,'mail_auto_subscribe_no_notify':True}
    for ticket,text in descriptions.items():
        marker='T%s - revisión comercial publicada %s' % (ticket,args.commit[:7])
        previous=rpc('mail.message','search_read',[[('model','=','helpdesk.ticket'),('res_id','=',ticket),('body','ilike',marker)]],{'fields':['id']})
        if previous:
            message=previous[0]['id']
        else:
            title=rpc('helpdesk.ticket','read',[[ticket]],{'fields':['name']})[0]['name'];assert title.startswith('T'+str(ticket))
            body='<h3>'+html.escape(marker)+'</h3><p>'+html.escape(text)+'</p>'
            body+='<p>Publicado y verificado en Desarrollo y Cerro El Plomo, después de trece pruebas funcionales y conservación exacta de registros en copias frescas de ambos destinos. Se repitieron formularios, menús, flujo de ventas, datos del Gantt, totales USD y ambos PDF en los ambientes publicados. Las muestras de prueba se revirtieron.</p>'
            if ticket==65:
                body+='<p><a href="https://cerroelplomo.stepsapp.cl/odoo/action-%s">Abrir informe en Cerro</a>.</p>' % proof['cerro']['actions']['program_report']
            body+='<p><a href="https://github.com/fjcaroe/tracker-steps/blob/codex/ambientes-canonicos-reparacion/docs/T63_T67_REVISION_COMERCIAL_2026-10-11.rst">Acta de entrega y uso</a>. Código guardado y subido. Evidencia interna, sin envío de correo.</p>'
            message=rpc('mail.message','create',[{'model':'helpdesk.ticket','res_id':ticket,'message_type':'comment','subtype_id':note,'author_id':author,'body':body,'partner_ids':[(5,0,0)]}])
        rpc('helpdesk.ticket','write',[[ticket],{'stage_id':4}],{'context':context})
        saved=rpc('mail.message','read',[[message]],{'fields':['subtype_id','notification_ids']})[0]
        assert saved['subtype_id'][0]==note and not saved['notification_ids']
        assert rpc('helpdesk.ticket','read',[[ticket]],{'fields':['stage_id']})[0]['stage_id'][0]==4
        print('TICKET_DELIVERY_OK',ticket,'note',message,'Solved notifications=0')


if __name__=='__main__':main()
