"""Record T171 delivery as a silent internal note after complete private proofs.

Never solves the ticket, migrates business documents, or sends a customer reply.
"""
import argparse
import html
import json
import math
from pathlib import Path
import re
import xmlrpc.client


TICKET = 171
REVIEWED_MESSAGE = 10174
MODULE = 'step_packing_fruit_proforma'
VERSION = '18.0.1.0.0'
TARGETS = ('development', 'cerro', 'qa-cerro')


def _payloads(log, marker):
    return [json.loads(line[len(marker):]) for line in log.splitlines() if line.startswith(marker)]


def _registry(log):
    values = [entry for entry in _payloads(log, 'MANAGEMENT_REGISTRY_OK ')
              if entry.get('ticket') == TICKET and entry.get('versions', {}).get(MODULE) == VERSION]
    assert values, 'Missing native T171 registry verification'
    result = values[-1]
    assert result.get('existing_profile') not in (None, False, 1)
    assert result.get('live_business_writes') is False
    ui = result.get('ui', {})
    assert all(ui.get(name) is True for name in (
        'menus', 'monthly_form', 'proforma_form', 'species_retention_selector', 'tag_proforma_link'))
    return result


def verify_evidence(root):
    proofs = {}
    counts = {}
    actual = None
    for target in TARGETS:
        proof = json.loads((root / (target + '-qa.json')).read_text(encoding='utf-8-sig'))
        assert re.fullmatch('[0-9a-f]{40}', proof['commit'])
        assert re.fullmatch('[0-9a-f]{64}', proof['release_sha256'])
        tests = (root / (target + '-qa.log')).read_text(encoding='utf-8-sig')
        results = re.findall(r'(\d+) failed,\s*(\d+) error\(s\) of (\d+) tests', tests)
        assert results and all(int(failed) == 0 and int(errors) == 0 for failed, errors, _ in results)
        counts[target] = max(int(count) for _, _, count in results)
        assert counts[target] >= 23, 'Incomplete T171 test scope: ' + target

        live = (root / (target + '-live.log')).read_text(encoding='utf-8-sig')
        assert all(marker in live for marker in (
            'MANAGEMENT_DEPLOY_OK backup=', 'MANAGEMENT_VERIFY_OK ', 'MANAGEMENT_REGISTRY_OK '))
        assert proof['commit'] in live
        assert any(item.get('environment') == target and item.get('commit') == proof['commit']
                   for item in _payloads(live, 'MANAGEMENT_VERIFY_OK '))
        assert _registry(live).get('copy_flow') is None, 'Live validation must remain read-only'

        clone_log = (root / (target + '-verify.log')).read_text(encoding='utf-8-sig')
        flow = _registry(clone_log).get('copy_flow')
        assert isinstance(flow, dict)
        assert all(flow.get(name) is True for name in (
            'accountant_without_purchase_role', 'outside_accounting_before_approval',
            'selected_retention', 'no_official_folio', 'retry_same_documents',
            'stock_preserved', 'html_pdf'))
        assert set(flow.get('draft_documents', [])) == {'33', '46'}
        assert flow.get('large_pdf_annex_rows', 0) >= 1000
        if target == 'cerro':
            cases = _payloads(clone_log, 'T171_ACTUAL_MONTHLY_CASE_OK ')
            assert len(cases) == 1, 'Missing unchanged customer-case proof'
            actual = cases[0]
            assert all(actual.get(name) is True for name in (
                'review_before_cancellation', 'retry_same_invoice', 'monthly_same_proforma',
                'masters_and_stock_preserved', 'new_species_policy_configured_in_copy_only'))
            assert actual.get('dte') == '46' and actual.get('proformas')
            plan = proof.get('monthly_fruit_plan')
            assert isinstance(plan, dict) and plan
            assert set(actual['legacy_cancelled_preserved']) == set(plan['legacy_move_ids'])
            assert actual['currency'] == plan['currency']
            assert set(actual['expense_accounts']) == {plan['expense_code']}
            assert set(actual['taxes']) == set(plan['tax_ids'])
            for name in ('quantity', 'subtotal', 'tax', 'total'):
                assert math.isclose(actual[name], plan[name], rel_tol=0, abs_tol=0.000001)
        proofs[target] = proof

    assert len({entry['commit'] for entry in proofs.values()}) == 1
    assert len({entry['release_sha256'] for entry in proofs.values()}) == 1
    pair_log = (root / 'pair.log').read_text(encoding='utf-8-sig')
    pairs = _payloads(pair_log, 'CERRO_RELEASE_PAIR_OK ')
    assert pairs
    pair = pairs[-1]
    commit = proofs['cerro']['commit']
    for target in ('cerro', 'qa-cerro'):
        module = pair[target][MODULE]
        assert module['version'] == VERSION and commit in module['source']
    assert pair['cerro'][MODULE]['sha256'] == pair['qa-cerro'][MODULE]['sha256']
    isolation = (root / 'isolation.log').read_text(encoding='utf-8-sig')
    assert all(marker in isolation for marker in (
        'CUSTOMER_QA_VERIFY_OK', 'CUSTOMER_QA_EGRESS_BLOCKED', 'CUSTOMER_QA_SOURCE_DB_DENIED'))
    return proofs['cerro'], counts, actual


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    proof, counts, _ = verify_evidence(args.evidence)
    config = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(
        config['db'], config['username'], config['api_key'], {})
    assert uid, 'Authentication failed'
    rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
               'mail_notify_force_send': False, 'mail_auto_subscribe_no_notify': True}

    def call(model, method, values, kwargs=None):
        return rpc.execute_kw(config['db'], uid, config['api_key'], model, method, values,
                              dict({'context': context}, **(kwargs or {})))

    def require_current_review():
        ticket = call('helpdesk.ticket', 'read', [[TICKET]], {'fields': ['stage_id']})[0]
        assert ticket['stage_id'][0] == 2, 'T171 must remain in progress'
        messages = call('mail.message', 'search_read', [[
            ('model', '=', 'helpdesk.ticket'), ('res_id', '=', TICKET), ('id', '>', REVIEWED_MESSAGE)]],
            {'fields': ['id', 'message_type', 'attachment_ids'], 'order': 'id desc'})
        # Do not filter on body: a blank comment with an attachment is a reply.
        replies = [message['id'] for message in messages
                   if message['message_type'] in ('comment', 'email') or message['attachment_ids']]
        assert not replies, 'Read new T171 replies/attachments before recording: ' + str(replies)

    require_current_review()
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]],
                   {'fields': ['res_id']})[0]['res_id']
    body = (
        'T171: publicada la compra mensual mediante Packing / Facturación / Preparar compra mensual. '
        'Primero se crea una proforma fuera de Contabilidad, con resumen por especie y variedad '
        'y anexo de tarjas y guías. Tras la aprobación se prepara una factura nativa en borrador: '
        'DTE 33 con recepción y número del documento del proveedor, o DTE 46 según la política '
        'de la especie. La retención utiliza el impuesto seleccionado y su factor configurado, '
        'sin tasas fijas incorporadas en el código. '
        'Los borradores mensuales anteriores se revisan explícitamente; solo al confirmar su '
        'traslado se cancelan y conservan como historial. La instalación no traslada documentos '
        'ni cambia configuraciones comerciales automáticamente. '
        'El mismo paquete se verificó y publicó en Desarrollo, Cerro producción y QA-Cerro, '
        'con respaldo y bloqueo. Pruebas funcionales en copias: flujo 33/46, anexo de 1.000 filas, '
        'caso real de Cerro, conservación de maestros y stock, reintentos sin duplicados, '
        'formularios, menús, paridad e aislamiento. No se emitieron documentos fiscales, '
        'no se enviaron correos ni se trasladaron borradores reales durante la publicación. '
        'Pendiente de confirmación del cliente; el ticket permanece en curso. Commit: ' +
        proof['commit'] + '; SHA-256: ' + proof['release_sha256'] + '.')
    require_current_review()
    message = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': TICKET,
        'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
        'partner_ids': [(6, 0, [])], 'body': '<p>' + html.escape(body) + '</p>'}])
    for model in ('mail.notification', 'mail.mail'):
        assert not call(model, 'search_count', [[('mail_message_id', '=', message)]])
    assert call('helpdesk.ticket', 'read', [[TICKET]], {'fields': ['stage_id']})[0]['stage_id'][0] == 2
    print('T171_DELIVERY_RECORDED note=%s stage=2 NO_NOTIFICATIONS_OK tests=%s' % (message, counts))


if __name__ == '__main__':
    main()
