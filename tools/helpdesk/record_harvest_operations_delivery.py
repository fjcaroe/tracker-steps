"""Record verified T101/T102 delivery silently; reject unread replies and mail."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    proofs = []
    for target in ('development', 'cerro'):
        proof = json.loads((args.evidence / (target + '-qa.json')).read_text(encoding='utf-8'))
        log = (args.evidence / (target + '-deploy.log')).read_text(encoding='utf-8')
        assert 'MANAGEMENT_DEPLOY_OK backup=' in log and 'MANAGEMENT_VERIFY_OK' in log
        assert 'MANAGEMENT_REGISTRY_OK' in log and '"nested_fields_valid": true' in log
        proofs.append(proof)
    assert proofs[0]['commit'] == proofs[1]['commit']
    assert proofs[0]['release_sha256'] == proofs[1]['release_sha256']
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
    helpdesk_model = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', helpdesk_model), ('active', '=', True)]])
    bodies = {
        101: 'Procesos de Cosecha está en Cosecha / Recepción. Configuración incorpora Clase de fruta, '
             'Estado de tarja y Tipo de tarja, enlazados a los maestros existentes. Se probaron los menús '
             'y el alta y edición de maestros con perfil administrador agrícola.',
        102: 'El contratista se selecciona en la cabecera de la cuadrilla. La columna redundante de '
             'las líneas fue retirada y los trabajadores se filtran por ese contratista. Se corrigió '
             'la subvista heredada de empleados que impedía abrir el registro de cosecha. Se probó '
             'crear cuadrilla, incorporar trabajador, registrar la cosecha, guardar y reabrir, aprobar '
             'y volver a Ingresado; también se comprobaron registros existentes.',
    }
    latest = {101: 9582, 102: 9586}
    # Preflight every ticket before the first mutation.
    for ticket in bodies:
        record = call('helpdesk.ticket', 'read', [[ticket]],
                      {'fields': ['name', 'stage_id', 'sla_ids', 'sla_status_ids']})[0]
        assert not record['sla_ids'] and not record['sla_status_ids']
        recent = call('mail.message', 'search_read', [[('model', '=', 'helpdesk.ticket'),
                      ('res_id', '=', ticket), ('id', '>', latest[ticket]),
                      ('message_type', 'in', ['comment', 'email'])]], {'fields': ['id', 'body']})
        assert not recent, 'Read newer ticket replies before recording delivery'
    messages = []
    for ticket, body in bodies.items():
        full = ('Publicado y verificado en Desarrollo y Cerro El Plomo. ' + body +
                ' El mismo paquete pasó pruebas funcionales en copias frescas de ambos destinos. '
                'Se conservaron los datos y se respaldaron ambos ambientes. '
                'Paquete: ' + proofs[0]['commit'] + '; SHA-256: ' + proofs[0]['release_sha256'] + '.')
        message = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': ticket,
                       'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
                       'partner_ids': [(6, 0, [])], 'body': '<p>' + html.escape(full) + '</p>'}])
        messages.append(message)
        call('helpdesk.ticket', 'write', [[ticket], {'stage_id': 4}])
        state = call('helpdesk.ticket', 'read', [[ticket]], {'fields': ['stage_id', 'close_date']})[0]
        assert state['stage_id'][0] == 4 and state['close_date']
        print('TICKET_DELIVERY_RECORDED', ticket, 'note=' + str(message), 'stage=4')
    for model in ('mail.notification', 'mail.mail'):
        assert not call(model, 'search_count', [[('mail_message_id', 'in', messages)]])
    print('HARVEST_DELIVERY_NO_NOTIFICATIONS_OK')


if __name__ == '__main__':
    main()
