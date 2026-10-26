"""Record T123 Development review readiness silently, without closing scope."""
import argparse
import html
import json
from pathlib import Path
import re
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args(); root = args.evidence
    expected = json.loads((root / 'delivery-reviewed.json').read_text())
    proof = json.loads((root / 'development-qa.json').read_text())
    assert proof['commit'] == expected['commit'] and proof['release_sha256'] == expected['sha256']
    qa = (root / 'development-qa.log').read_text(encoding='utf-8-sig')
    counts = re.findall(r'0 failed, 0 error\(s\) of ([0-9]+) tests', qa)
    assert counts and max(map(int, counts)) >= 24
    flow = (root / 'development-clone-flow.log').read_text(encoding='utf-8-sig')
    assert 'T123_NATIVE_INVOICE_PAYMENT_FLOW_OK' in flow
    deploy = (root / 'development-deploy.log').read_text(encoding='utf-8-sig')
    assert all(marker in deploy for marker in ('MANAGEMENT_DEPLOY_OK backup=', 'MANAGEMENT_VERIFY_OK', expected['commit']))
    checks = [json.loads(line.split('MANAGEMENT_REGISTRY_OK ', 1)[1]) for line in deploy.splitlines()
              if line.startswith('MANAGEMENT_REGISTRY_OK ')]
    assert any(item.get('existing_profile', 1) != 1 and item.get('native_menu_and_form')
               and item.get('invoice_selection') and item.get('one_counterpart_per_invoice')
               and item.get('writes') is False for item in checks)
    body = ('T123 disponible para revisión en Desarrollo. En el pago de cliente o proveedor, '
            'Seleccionar facturas pendientes permite agregar una o varias facturas y aplicar importes completos o parciales. '
            'El total es la suma distribuida y cada factura tiene su propia contrapartida en el comprobante. '
            'Confirmar concilia cada factura con su línea y actualiza el saldo usando el motor nativo, '
            'conservando sus ajustes de cambio y bimoneda. Se comprueban saldos actuales, empresa, tercero, '
            'permisos y coherencia del comprobante; los pagos confirmados conservan su distribución. '
            'Veinticuatro pruebas y flujo completo de cobro/pago con perfil existente aprobados en copia fresca; '
            'el mismo paquete fue instalado con respaldo y bloqueo y se verificaron versión, origen, menús y formularios. '
            'No se contabilizaron pagos reales ni se alteraron facturas históricas durante la instalación. '
            'El adjunto no define destinos adicionales: se solicitó confirmar si corresponde también Cerro y QA-Cerro. '
            'El ticket permanece En curso hasta definir ese alcance. '
            'Commit: ' + expected['commit'] + '; SHA-256: ' + expected['sha256'] + '.')
    c = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(c['db'], c['username'], c['api_key'], {})
    assert uid; rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
               'mail_notify_force_send': False, 'mail_auto_subscribe_no_notify': True}
    def call(model, method, values, kwargs=None):
        return rpc.execute_kw(c['db'], uid, c['api_key'], model, method, values,
                              dict({'context': context}, **(kwargs or {})))
    ticket = call('helpdesk.ticket', 'read', [[123]], {'fields': ['stage_id', 'sla_ids', 'sla_status_ids']})[0]
    assert ticket['stage_id'][0] in (1, 2) and not ticket['sla_ids'] and not ticket['sla_status_ids']
    models = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', models), ('active', '=', True)]])
    assert not call('mail.message', 'search_count', [[('model', '=', 'helpdesk.ticket'), ('res_id', '=', 123),
        ('id', '>', expected['reviewed_message_id']), ('message_type', 'in', ['comment', 'email'])]])
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], {'fields': ['res_id']})[0]['res_id']
    message = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': 123, 'message_type': 'comment',
        'subtype_id': subtype, 'author_id': author, 'partner_ids': [(6, 0, [])], 'body': '<p>' + html.escape(body) + '</p>'}])
    call('helpdesk.ticket', 'write', [[123], {'stage_id': 2}])
    for model in ('mail.notification', 'mail.mail'):
        assert not call(model, 'search_count', [[('mail_message_id', '=', message)]])
    print('T123_REVIEW_RECORDED note=%s stage=2 NO_NOTIFICATIONS_OK scope_pending=True' % message)


if __name__ == '__main__': main()
