"""Record T170 software delivery silently; leave business decisions open."""
import argparse
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    root = args.evidence
    proofs = []
    for target in ('development', 'cerro', 'qa-cerro'):
        proof = json.loads((root / (target + '-qa.json')).read_text())
        log = (root / (target + '-live.log')).read_text(encoding='utf-8-sig')
        assert all(marker in log for marker in (
            'MANAGEMENT_DEPLOY_OK backup=', 'MANAGEMENT_VERIFY_OK', 'MANAGEMENT_REGISTRY_OK'))
        assert proof['commit'] in log
        assert '18.0.2.12.0' in log
        assert '0 failed, 0 error(s) of 39 tests' in (root / (target + '-qa.log')).read_text()
        if target == 'cerro':
            flow = (root / (target + '-verify.log')).read_text()
            marker = 'T170_ACTUAL_MONTHLY_CASE_OK '
            actual = json.loads(next(line[len(marker):] for line in flow.splitlines() if line.startswith(marker)))
            assert actual['masters_and_stock_preserved'] and actual['retry_same_draft'] and actual['branch_only']
            assert proof['monthly_fruit_plan']
        elif target == 'qa-cerro':
            assert 'T170_NATIVE_EXPENSE_FLOW_OK' in (root / (target + '-verify.log')).read_text()
        proofs.append(proof)
    assert len({p['commit'] for p in proofs}) == 1
    assert len({p['release_sha256'] for p in proofs}) == 1
    assert 'CERRO_RELEASE_PAIR_OK' in (root / 'pair.log').read_text()
    assert 'CUSTOMER_QA_VERIFY_OK' in (root / 'isolation.log').read_text()
    c = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(c['db'], c['username'], c['api_key'], {})
    assert uid
    rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
               'mail_notify_force_send': False, 'mail_auto_subscribe_no_notify': True}

    def call(model, method, values, kwargs=None):
        return rpc.execute_kw(c['db'], uid, c['api_key'], model, method, values,
                              dict({'context': context}, **(kwargs or {})))

    ticket = call('helpdesk.ticket', 'read', [[170]], {'fields': ['stage_id']})[0]
    assert ticket['stage_id'][0] == 2
    assert not call('mail.message', 'search_count', [[('model', '=', 'helpdesk.ticket'),
        ('res_id', '=', 170), ('id', '>', 10164), ('message_type', 'in', ['comment', 'email'])]])
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]],
                   {'fields': ['res_id']})[0]['res_id']
    body = ('T170 revisión integral de los comentarios 10163/10164 y adjuntos 3525/3526. '
        'La cuenta de gastos del producto estaba configurada: el módulo exigía indebidamente '
        'otra cuenta en la línea del contrato. Ahora utiliza las cuentas nativas del producto '
        'o categoría en la sucursal; respeta una cuenta contractual específica y la posición fiscal. '
        'Los impuestos se calculan por Odoo, conservando IVA de matriz y su mapeo fiscal. '
        'Admite el diario de matriz compatible sin cambiar la empresa de la factura. '
        'Se reprodujo primero el fallo original en copia fresca y se verificó después el mismo '
        'caso sin sustituir cuentas, contratos ni precios por datos ficticios. '
        'Caso verificado: contrato ' + actual['contract'] + ', OT ' + ', '.join(actual['orders']) +
        ', cantidad ' + str(actual['quantity']) + ', moneda ' + actual['currency'] +
        ', neto ' + str(actual['subtotal']) + ', impuesto ' + str(actual['tax']) +
        ', total ' + str(actual['total']) + '. Cuenta(s): ' + ', '.join(actual['accounts']) + '. '
        'Borrador nativo balanceado, formulario, diario, producto, UdM, cuenta por pagar e '
        'idempotencia verificados. Maestros y stock conservados; todo el ensayo se revierte. '
        'Publicado el mismo paquete en Desarrollo, Cerro producción y QA-Cerro, versión '
        'step_packing_operations 18.0.2.12.0: 39 pruebas por destino, respaldo, bloqueo, '
        'paridad e aislamiento. No se requieren cambios adicionales en la cuenta mostrada '
        'por el cliente. No se generaron facturas reales. Listo para confirmación del cliente; '
        'el ticket permanece en curso. Commit: ' + proofs[0]['commit'] +
        '; SHA-256: ' + proofs[0]['release_sha256'] + '.')
    message = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': 170,
        'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
        'partner_ids': [(6, 0, [])], 'body': '<p>' + html.escape(body) + '</p>'}])
    for model in ('mail.notification', 'mail.mail'):
        assert not call(model, 'search_count', [[('mail_message_id', '=', message)]])
    assert call('helpdesk.ticket', 'read', [[170]], {'fields': ['stage_id']})[0]['stage_id'][0] == 2
    print('T170_SOFTWARE_DELIVERY_RECORDED note=%s stage=2 NO_NOTIFICATIONS_OK' % message)


if __name__ == '__main__':
    main()
