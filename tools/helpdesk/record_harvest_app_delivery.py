"""Silently close T231/T232 after checking the same backend and web in all targets."""
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
    versions = {'step_cosecha_operations': '18.0.1.0.1', 'step_harvest_launcher': '18.0.1.2.0'}
    for target in ('development', 'qa-cerro', 'cerro'):
        qa = json.loads((root/(target+'-qa.json')).read_text())
        web = json.loads((root/(target+'-web.json')).read_text())
        review = json.loads((root/(target+'-live-review.json')).read_text())
        assert qa['commit'] == web['backend_commit'] == review['backend_commit'] == delivery['backend_commit']
        assert qa['release_sha256'] == delivery['backend_sha256']
        assert web['web_commit'] == review['web_commit'] == delivery['web_commit']
        assert web['served'] == delivery['web_files'] and web['backup']
        assert review['environment'] == target and review['reviewed'] is True
        assert all(review[key] for key in ('tariff_form', 'native_centers', 'harvest_menu', 'native_context', 'no_sample_data'))
        assert re.search(r'0 failed, 0 error\(s\) of 18 tests', (root/(target+'-qa.log')).read_text())
        live = (root/(target+'-live.log')).read_text()
        assert 'MANAGEMENT_VERIFY_OK' in live
        installed = [json.loads(line.split('MANAGEMENT_REGISTRY_OK ', 1)[1])
            for line in live.splitlines() if line.startswith('MANAGEMENT_REGISTRY_OK ')]
        assert any(row['versions'] == versions and row['harvest_own_form_without_studio']
            and row['harvest_api_context_scope'] for row in installed)
    pair = json.loads((root/'pair.json').read_text())
    for module, version in versions.items():
        assert pair['cerro'][module]['version'] == pair['qa-cerro'][module]['version'] == version
        assert pair['cerro'][module]['sha256'] == pair['qa-cerro'][module]['sha256']
    assert all(marker in (root/'isolation.log').read_text() for marker in (
        'CUSTOMER_QA_VERIFY_OK', 'CUSTOMER_QA_EGRESS_BLOCKED', 'CUSTOMER_QA_SOURCE_DB_DENIED'))
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
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], {'fields': ['res_id']})[0]['res_id']
    descriptions = {
        231: 'Las tarifas de Cosecha propia y contratistas abren el formulario Steps con Labor/Tarea y unidad visibles. '
             'Al elegir la labor se propone la unidad de su ficha y se permite seleccionar los centros de costos '
             'de la empresa o compartidos. Se probaron creación, edición y cálculo de tarifas en copias; '
             'las labores, unidades e importes históricos se conservaron.',
        232: 'Harvest abre el ambiente correspondiente y consulta los datos reales de la base, usuario y empresa activa. '
             'Retirados los ejemplos de respaldo. Las jornadas se seleccionan por su registro nativo, '
             'sus tarjas y totales permanecen separados y los pendientes locales no se mezclan entre ambientes o empresas. '
             'La sincronización rechaza un contexto distinto antes de crear registros. Los pendientes antiguos '
             'sin atribución quedan conservados para revisión y descarga, sin cargarse automáticamente.',
    }
    before = {}
    for ticket in descriptions:
        state = call('helpdesk.ticket', 'read', [[ticket]], {'fields': ['stage_id', 'sla_ids', 'sla_status_ids']})[0]
        assert state['stage_id'][0] not in (4, 5) and not state['sla_ids'] and not state['sla_status_ids']
        assert not call('mail.message', 'search_count', [[('model', '=', 'helpdesk.ticket'),
            ('res_id', '=', ticket), ('id', '>', delivery['reviewed_messages'][str(ticket)]),
            '|', ('message_type', 'in', ['comment', 'email']), ('attachment_ids', '!=', False)]])
        domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', ticket)]
        before[ticket] = {name: set(call(name, 'search', [domain])) for name in ('mail.notification', 'mail.mail')}
    for ticket, description in descriptions.items():
        body = ('Publicado y verificado en Desarrollo, QA-Cerro y Cerro El Plomo. '+description+
            ' Mismos paquetes, copias frescas, respaldo, bloqueo compartido y paridad verificados. '
            '18 pruebas de servidor por destino y 14 de la aplicación. Backend: '+delivery['backend_commit']+
            '; SHA-256: '+delivery['backend_sha256']+'. Harvest: '+delivery['web_commit']+'.')
        note = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': ticket,
            'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
            'partner_ids': [(6, 0, [])], 'body': '<p>'+html.escape(body)+'</p>'}])
        call('helpdesk.ticket', 'write', [[ticket], {'stage_id': 4}])
        assert call('helpdesk.ticket', 'read', [[ticket]], {'fields': ['stage_id']})[0]['stage_id'][0] == 4
        domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', ticket)]
        for name, ids in before[ticket].items():
            assert set(call(name, 'search', [domain])) == ids
        print('HARVEST_DELIVERY_RECORDED ticket=%s note=%s stage=4 NO_NOTIFICATIONS_OK' % (ticket, note))


if __name__ == '__main__':
    main()
