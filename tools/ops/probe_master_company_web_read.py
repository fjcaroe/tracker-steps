"""Private-clone-only native web_read of a shared master from one active company."""
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests.common import new_test_user

assert env.cr.dbname.startswith('MANAGEMENT_QA_')
try:
    a = env.company
    b = env['res.company'].create({'name': 'QA web-read other'})
    user = new_test_user(env(context=dict(env.context, no_reset_password=True)), login='qa-web-shared-master',
        groups='base.group_user,step_management_costs.group_management_manager',
        company_id=a.id, company_ids=[Command.set(a.ids)])
    record = env['step.fruit.color'].create({'name': 'QA web-read shared', 'code': 'QA-WEB-COMPANY',
        'company_id': a.id, 'company_ids': [Command.set((a|b).ids)]})
    scoped = record.with_user(user).with_context(allowed_company_ids=a.ids)
    try:
        scoped.web_read({'name': {}, 'company_ids': {'fields': {'display_name': {}}}})
        print('SHARED_MASTER_WEB_READ_OK')
    except AccessError:
        print('SHARED_MASTER_WEB_READ_ACCESS_ERROR')
finally:
    env.cr.rollback()
