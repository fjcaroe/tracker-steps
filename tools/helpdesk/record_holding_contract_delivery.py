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
        assert '18.0.2.11.2' in log
        if target != 'development':
            flow = (root / (target + '-verify.log')).read_text()
            assert 'T170_BRANCH_MONTHLY_FLOW_OK BRANCH_ONLY_BASE_PRODUCT' in flow
            assert 'T170_MISSING_ACCOUNTS_IDENTIFIED' in flow
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
        ('res_id', '=', 170), ('id', '>', 10161), ('message_type', 'in', ['comment', 'email'])]])
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]],
                   {'fields': ['res_id']})[0]['res_id']
    body = ('T170 revisión 3, adjunto 3524 y comentario 10161: publicada en Desarrollo, Cerro '
        'El Plomo producción y QA-Cerro, step_packing_operations 18.0.2.11.2 y '
        'step_packing_holding_contract 18.0.1.0.0. El aviso de cuenta de cargo identifica '
        'todos los productos sin cuenta, con código/nombre y contrato. La comprobación se '
        'hace antes de crear cualquier borrador, sin asignar cuentas automáticamente. '
        'Conserva la búsqueda de precio por Producto base y la lectura de contratos de matriz '
        'con solo la sucursal activa. Copias frescas de los tres destinos: 33 pruebas por copia, '
        'flujo nativo con error identificado y posterior preparación de borrador en rollback, '
        'formulario/menú, mismo paquete, respaldo, bloqueo, paridad y aislamiento verificados. '
        'En el caso comunicado, el producto pendiente es [AR00] del contrato CTR/2026/00011; '
        'el cliente aún debe indicar su cuenta de cargo. No se modificaron cuentas de contratos '
        'ni se generaron facturas reales. Ticket permanece en curso. Commit: ' +
        proofs[0]['commit'] + '; SHA-256: ' + proofs[0]['release_sha256'] + '.')
    message = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': 170,
        'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
        'partner_ids': [(6, 0, [])], 'body': '<p>' + html.escape(body) + '</p>'}])
    for model in ('mail.notification', 'mail.mail'):
        assert not call(model, 'search_count', [[('mail_message_id', '=', message)]])
    assert call('helpdesk.ticket', 'read', [[170]], {'fields': ['stage_id']})[0]['stage_id'][0] == 2
    print('T170_SOFTWARE_DELIVERY_RECORDED note=%s stage=2 NO_NOTIFICATIONS_OK' % message)


if __name__ == '__main__':
    main()
