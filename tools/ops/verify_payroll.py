"""Check the effective payroll registry/forms; every probe rolls back."""
import json
from odoo.exceptions import UserError

assert env.cr.dbname == EXPECTED_DATABASE
try:
    installed = env['ir.module.module'].search([('state', '=', 'installed')]).mapped('name')
    assert 'l10n_cl_simpledigital_payroll' in installed
    assert not any(n.startswith('l10n_cl_hr') or n in ('step_hr_previred_blueminds','step_hr_contract_lifecycle_agriculture') for n in installed)
    for model in ('hr.afp','hr.indicadores','hr.isapre'):
        assert model not in env.registry.models, model
    contract = env['hr.contract']
    form = contract.get_view(view_type='form')['arch']
    for name in ('afp_option','health_institution','step_payroll_migration_review'):
        assert 'name="'+name+'"' in form, name
    assert env['hr.payslip'].get_view(view_type='form')['arch']
    for name in ('step_hr_contract_days','step_hr_previred_simpledigital','step_hr_contract_lifecycle_simpledigital'):
        assert name in installed, name
    archived = env['step.payroll.legacy.snapshot'].search_count([])
    blocked = env['ir.module.module'].search([('name','=','l10n_cl_hr')])
    if blocked:
        try:
            with env.cr.savepoint():
                blocked.button_install()
        except UserError:
            pass
        else:
            raise AssertionError('Retired engine can be reinstalled')
    configured = env['ir.config_parameter'].sudo().get_param('steps.environment.menu_root_xmlids')
    if configured:
        allowed_roots = [env.ref(x,raise_if_not_found=False) for x in json.loads(configured)]
        allowed = {r.id for r in allowed_roots if r}
        visible = env['ir.ui.menu']._visible_menu_ids(debug=True)
        roots = env['ir.ui.menu'].search([('parent_id','=',False),('id','in',list(visible))])
        assert set(roots.ids)<=allowed, 'Unrelated apps visible'
        assert env.ref('hr_work_entry_contract_enterprise.menu_hr_payroll_root').id in visible
    old_structure = env['hr.payroll.structure'].search([('step_legacy_payroll','=',True)],limit=1)
    if old_structure:
        draft = env['hr.payslip'].new({'struct_id':old_structure.id})
        try:
            draft.compute_sheet()
        except UserError:
            pass
        else:
            raise AssertionError('Legacy calculation not blocked')
    print('PAYROLL_REGISTRY_OK '+json.dumps({'database':env.cr.dbname,'simpledigital':True,'legacy_engine_removed':True,'archive_records':archived}))
finally:
    env.cr.rollback()
