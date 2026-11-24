"""Close T233/T234 only after matching native, browser and publication evidence."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    root = args.evidence
    delivery = json.loads((root/'delivery.json').read_text(encoding='utf-8'))
    flags = ('plot_selector', 'plots_filtered_by_center', 'plot_selection_reset',
        'plot_all_location_modes', 'mobile_layout', 'harvest_dashboard_filters',
        'harvest_dashboard_table', 'harvest_dashboard_settings')
    for target in ('development', 'qa-cerro', 'cerro'):
        def read(suffix):
            return json.loads((root/(target+'-'+suffix+'.json')).read_text(encoding='utf-8'))
        qa, web, copy, live = [read(name) for name in ('qa', 'web', 'copy-review', 'live-review')]
        assert qa['commit'] == web['backend_commit'] == copy['backend_commit'] == live['backend_commit'] == delivery['backend_commit']
        assert qa['release_sha256'] == copy['backend_sha256'] == delivery['backend_sha256']
        assert web['web_commit'] == copy['web_commit'] == live['web_commit'] == delivery['web_commit']
        assert web['served'] == delivery['web_files'] and web['backup']
        assert copy['database'] == qa['database'] and copy['reviewed']
        assert all(copy[key] for key in flags)
        assert live['reviewed'] and live['readonly_live'] and live['plot_visible_without_configuration']
        assert all(live[key] for key in ('harvest_dashboard_filters', 'harvest_dashboard_table', 'harvest_dashboard_settings'))
        log = (root/(target+'-qa.log')).read_text(encoding='utf-8')
        count = re.findall(r'0 failed, 0 error\(s\) of (\d+) tests when loading database', log)
        assert count and int(count[-1]) >= 28
        assert 'test_harvest_without_a_tariff_uses_its_native_variety_species' in log
        assert 'test_workers_hours_and_native_costs_do_not_rewrite_original_lines' in log
        assert 'test_plot_catalog_tracks_center_and_upload_saves_native_relation' in log
    assert all(marker in (root/'isolation.log').read_text(encoding='utf-8') for marker in
        ('CUSTOMER_QA_VERIFY_OK', 'CUSTOMER_QA_EGRESS_BLOCKED', 'CUSTOMER_QA_SOURCE_DB_DENIED'))
    pair = json.loads((root/'pair.json').read_text(encoding='utf-8'))
    for module in ('step_cosecha_operations', 'step_harvest_launcher'):
        assert all(pair['cerro'][module][key] == pair['qa-cerro'][module][key] for key in ('version', 'sha256'))
    config = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(
        config['db'], config['username'], config['api_key'], {})
    assert uid
    rpc = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
        'mail_notify_force_send': False, 'mail_auto_subscribe_no_notify': True}

    def call(model, method, values, kwargs=None):
        return rpc.execute_kw(config['db'], uid, config['api_key'], model, method,
            values, dict({'context': context}, **(kwargs or {})))

    model = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', model), ('active', '=', True)]])
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], {'fields': ['res_id']})[0]['res_id']
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    descriptions = {
        233: 'La captura mostraba el campo oculto por el modo de ubicación guardado en el navegador. '
             'Harvest 0.0.6 muestra Cuartel en Nueva OT tanto en móvil como en escritorio y en los tres modos. '
             'Se habilita al elegir un centro con cuarteles, limpia la selección al cambiar de centro y '
             'conserva la relación nativa al guardar y sincronizar. Se exige en modo Cuartel y es opcional '
             'en los demás modos para conservar los pendientes y flujos anteriores.',
        234: 'El panel Cosecha inicia en Hoy, agrega Ayer y filtra por Especie y Fundo desde los maestros '
             'nativos de la empresa. La tabla ocupa el ancho disponible y muestra OP, P/C, Fecha, Especie, '
             'Dotación, Horas totales, Kilos, Kg promedio, Estado, Costo total y Costo kilo. '
             'Dotación cuenta trabajadores distintos; horas suma las horas nativas. Kg promedio = '
             'Kilos / Horas totales × Horas por jornada. Configuración → Parámetros del panel permite '
             'cambiar las horas por empresa, inicialmente 8. Costo kilo = Costo total / Kilos; '
             'sin base o sin costear se muestra guion. Control operativo queda al final en horizontal. '
             'La tabla permite recorrer todos los registros filtrados. Consultar costos conserva '
             'las líneas, remuneraciones y tarifas originales.',
    }
    before = {}
    for ticket in descriptions:
        state = call('helpdesk.ticket', 'read', [[ticket]], {'fields': ['stage_id', 'sla_ids', 'sla_status_ids']})[0]
        assert state['stage_id'][0] == 2 and not state['sla_ids'] and not state['sla_status_ids']
        assert not call('mail.message', 'search_count', [[('model', '=', 'helpdesk.ticket'),
            ('res_id', '=', ticket), ('id', '>', delivery['reviewed_messages'][str(ticket)]),
            '|', ('message_type', 'in', ['comment', 'email']), ('attachment_ids', '!=', False)]])
        domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', ticket)]
        before[ticket] = {name: set(call(name, 'search', [domain])) for name in ('mail.notification', 'mail.mail')}
    for ticket, text in descriptions.items():
        body = ('Publicado y verificado en Desarrollo, QA-Cerro y Cerro El Plomo. '+text+
            ' Recargar la aplicación una vez para cargar la entrega. Mismos paquetes, copias frescas, '
            'pruebas funcionales, respaldo, bloqueo y paridad comprobados. 28 pruebas nativas por destino '
            'y 23 de Harvest. Backend '+delivery['backend_commit']+'; Harvest '+delivery['web_commit']+'.')
        if ticket == 234:
            body += ' Estados con costo: '+', '.join(delivery['cost_state_labels'])+'.'
        note = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': ticket,
            'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
            'partner_ids': [(6, 0, [])], 'body': '<p>'+html.escape(body)+'</p>'}])
        call('helpdesk.ticket', 'write', [[ticket], {'stage_id': 4}])
        assert call('helpdesk.ticket', 'read', [[ticket]], {'fields': ['stage_id']})[0]['stage_id'][0] == 4
        domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', ticket)]
        for name, ids in before[ticket].items():
            assert set(call(name, 'search', [domain])) == ids
        print('HARVEST_PANEL_DELIVERY_RECORDED ticket=%s note=%s NO_NOTIFICATIONS_OK' % (ticket, note))


if __name__ == '__main__':
    main()
