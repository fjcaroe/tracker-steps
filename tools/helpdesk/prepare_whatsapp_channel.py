"""Run inside Odoo shell: prepare T48's team channel, disabled and secret-safe.

Launch with root flock -n /run/lock/steps-environments.lock before the Odoo shell.
No provider calls, credentials, ticket messages or customer records are created.
An existing channel is checked, never silently reconfigured.
"""
import json


def prepare():
    ticket = env['helpdesk.ticket'].browse(48).exists()
    assert ticket and ticket.team_id.company_id, 'T48 must identify a company-scoped team'
    channel_model = env['step.helpdesk.wa.channel'].with_company(ticket.team_id.company_id)
    channel = channel_model.search([('name', '=', 'Soporte WhatsApp — T48'), ('team_id', '=', ticket.team_id.id)])
    assert len(channel) <= 1
    if not channel:
        channel = channel_model.create({
            'name': 'Soporte WhatsApp — T48', 'provider': 'meta_cloud',
            'company_id': ticket.team_id.company_id.id, 'team_id': ticket.team_id.id,
            'enabled': False, 'pause_outgoing': True, 'auto_receipt': False,
        })
    assert not channel.enabled and channel.pause_outgoing and not channel.auto_receipt
    assert channel.provider == 'meta_cloud' and channel.company_id == ticket.team_id.company_id
    assert not env['step.helpdesk.wa.conversation'].search_count([('channel_id', '=', channel.id)])
    action = env.ref('step_helpdesk_whatsapp.channels_action').id
    env.cr.commit()
    print('WHATSAPP_CHANNEL_PREPARED ' + json.dumps({
        'channel_id': channel.id, 'action_id': action,
        'enabled': channel.enabled, 'pause_outgoing': channel.pause_outgoing,
        'settings_url': 'https://stepsapp.cl/odoo/action-%s/%s' % (action, channel.id),
    }))


prepare()
