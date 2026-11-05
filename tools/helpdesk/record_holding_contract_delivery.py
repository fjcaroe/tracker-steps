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
        assert '18.0.2.11.1' in log
        if target != 'development':
            assert 'T170_BRANCH_MONTHLY_FLOW_OK BRANCH_ONLY_BASE_PRODUCT' in (root / (target + '-verify.log')).read_text()
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
        ('res_id', '=', 170), ('id', '>', 10159), ('message_type', 'in', ['comment', 'email'])]])
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]],
                   {'fields': ['res_id']})[0]['res_id']
    body = ('T170 revisión 2, adjunto 3522 y comentario 10159: publicado en Desarrollo, Cerro '
        'El Plomo producción y QA-Cerro. Versiones step_packing_operations 18.0.2.11.1 y '
        'step_producers 18.0.1.9.1. El precio se busca mediante el Producto base registrado '
        '(AR151 → AR00), usando los kilos netos de cada detalle para precios por peso. '
        'Se conserva el producto y la cantidad de stock de las tarjas; la factura usa el producto '
        'base y la unidad del contrato. Los contratos de matrices autorizadas se leen con solo '
        'la sucursal seleccionada, sin ampliar permisos de escritura ni acceso a empresas ajenas. '
        'El error de precio detalla OT, tarja, contrato, producto, producto de precio, especie, '
        'variedad, categoría y calibre. Mismo paquete probado en copias de los tres destinos, '
        'con flujo nativo, formulario, menú, respaldo, bloqueo, paridad e aislamiento. '
        'El adjunto confirma CTR/2026/00011. La cuenta de cargo sigue vacía en el contrato; '
        'queda pendiente que el cliente indique la cuenta. No se generaron facturas reales ni '
        'se cambiaron precios o contratos. Ticket permanece en curso. Commit: ' +
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
