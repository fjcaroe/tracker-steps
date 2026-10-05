"""Activate only the guide profile; verify with an existing accounting user."""
import json
from unittest.mock import patch

from odoo.modules.module import get_module_path

assert get_module_path('step_support_assistant') == '/opt/luis_odoo18/odoo_agriculture/step_support_assistant'
env['ir.config_parameter'].sudo().set_param('step_support_assistant.guide_profile', 'accounting')
group = env.ref('account.group_account_manager')
user = env['res.users'].sudo().search([
    ('active', '=', True), ('share', '=', False), ('groups_id', 'in', group.id), ('id', '!=', 1),
], limit=1)
assert user, 'An existing accounting user is required'
assistant = env['step.support.assistant'].with_user(user).sudo(False).with_context(
    allowed_company_ids=[user.company_id.id])
with patch('odoo.addons.step_support_assistant.models.assistant.requests.post',
           side_effect=AssertionError('Local queries must not call the provider')):
    bootstrap = assistant.get_bootstrap()
    assert bootstrap['ready'] and bootstrap['guide_profile'] == 'accounting'
    sources = assistant.env['step.assistant.article']._available_sources()
    articles = assistant.env['step.assistant.article'].browse([item['id'] for item in sources])
    assert not articles.filtered(lambda article: article.category == 'colaciones')
    assert articles[0].category == 'accounting'
    accounting_count = len(articles.filtered(lambda article: article.category == 'accounting'))
    assert accounting_count >= 4, 'Basic accounting guides must be visible'
    for app in ('asientos', 'facturas', 'pagos'):
        assert assistant.query_business(app)['status'] == 'answered'

# Generic software usage only: no real account code, amount or document sent.
result = assistant.ask('¿Cómo consulto el saldo acumulado de una cuenta y cómo cambia si indico fecha Desde?')
assert result['status'] == 'answered' and result['sources'], 'Verified accounting help is required'
assert any(source['id'] == env.ref('step_support_assistant.help_accounting_balance').id
           for source in result['sources']), 'The new balance guide must support the answer'
env.cr.commit()
print('SYS_ACCOUNTING_PROFILE_OK ' + json.dumps({
    'approved_guides': len(articles), 'accounting_guides': accounting_count,
    'ai_check': result['status'], 'verified_citations': len(result['sources']),
    'business_api_calls': 0,
}))
