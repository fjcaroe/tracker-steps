"""Record the requested Harvest company-selector addendum without notifications."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--reviewed-message', required=True, type=int)
    args = parser.parse_args()
    root = args.evidence
    delivery = json.loads((root/'delivery.json').read_text(encoding='utf-8'))
    flags = ('reviewed', 'company_selector', 'authorized_companies_only',
        'company_round_trip', 'pending_preserved', 'mobile_layout')
    for target in ('development', 'qa-cerro', 'cerro'):
        def read(name):
            return json.loads((root/(target+'-'+name+'.json')).read_text(encoding='utf-8'))
        qa, gui, web, live = [read(name) for name in ('qa', 'gui', 'web', 'live-review')]
        assert qa['feature'] == 'harvest-company-selector' and qa['business_preserved']
        assert qa['readonly_copy'] and qa['harvest_web']['commit'] == delivery['web_commit']
        assert qa['commit'] == web['backend_commit'] == gui['backend_commit'] == delivery['backend_commit']
        assert web['web_commit'] == gui['web_commit'] == live['web_commit'] == delivery['web_commit']
        assert qa['harvest_web']['files'] == web['served'] == delivery['web_files']
        assert gui['database'] == qa['database'] and all(gui[key] for key in flags)
        assert web['backup'] and live['gui'] and live['readonly_live']
        assert len(set(live['company_round_trip'])) > 1
        assert live['company_round_trip'][0] == live['company_round_trip'][-1]
    assert 'CUSTOMER_QA_VERIFY_OK' in (root/'isolation.log').read_text(encoding='utf-8')
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

    ticket = 232
    model = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', model), ('active', '=', True)]])
    assert call('helpdesk.ticket', 'read', [[ticket]], {'fields': ['stage_id']})[0]['stage_id'][0] == 4
    assert not call('mail.message', 'search_count', [[('model', '=', 'helpdesk.ticket'),
        ('res_id', '=', ticket), ('id', '>', args.reviewed_message),
        '|', ('message_type', 'in', ['comment', 'email']), ('attachment_ids', '!=', False)]])
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], {'fields': ['res_id']})[0]['res_id']
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', ticket)]
    before = {name: set(call(name, 'search', [domain])) for name in ('mail.notification', 'mail.mail')}
    body = ('Ampliación solicitada en el chat: selector Empresa dentro de Harvest 0.0.4, '
        'publicado y verificado en Desarrollo, QA-Cerro y Cerro El Plomo. Permite cambiar directamente '
        'entre las empresas autorizadas de la sesión nativa, sin pasar por Odoo. '
        'Las jornadas y trabajadores cambian con la empresa; la tarja y sus entregas pendientes '
        'se conservan al regresar. Cambio bloqueado sin conexión o durante sincronización. '
        '23 pruebas de la app, pruebas funcionales móviles en copias frescas e ida/vuelta en los '
        'tres ambientes publicados. Mismo paquete, respaldos, bloqueo y aislamiento de QA comprobados. '
        'Recargar Harvest para ver Empresa arriba de la pantalla. Web: '+delivery['web_commit']+
        '. Backend conservado: '+delivery['backend_commit']+'.')
    note = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': ticket,
        'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
        'partner_ids': [(6, 0, [])], 'body': '<p>'+html.escape(body)+'</p>'}])
    assert call('helpdesk.ticket', 'read', [[ticket]], {'fields': ['stage_id']})[0]['stage_id'][0] == 4
    for name, ids in before.items():
        assert set(call(name, 'search', [domain])) == ids
    print('HARVEST_COMPANY_DELIVERY_RECORDED ticket=232 note=%s NO_NOTIFICATIONS_OK' % note)


if __name__ == '__main__':
    main()
