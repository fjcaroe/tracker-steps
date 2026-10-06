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
