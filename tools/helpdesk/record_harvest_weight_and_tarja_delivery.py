"""Record the verified T242 and T243 release as silent Helpdesk notes."""
import argparse
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import re
import xmlrpc.client


TICKETS = {242: (10673, 'Peso estándar toma los kg por caja del envase Cosecha de la OT. '
    'La cantidad de trato se registra en cajas. El pesaje manual permite dos decimales.'),
    243: (10677, 'La opción Sin tarja desactiva el vínculo trabajador–folio y permite registrar '
    'entregas con su trabajador, cajas y kilos. El cierre de la OT funciona sin abrir ni cerrar una tarja.')}
TARGETS = ('development', 'qa-cerro', 'cerro')
VERSIONS = {'step_harvest_launcher': '18.0.1.6.0', 'step_cosecha_operations': '18.0.1.2.0'}


def verify_release(root):
    stage = None
    counts = []
    for target in TARGETS:
        qa = json.loads((root/f'{target}-qa.json').read_text(encoding='utf-8'))
        web = json.loads((root/f'{target}-web.json').read_text(encoding='utf-8'))
        browser = json.loads((root/f'{target}-live-review.json').read_text(encoding='utf-8'))
        copy = json.loads((root/f'{target}-copy-review.json').read_text(encoding='utf-8'))
        assert qa['environment'] == web['environment'] == browser['environment'] == target
        assert qa['backend_versions'] == VERSIONS and qa['business_preserved'] is True
        assert qa['commit'] == web['backend_commit'] == copy['backend_commit'] == browser['backend_commit']
        assert qa['release_sha256'] == copy['backend_sha256']
        assert web['web_commit'] == browser['web_commit'] == copy['web_commit'] and web['backup']
        assert all(copy[key] is True for key in ('reviewed', 'native_standard_weight', 'native_manual_hundredths',
            'native_capture_without_tarja', 'sync_idempotency', 'ot_close', 'ot_send_confirmation'))
        assert all(browser[key] is True for key in ('native_context', 'native_weight_form', 'harvest_launcher',
            'standard_weight_readonly', 'manual_weight_hundredths', 'capture_without_tarja', 'worker_tarja_association_off'))
        assert browser['server_writes'] is False and browser['version'] == '0.0.11'
        identity = (qa['commit'], qa['release_sha256'], web['web_commit'], web['served'])
        if stage is None:
            stage = identity
        assert identity == stage
        log = (root/f'{target}-qa.log').read_text(encoding='utf-8')
        count = re.findall(r'0 failed, 0 error\(s\) of (\d+) tests when loading database', log)
        assert count and int(count[-1]) >= 81
        counts.append(int(count[-1]))
    pair = json.loads((root/'pair.json').read_text(encoding='utf-8'))
    for name, version in VERSIONS.items():
        assert pair['cerro'][name]['version'] == pair['qa-cerro'][name]['version'] == version
        assert pair['cerro'][name]['sha256'] == pair['qa-cerro'][name]['sha256']
    isolation = (root/'isolation.log').read_text(encoding='utf-8')
    assert all(marker in isolation for marker in ('CUSTOMER_QA_VERIFY_OK', 'CUSTOMER_QA_EGRESS_BLOCKED', 'CUSTOMER_QA_SOURCE_DB_DENIED'))
    return stage, counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    root = args.evidence.resolve()
    assert not root.is_relative_to(Path(__file__).resolve().parents[2])
    package, counts = verify_release(root)
    config = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = 'https://soporte.stepsapp.cl'
    uid = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(config['db'], config['username'], config['api_key'], {})
    assert uid
    rpc = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True, 'mail_create_nosubscribe': True,
               'mail_notify_force_send': False, 'mail_auto_subscribe_no_notify': True}

    def call(model, method, values, **kwargs):
        return rpc.execute_kw(config['db'], uid, config['api_key'], model, method, values, dict(kwargs, context=context))

    model = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', model), ('active', '=', True)]])
    author = call('res.users', 'read', [[uid]], fields=['partner_id'])[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_note')]], fields=['res_id'])[0]['res_id']
    before = {}
    for ticket, (reviewed, _) in TICKETS.items():
        state = call('helpdesk.ticket', 'read', [[ticket]], fields=['stage_id', 'team_id', 'sla_ids', 'sla_status_ids'])[0]
        assert state['team_id'][0] == 1 and state['stage_id'][0] not in (4, 5)
        assert not state['sla_ids'] and not state['sla_status_ids']
        assert not call('mail.message', 'search_count', [[('model', '=', 'helpdesk.ticket'),
            ('res_id', '=', ticket), ('id', '>', reviewed), '|',
            ('message_type', 'in', ['comment', 'email']), ('attachment_ids', '!=', False)]])
        domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', ticket)]
        before[ticket] = (domain, {name: set(call(name, 'search', [domain])) for name in ('mail.notification', 'mail.mail')})

    if not args.apply:
        print('HARVEST_T242_T243_PREFLIGHT_OK')
        return
    closed = {}
    for ticket, (_, description) in TICKETS.items():
        body = ('Harvest 0.0.11 publicado y verificado en Desarrollo, QA-Cerro y Cerro El Plomo. '
            f'{description} Copias frescas, respaldos, bloqueo y paridad verificados. '
            f'Pruebas nativas por destino: {counts[0]}, {counts[1]} y {counts[2]}. '
            f'Backend {package[0][:8]} y Harvest {package[2][:8]}.')
        note = call('mail.message', 'create', [{'model': 'helpdesk.ticket', 'res_id': ticket,
            'message_type': 'comment', 'subtype_id': subtype, 'author_id': author,
            'partner_ids': [(6, 0, [])], 'body': '<p>'+html.escape(body)+'</p>'}])
        assert call('helpdesk.ticket', 'write', [[ticket], {'stage_id': 4}])
        state = call('helpdesk.ticket', 'read', [[ticket]], fields=['stage_id', 'close_date'])[0]
        assert state['stage_id'][0] == 4 and state['close_date']
        domain, counts_before = before[ticket]
        for name, previous in counts_before.items():
            assert set(call(name, 'search', [domain])) == previous
        closed[ticket] = dict(state, note=note)
    with (root/'ticket-closure.json').open('x', encoding='utf-8') as stream:
        json.dump({'verified_at': datetime.now(timezone.utc).isoformat(), 'tickets': closed}, stream, indent=2)
    print('HARVEST_T242_T243_CLOSED_NO_NOTIFICATIONS', json.dumps(closed))


if __name__ == '__main__':
    main()
