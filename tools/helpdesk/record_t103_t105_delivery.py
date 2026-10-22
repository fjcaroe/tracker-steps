"""Silent delivery after isolated functional tests and real destination flows."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('ticket', type=int, choices=(103, 104, 105))
    parser.add_argument('--evidence', type=Path, required=True)
    args = parser.parse_args()
    record = json.loads((args.evidence / 'delivery-reviewed.json').read_text(encoding='utf-8'))
    expected = record[str(args.ticket)]
    for target in ('development', 'cerro'):
        proof = json.loads((args.evidence / (target + '-qa.json')).read_text(encoding='utf-8'))
        log = (args.evidence / (target + '-deploy.log')).read_text(encoding='utf-8')
        gui = expected['gui'][target]
        assert proof['commit'] == expected['commit']
        assert proof['release_sha256'] == expected['sha256']
        assert all(marker in log for marker in ('MANAGEMENT_DEPLOY_OK backup=',
                   'MANAGEMENT_VERIFY_OK', 'MANAGEMENT_REGISTRY_OK', expected['commit']))
        assert gui['version']
        if not all(gui[key] for key in ('form', 'menu', 'flow')):
            # A browser session is optional when the installed destination's
            # actual non-superuser business profile opens native Form bindings
            # and executes menu/document actions. Never replace this with HTTP.
            lines = (args.evidence / (target + '-native-flow.log')).read_text(encoding='utf-8-sig').splitlines()
            payloads = [json.loads(line.split('TICKET_NATIVE_FLOW_OK ', 1)[1])
                        for line in lines if line.startswith('TICKET_NATIVE_FLOW_OK ')]
            database = {'development': 'LAB_TAREAS', 'cerro': 'CERRO_EL_PLOMO'}[target]
            valid = [item['tickets'][str(args.ticket)] for item in payloads
                     if item['database'] == database and str(args.ticket) in item['tickets']]
            assert len(valid) == 1
            flow = valid[0]
            assert flow['native_form'] and flow['existing_profile'] != 1
            if args.ticket == 104:
                assert flow['menu_action'] and not flow['financial_records_created']
            elif args.ticket == 105:
                assert flow['menu_actions'] == 3 and flow['same_master']
                assert flow['existing_record_read'] or flow['master_empty']
            else:
                assert flow['cost_center_actions'] == 13 and flow['existing_application_read']
        if args.ticket == 103:
            assert '"native_models": 33' in log and '"destination_grants_preserved": true' in log
        else:
            assert '"season_menus": 3' in log and '"security_button": true' in log
    config = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(
        config['db'], config['username'], config['api_key'], {})
    assert uid
    proxy = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
               'mail_notify_force_send': False, 'mail_auto_subscribe_no_notify': True}

    def call(model, method, positional, keyword=None):
        return proxy.execute_kw(config['db'], uid, config['api_key'], model, method,
                                positional, dict({'context': context}, **(keyword or {})))

    model = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', model), ('active', '=', True)]])
    ticket = call('helpdesk.ticket', 'read', [[args.ticket]],
                  {'fields': ['stage_id', 'sla_ids', 'sla_status_ids']})[0]
    assert ticket['stage_id'][0] not in (4, 5), 'Inspect a closed/cancelled ticket before retrying'
    assert not ticket['sla_ids'] and not ticket['sla_status_ids']
    assert not call('mail.message', 'search_count', [[('model', '=', 'helpdesk.ticket'),
        ('res_id', '=', args.ticket), ('id', '>', expected['reviewed_message_id']),
        ('message_type', 'in', ['comment', 'email'])]]), 'Read newer replies before delivery'
    descriptions = {
        103: 'Se completó la actualización solicitada en Cerro El Plomo y se verificó también Desarrollo. '
             'Los 33 modelos y los trece accesos agrícolas usan código y formularios nativos. '
             'La migración conserva los registros, identificadores, relaciones y permisos propios del destino. '
             'Se respetan los estados aprobados y el histórico original de tarjas.',
        104: 'Publicado en Desarrollo y Cerro El Plomo el exportador Security desde lotes salientes de Tesorería. '
             'Genera Excel 97–2003 real (.xls), sin encabezado, con las nueve columnas del adjunto. '
             'Valida RUT, cuenta, banco, tipo de abono, CLP y límites del formato, conservando ceros iniciales '
             'y los controles de aprobación y confianza bancaria de Odoo. La exportación no envía pagos al banco.',
        105: 'Publicado en Desarrollo y Cerro El Plomo el acceso Temporadas en Configuración de '
             'Exportaciones, Packing y Productores. Los tres abren el maestro existente step.temporada '
             'y sus formularios, sin duplicar datos.'}
    body = descriptions[args.ticket] + (
        ' El mismo paquete pasó pruebas funcionales y preservación en copias frescas de ambos destinos. '
        'Publicación con respaldo y bloqueo; versión, formularios y acciones de menú revisados '
        'con el perfil existente del destino, además de revisión gráfica en Desarrollo. '
        'Commit: ' + expected['commit'] + '; SHA-256: ' + expected['sha256'] + '.')
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]],
                   {'fields': ['res_id']})[0]['res_id']
    message = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': args.ticket,
        'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
        'partner_ids': [(6, 0, [])], 'body': '<p>' + html.escape(body) + '</p>'}])
    call('helpdesk.ticket', 'write', [[args.ticket], {'stage_id': 4}])
    assert call('helpdesk.ticket', 'read', [[args.ticket]], {'fields': ['stage_id']})[0]['stage_id'][0] == 4
    for resource in ('mail.notification', 'mail.mail'):
        assert not call(resource, 'search_count', [[('mail_message_id', '=', message)]])
    print('TICKET_DELIVERY_RECORDED ticket=%s note=%s stage=4 NO_NOTIFICATIONS_OK' % (args.ticket, message))


if __name__ == '__main__':
    main()
