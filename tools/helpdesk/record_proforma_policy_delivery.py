"""Record T171 review 1 only after the exact package and customer draft pass.

Adds a silent internal acta and resolves the reviewed request. No customer
message, email, fiscal document or business configuration is generated here.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import xmlrpc.client


TICKET = 171
REVIEWED_MESSAGE = 10199
MODULE = 'step_packing_fruit_proforma'
VERSION = '18.0.1.1.0'
TARGETS = ('development', 'cerro', 'qa-cerro')
MARKER = 'MANAGEMENT_REGISTRY_OK draft proforma tax update and native menus/forms'


def payloads(text, marker):
    return [json.loads(line[len(marker):]) for line in text.splitlines() if line.startswith(marker)]


def evidence(root):
    proofs = {}
    for target in TARGETS:
        proof = json.loads((root / (target + '-qa.json')).read_text(encoding='utf-8-sig'))
        deployed = json.loads((root / (target + '-deployment.json')).read_text(encoding='utf-8-sig'))
        assert proof['commit'] == deployed['commit']
        assert proof['release_sha256'] == deployed['sha256']
        assert re.fullmatch('[0-9a-f]{40}', proof['commit'])
        assert re.fullmatch('[0-9a-f]{64}', proof['release_sha256'])
        tests = (root / (target + '-qa.log')).read_text(encoding='utf-8-sig')
        assert re.search(r'0 failed, 0 error\(s\) of 30 tests', tests)
        clone = (root / (target + '-verify.log')).read_text(encoding='utf-8-sig')
        assert MARKER in clone
        live = (root / (target + '-live.log')).read_text(encoding='utf-8-sig')
        assert MARKER in live and 'MANAGEMENT_DEPLOY_OK backup=' in live
        assert any(item['environment'] == target and item['commit'] == proof['commit']
                   for item in payloads(live, 'MANAGEMENT_VERIFY_OK '))
        proofs[target] = proof
    assert len({item['commit'] for item in proofs.values()}) == 1
    assert len({item['release_sha256'] for item in proofs.values()}) == 1
    plan = proofs['cerro']['proforma_policy_plan']
    assert plan['ticket'] == TICKET and plan['reviewed_message_id'] == REVIEWED_MESSAGE
    assert plan['before']['dte'] == '33' and plan['target']['dte'] == '46'
    assert not plan['before']['invoice_ids']
    clone = (root / 'cerro-verify.log').read_text(encoding='utf-8-sig')
    case, = payloads(clone, 'T171_POLICY_CASE_OK ')
    applied, = payloads((root / 'cerro-refresh.log').read_text(encoding='utf-8-sig'), 'PROFORMA_POLICY_APPLIED ')
    for result in (case, applied):
        assert result['id'] == plan['before']['id'] and result['dte'] == '46'
        assert result['previous_name'] == plan['before']['name']
        assert all(result[key] is True for key in (
            'draft_only', 'sources_preserved', 'stock_preserved', 'accounts_preserved', 'idempotent'))
        assert all(abs(actual - expected) < 0.000001
                   for actual, expected in zip(result['totals'], plan['target']['totals']))
    review = json.loads((root / 'pdf-review.json').read_text(encoding='utf-8-sig'))
    assert review['reviewed'] is True
    assert review['sha256'] == hashlib.sha256((root / 't171-review-proforma.pdf').read_bytes()).hexdigest()
    pair, = payloads((root / 'pair.log').read_text(encoding='utf-8-sig'), 'CERRO_RELEASE_PAIR_OK ')
    for target in ('cerro', 'qa-cerro'):
        module = pair[target][MODULE]
        assert module['version'] == VERSION and proofs[target]['commit'] in module['source']
    assert pair['cerro'][MODULE]['sha256'] == pair['qa-cerro'][MODULE]['sha256']
    isolation = (root / 'isolation.log').read_text(encoding='utf-8-sig')
    assert all(marker in isolation for marker in (
        'CUSTOMER_QA_VERIFY_OK', 'CUSTOMER_QA_EGRESS_BLOCKED', 'CUSTOMER_QA_SOURCE_DB_DENIED'))
    return proofs['cerro'], applied


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    args = parser.parse_args()
    proof, case = evidence(args.evidence)
    config = json.loads((Path.home() / '.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/common').authenticate(
        config['db'], config['username'], config['api_key'], {})
    assert uid
    rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
               'mail_notify_force_send': False, 'mail_auto_subscribe_no_notify': True}

    def call(model, method, values, kwargs=None):
        return rpc.execute_kw(config['db'], uid, config['api_key'], model, method, values,
                              dict({'context': context}, **(kwargs or {})))

    ticket = call('helpdesk.ticket', 'read', [[TICKET]], {'fields': ['stage_id', 'sla_ids', 'sla_status_ids']})[0]
    assert ticket['stage_id'][0] == 2 and not ticket['sla_ids'] and not ticket['sla_status_ids']
    model = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', model), ('active', '=', True)]])
    messages = call('mail.message', 'search_read', [[
        ('model', '=', 'helpdesk.ticket'), ('res_id', '=', TICKET), ('id', '>', REVIEWED_MESSAGE)]],
        {'fields': ['id', 'message_type', 'attachment_ids']})
    assert not [item['id'] for item in messages
                if item['message_type'] in ('comment', 'email') or item['attachment_ids']], 'Read new replies first'
    author = call('res.users', 'read', [[uid]], {'fields': ['partner_id']})[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]],
                   {'fields': ['res_id']})[0]['res_id']
    body = (
        'Revisión 1 resuelta: cuando la retención de la especie se configura después de preparar '
        'la proforma, el borrador ya se puede actualizar mediante Actualizar impuestos. '
        'Preparar proformas también actualiza los borradores existentes. Si cambió la configuración, '
        'la aprobación pide actualizar y revisar primero el tipo de documento y los importes. '
        'Se corrigió el borrador reportado: ' + case['previous_name'] + ' pasó a ' + case['name'] +
        ' con DTE 46 y la retención seleccionada en la especie. Se conservan la referencia anterior, '
        'cantidades, precios, neto, tarjas, guías y vínculos de origen. Permanece en borrador, '
        'pendiente de la aprobación habitual del responsable. '
        'Publicado y verificado en Desarrollo, Cerro producción y QA-Cerro. '
        'Treinta pruebas por copia, flujo nativo 33/46, caso original y revisión de su PDF. '
        'No se alteraron impuestos maestros, documentos aprobados, inventario ni contabilidad. '
        'Entrega respaldada. Referencia técnica: ' + proof['commit'] + '; paquete ' + proof['release_sha256'] + '.')
    domain = [('model', '=', 'helpdesk.ticket'), ('res_id', '=', TICKET)]
    original = set(call('mail.message', 'search', [domain]))
    deliveries = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', TICKET)]
    before = {name: set(call(name, 'search', [deliveries])) for name in ('mail.notification', 'mail.mail')}
    note = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': TICKET,
        'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
        'partner_ids': [(6, 0, [])], 'body': '<p>' + html.escape(body) + '</p>'}])
    call('helpdesk.ticket', 'write', [[TICKET], {'stage_id': 4}])
    assert call('helpdesk.ticket', 'read', [[TICKET]], {'fields': ['stage_id']})[0]['stage_id'][0] == 4
    assert set(call('mail.message', 'search', [domain])) == original | {note}
    for name in before:
        assert set(call(name, 'search', [deliveries])) == before[name]
    print('T171_REVIEW1_RECORDED note=%s stage=4 NO_NOTIFICATIONS_OK' % note)


if __name__ == '__main__':
    main()
