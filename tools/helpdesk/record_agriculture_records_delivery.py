"""Record T103 after native migration, preservation and actual GUI review."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    proof = json.loads((args.evidence / 'development-qa.json').read_text(encoding='utf-8'))
    log = (args.evidence / 'development-deploy.log').read_text(encoding='utf-8')
    gui = json.loads((args.evidence / 'gui-reviewed.json').read_text(encoding='utf-8'))
    assert 'MANAGEMENT_DEPLOY_OK backup=' in log and 'MANAGEMENT_VERIFY_OK' in log
    assert 'MANAGEMENT_REGISTRY_OK' in log and '"native_models": 33' in log
    assert '"smart_buttons": 13' in log and '"original_tag_states_preserved": true' in log
    assert '"canonical_tag_states_unified": true' in log
    assert gui['environment'] == 'development' and gui['commit'] == proof['commit']
    assert gui['cost_center_buttons'] and gui['historical_forms'] and gui['existing_records']
    assert gui['menus'] and gui['related_document_navigation']
    assert gui['canonical_states_and_original_history'] and gui['destination_edit_permissions']
    config = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(
        config['db'], config['username'], config['api_key'], {})
    assert uid
    proxy = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True,
               'mail_create_nosubscribe': True, 'mail_notify_force_send': False,
               'mail_auto_subscribe_no_notify': True}

    def call(model, method, positional, keyword=None):
        return proxy.execute_kw(config['db'], uid, config['api_key'], model, method,
                                positional, dict({'context': context}, **(keyword or {})))

    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]],
                   {'fields': ['res_id']})[0]['res_id']
    model = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', model), ('active', '=', True)]])
    record = call('helpdesk.ticket', 'read', [[103]],
                  {'fields': ['stage_id', 'sla_ids', 'sla_status_ids']})[0]
    assert record['stage_id'][0] != 4, 'Ticket already closed; inspect before retrying'
    assert not record['sla_ids'] and not record['sla_status_ids']
    recent = call('mail.message', 'search_read', [[('model', '=', 'helpdesk.ticket'),
                  ('res_id', '=', 103), ('id', '>', 9594),
                  ('message_type', 'in', ['comment', 'email'])]], {'fields': ['id', 'body']})
    assert not recent, 'Read newer ticket replies before recording delivery'
    body = ('Publicado y verificado en Desarrollo. Los trece accesos de centros de costo '
            'usan acciones y formularios versionados. Se convirtieron también los registros '
            'y formularios históricos: 33 modelos, sus líneas, maestros, permisos y secuencias. '
            'Se unificaron los estados operativos con el maestro actual: Vigente a Validada, '
            'Despachada a Desp/Emb, conservando Repaletizada, Procesada y Nula. '
            'Se conservaron IDs, valores, relaciones, estados originales de tarjas como histórico, mensajes '
            'y adjuntos mediante migración sobre las tablas existentes. El mismo paquete pasó '
            'pruebas funcionales y comparación de preservación en una copia fresca de Desarrollo. '
            'Se revisaron menús, formularios históricos y navegación real desde centros de costo, '
            'y se respaldó el ambiente antes de publicar. Paquete: ' + proof['commit'] +
            '; SHA-256: ' + proof['release_sha256'] + '.')
    message = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': 103,
                   'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
                   'partner_ids': [(6, 0, [])], 'body': '<p>' + html.escape(body) + '</p>'}])
    call('helpdesk.ticket', 'write', [[103], {'stage_id': 4}])
    state = call('helpdesk.ticket', 'read', [[103]], {'fields': ['stage_id', 'close_date']})[0]
    assert state['stage_id'][0] == 4 and state['close_date']
    for resource in ('mail.notification', 'mail.mail'):
        assert not call(resource, 'search_count', [[('mail_message_id', '=', message)]])
    print('TICKET_DELIVERY_RECORDED 103 note=' + str(message) + ' stage=4')
    print('AGRICULTURE_DELIVERY_NO_NOTIFICATIONS_OK')


if __name__ == '__main__':
    main()
