"""Check the effective payroll registry/forms; every probe rolls back."""
import json
import importlib
from pathlib import Path
from odoo.exceptions import UserError

assert env.cr.dbname == EXPECTED_DATABASE
try:
    installed = env['ir.module.module'].search([('state', '=', 'installed')]).mapped('name')
    assert 'l10n_cl_simpledigital_payroll' in installed
    versions = {}
    for name, expected in EXPECTED_VERSIONS.items():
        if name not in installed:
            continue
        actual = env['ir.module.module'].search([('name', '=', name)]).latest_version
        assert actual == expected, (name, actual, expected)
        source = Path(importlib.import_module('odoo.addons.' + name).__file__).resolve()
        assert source.is_relative_to(Path(EXPECTED_ROOT).resolve()), (name, str(source))
        versions[name] = actual
    assert not any(n.startswith('l10n_cl_hr') or n in ('step_hr_previred_blueminds','step_hr_contract_lifecycle_agriculture') for n in installed)
    for model in ('hr.afp','hr.indicadores','hr.isapre'):
        assert model not in env.registry.models, model
    retired = {'hr.causal.termino', 'hr.afp', 'hr.indicadores', 'hr.isapre'}
    menus = env['ir.ui.menu'].sudo().with_context(**{'ir.ui.menu.full_list': True}).search([
        ('action', '!=', False),
    ])
    assert not menus.filtered(lambda m: m.action._name == 'ir.actions.act_window' and
                              m.action.res_model in retired), 'Menu still targets a retired payroll master'
    contract = env['hr.contract']
    for field in ('analytic_account_id','health_institution','pension_option','has_gratification','is_retired_elderly','contract_type_id'):
        assert not contract._fields[field].required, 'Incomplete historical contract cannot load: '+field
    assert not env['hr.employee']._fields['hr_commune'].required
    form = contract.get_view(view_type='form')['arch']
    for name in ('afp_option','health_institution','step_payroll_migration_review'):
        assert 'name="'+name+'"' in form, name
    assert env['hr.payslip'].get_view(view_type='form')['arch']
    assert env['hr.employee'].get_view(view_type='form')['arch']
    for name in ('step_hr_contract_days','step_hr_previred_simpledigital','step_hr_contract_lifecycle_simpledigital'):
        assert name in installed, name
    archived = env['step.payroll.legacy.snapshot'].search_count([])
    packing=env.ref('step_packing_operations.menu_packing_operations_root',raise_if_not_found=False)
    if packing:
        for xmlid in ('step_packing.menu_step_packing_root','step_packing.menu_packing_fruta_root'):
            old=env.ref(xmlid,raise_if_not_found=False)
            assert not old or old.parent_id==env.ref('step_environment_policy.packing_history')
    if env.ref('step_cosecha.menu_step_cosecha_root',raise_if_not_found=False):
        assert env.ref('step_environment_policy.harvest_master_variedad').action.res_model=='step.variedad'
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
    print('PAYROLL_REGISTRY_OK '+json.dumps({'database':env.cr.dbname,'simpledigital':True,'legacy_engine_removed':True,'archive_records':archived,'versions':versions}))
finally:
    env.cr.rollback()
