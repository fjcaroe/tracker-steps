"""Run in an Odoo shell for the existing Cerro Treasury business profile."""
from odoo.addons.step_account_treasury_reports.hooks import LAUNCHERS


try:
    company = env['res.company'].search([('vat', '=', '76943293-0'), ('parent_id', '=', False)])
    assert len(company) == 1
    users = env['res.users'].search([
        ('active', '=', True), ('share', '=', False), ('id', '!=', 1), ('company_ids', 'in', company.ids),
    ])
    user = users.filtered(lambda u: u.has_group('account.group_account_manager')
                          and u.has_group('step_account_treasury.group_treasury_reader'))[:1]
    assert user, 'An existing Treasury and Accounting reviewer is required'
    scoped = env(user=user, su=False, context=dict(env.context, allowed_company_ids=company.ids))
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    for name, label, parent, action_name, sequence in LAUNCHERS:
        menu = scoped.ref('step_account_treasury.' + name)
        assert menu.id in visible and menu == scoped.ref('step_account_treasury_reports.' + name)
        assert menu.action == scoped.ref('account_reports.' + action_name)
        assert menu.action._get_action_dict()['id'] == menu.action.id
    flows = scoped['step.cashflow']
    dashboard = scoped.ref('step_account_treasury.menu_treasury_dashboard')
    assert dashboard.id in visible and dashboard.action.tag
    assert flows.get_view(view_type='form')['arch'] and flows.get_treasury_dashboard_data()
    assert scoped['account.payment'].get_view(view_type='form')['arch']
    print('T223_ENTERPRISE_FLOW_OK five_menus=True dashboard=True treasury_and_payment_forms=True')
finally:
    env.cr.rollback()
