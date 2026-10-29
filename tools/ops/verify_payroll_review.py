"""Read-only native payroll review form, menu, source and error contract."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.exceptions import UserError
from odoo.tools import config

try:
    assert set(EXPECTED)=={'step_payroll_engine_transition','step_payroll_batch_period'}, 'Both payroll fixes must be installed and tested'
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    company = env.ref('base.main_company')
    users = env['res.users'].search([('active', '=', True), ('share', '=', False), ('id', '!=', 1)])
    users = users.filtered(lambda user: company in user.company_ids and user.has_group('hr_payroll.group_hr_payroll_manager'))
    assert users, 'Existing payroll manager required'
    if 'hr.labor.document' in env:
        users=users.filtered(lambda u: env['hr.labor.document'].with_user(u).check_access_rights('read',raise_exception=False))
    assert users, 'Existing payroll manager with contract-form access required'
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
    if env.cr.dbname.startswith('MANAGEMENT_QA_SYS_'):
        # Replay the reported workers through the actual native wizard. All
        # work-entry generation and draft calculations stay inside this clone
        # transaction, and the final rollback removes them.
        company=env['res.company'].search([('id','=',7),('name','ilike','Emca')])
        assert len(company)==1
        manager=users.filtered(lambda u: company in u.company_ids)[:1]
        assert manager
        business=env(user=manager,su=False,context=dict(env.context,allowed_company_ids=company.ids))
        staff=business['hr.employee'].search([('company_id','=',company.id),('name','in',['Nicol Morales Bueno','Viviana Pereira Díaz'])])
        assert len(staff)==2
        entries=business['hr.work.entry'].search([('employee_id','in',staff.ids),('state','=','conflict'),('date_start','>=','2026-09-30'),('date_stop','<=','2026-10-01')])
        assert entries
        original=entries.read(['state','date_start','date_stop','contract_id'])
        env.cr.execute("SELECT id,md5(to_jsonb(t)::text) FROM hr_payslip t ORDER BY id")
        historical=dict(env.cr.fetchall())
        run=business['hr.payslip.run'].create({'name':'QA T135 October Replay','date_start':'2026-10-01','date_end':'2026-10-31','company_id':company.id})
        wizard=business['hr.payslip.employees'].with_context(active_id=run.id).create({
            'structure_id':business.ref('l10n_cl_simpledigital_payroll.structure_chile').id})
        wizard.employee_ids=staff
        Form(wizard)
        result=wizard.compute_sheet()
        assert result.get('res_model')=='hr.payslip.run' and result.get('res_id')==run.id,result
        assert len(run.slip_ids)==2 and set(run.slip_ids.employee_id.ids)==set(staff.ids)
        assert run.state=='verify' and all(s.state=='verify' for s in run.slip_ids)
        assert entries.read(['state','date_start','date_stop','contract_id'])==original
        env.cr.execute("SELECT id,md5(to_jsonb(t)::text) FROM hr_payslip t WHERE id=ANY(%s) ORDER BY id",[list(historical)])
        assert dict(env.cr.fetchall())==historical,'Existing payslips changed'
        print('T135_NATIVE_OCTOBER_BATCH_OK employees=2 september_conflicts_preserved=True historical_payslips_unchanged=True rollback_required=True')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 128, 'versions': EXPECTED, 'existing_profile': user.id, 'company_id': company.id, 'native_forms_and_menu': True, 'review_action': True, 'historical_guard_preserved': True, 'writes': False}))
finally:
    env.cr.rollback()
