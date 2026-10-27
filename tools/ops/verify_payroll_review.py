"""Read-only native payroll review form, menu, source and error contract."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.exceptions import UserError
from odoo.tools import config

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    company = env.ref('base.main_company')
    users = env['res.users'].search([('active', '=', True), ('share', '=', False), ('id', '!=', 1)])
    users = users.filtered(lambda user: company in user.company_ids and user.has_group('hr_payroll.group_hr_payroll_manager'))
    assert users, 'Existing payroll manager required'
    user = users[:1]
    scoped = env(user=user, su=False, context=dict(env.context, allowed_company_ids=company.ids))
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    menus = scoped['ir.ui.menu'].search([('id', 'in', list(visible)), ('action', '!=', False)])
    assert menus.filtered(lambda menu: menu.action._name == 'ir.actions.act_window' and menu.action.res_model == 'hr.payslip')
    previous = config['test_enable']
    config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    contracts = scoped['hr.contract']
    contract = contracts.search([], limit=1)
    Form(contract or contracts)
    arch = etree.fromstring(contracts.get_view(view_type='form')['arch'])
    buttons = arch.xpath("//button[@name='action_confirm_payroll_migration']")
    assert len(buttons) == 1 and buttons[0].get('confirm')
    assert arch.xpath("//div[@role='alert'][@invisible='not step_payroll_migration_review']")
    payslips = scoped['hr.payslip']
    Form(payslips.search([], limit=1) or payslips)
    employee = scoped['hr.employee'].new({'name': 'QA Review', 'company_id': company.id})
    pending = contracts.new({'name': 'QA Contract', 'employee_id': employee, 'company_id': company.id, 'step_payroll_migration_review': True})
    slip = payslips.new({'employee_id': employee, 'contract_id': pending, 'struct_id': False, 'company_id': company.id})
    try:
        slip.compute_sheet()
    except UserError as error:
        assert 'QA Review' in str(error) and 'Confirmar' in str(error)
    else:
        raise AssertionError('Pending review must block calculation')
    assert pending.step_payroll_migration_review
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 128, 'versions': EXPECTED, 'existing_profile': user.id, 'company_id': company.id, 'native_forms_and_menu': True, 'review_action': True, 'historical_guard_preserved': True, 'writes': False}))
finally:
    env.cr.rollback()
