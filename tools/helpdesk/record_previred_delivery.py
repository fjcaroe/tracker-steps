"""Record a verified T172/T173 delivery without sending notifications."""
import argparse
import base64
import html
import json
from pathlib import Path
import xmlrpc.client


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ticket', type=int, choices=(172, 173), required=True)
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--acta', type=Path, required=True)
    parser.add_argument('--text', type=Path, required=True)
    args = parser.parse_args()
    proof = json.loads(args.proof.read_text(encoding='utf-8-sig'))
    targets = {'development', 'sys', 'demo-sys'} if args.ticket == 172 else {'development', 'sys'}
    assert set(proof['environments']) == targets
    assert all(item['functional'] and item['service_active'] and item['tests'] > 0
               and item['business_preserved'] for item in proof['environments'].values())
    assert proof['reported_case']['ticket'] == args.ticket
    assert proof['reported_case']['download_verified'] and proof['reported_case']['payroll_preserved']
    acta = args.acta.read_bytes()
    paragraphs = args.text.read_text(encoding='utf-8-sig').strip().split('\n\n')
    assert paragraphs and acta
    c = json.loads((Path.home()/'.odoo/helpdesk_api.json').read_text(encoding='utf-8-sig'))
    url = c['url'].rstrip('/')
    uid = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/common').authenticate(
        c['db'], c['username'], c['api_key'], {})
    assert uid
    proxy = xmlrpc.client.ServerProxy(url+'/xmlrpc/2/object')
    context = {'tracking_disable': True, 'mail_notrack': True,
               'mail_create_nosubscribe': True, 'mail_notify_force_send': False,
               'mail_auto_subscribe_no_notify': True}

    def call(model, method, values, **kwargs):
        return proxy.execute_kw(c['db'], uid, c['api_key'], model, method, values,
                                dict(context=context, **kwargs))

    tid = args.ticket
    ticket = call('helpdesk.ticket', 'read', [[tid]], fields=['stage_id', 'sla_ids', 'sla_status_ids'])[0]
    assert ticket['stage_id'][0] not in (4, 5)
    assert not ticket['sla_ids'] and not ticket['sla_status_ids']
    assert not call('mail.message', 'search_count', [[
        ('model', '=', 'helpdesk.ticket'), ('res_id', '=', tid),
        ('id', '>', proof['reviewed_message_id']),
        ('message_type', 'in', ['comment', 'email'])]]), 'Review the new response before closure'
    models = call('ir.model', 'search', [[('model', '=', 'helpdesk.ticket')]])
    assert not call('base.automation', 'search_count', [[('model_id', 'in', models), ('active', '=', True)]])
    domain = [('mail_message_id.model', '=', 'helpdesk.ticket'), ('mail_message_id.res_id', '=', tid)]
    deliveries = {model: set(call(model, 'search', [domain]))
                  for model in ('mail.notification', 'mail.mail')}
    attachment = call('ir.attachment', 'create', [{
        'name': f'Acta T{tid}.txt', 'res_model': 'helpdesk.ticket', 'res_id': tid,
        'mimetype': 'text/plain', 'datas': base64.b64encode(acta).decode()}])
    assert base64.b64decode(call('ir.attachment', 'read', [[attachment]], fields=['datas'])[0]['datas']) == acta
    author = call('res.users', 'read', [[uid]], fields=['partner_id'])[0]['partner_id'][0]
    subtype = call('ir.model.data', 'search_read', [[('module', '=', 'mail'), ('name', '=', 'mt_comment')]], fields=['res_id'])[0]['res_id']
    body = ''.join('<p>'+html.escape(text)+'</p>' for text in paragraphs)
    message = call('mail.message', 'create', [{
        'model': 'helpdesk.ticket', 'res_id': tid, 'message_type': 'comment',
        'subtype_id': subtype, 'author_id': author, 'partner_ids': [(6, 0, [])],
        'body': body, 'attachment_ids': [(4, attachment)]}])
    saved = call('mail.message', 'read', [[message]], fields=['body', 'attachment_ids'])[0]
    assert saved['body'] == body and attachment in saved['attachment_ids']
    call('helpdesk.ticket', 'write', [[tid], {'stage_id': 4}])
    assert call('helpdesk.ticket', 'read', [[tid]], fields=['stage_id'])[0]['stage_id'][0] == 4
    for model, before in deliveries.items():
        assert set(call(model, 'search', [domain])) == before
    print(f'T{tid}_DELIVERY_VERIFIED message={message} attachment={attachment} NO_NOTIFICATIONS_OK')


if __name__ == '__main__':
    main()
