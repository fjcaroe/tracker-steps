"""Run via Odoo shell. Read only; output metadata/counts, never business values."""
from unittest.mock import patch
import json

group = env.ref('account.group_account_manager')
user = env['res.users'].sudo().search([('active', '=', True), ('share', '=', False), ('groups_id', 'in', group.id), ('id', '!=', 1)], limit=1)
if not user:
    raise RuntimeError('No existing internal accounting user for read-only verification')
assistant = env['step.support.assistant'].with_user(user).sudo(False).with_context(allowed_company_ids=[user.company_id.id])
catalog = assistant.get_business_catalog()
result_counts = {}
with patch('odoo.addons.step_support_assistant.models.assistant.requests.post', side_effect=AssertionError('Unexpected provider call')):
    for item in catalog:
        if item['key'] == 'saldos':
            continue
        result = assistant.query_business(item['key'])
        assert result['status'] == 'answered'
        assert len(result['records']) <= 20
        result_counts[item['key']] = len(result['records'])
    account_env = assistant.env['account.account']
    account = account_env.search([('company_ids', 'in', [user.company_id.id])], limit=1)
    if account:
        balance = assistant.query_business('saldos', reference=account.code)
        assert balance['status'] == 'answered' and len(balance['records']) == 1
    bootstrap = assistant.get_bootstrap()
print('ASSISTANT_BUSINESS_SMOKE_OK ' + json.dumps({'visible_counts': result_counts, 'balance_checked': bool(account), 'ai_ready': bootstrap['ready'], 'guides': len(bootstrap['articles'])}))
env.cr.rollback()
