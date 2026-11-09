"""Recalculate copies of the reported slips while preserving the originals."""
import importlib
import json
from pathlib import Path

from odoo.tools import float_compare


try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    company = env['res.company'].browse(PAYROLL_CASE['company_id']).exists()
    batch = env['hr.payslip.run'].browse(PAYROLL_CASE['batch_id']).exists()
    assert company and batch.company_id == company
    assert env['ir.config_parameter'].get_param(PAYROLL_COMPANY_KEY) == str(company.id)
    users = env['res.users'].search([
        ('share', '=', False), ('id', '!=', 1), ('company_ids', 'in', company.ids),
    ]).filtered(lambda user: user.has_group('hr_payroll.group_hr_payroll_manager')
               and user.has_group('hr.group_hr_user'))
    assert users
    business = env(user=users[:1], su=False, context=dict(env.context, allowed_company_ids=company.ids,
        tracking_disable=True, mail_create_nosubscribe=True, lang='es_CL'))
    originals = batch.with_env(business).slip_ids
    assert len(originals) == 3
    structure = business.ref('l10n_cl_simpledigital_payroll.structure_chile')
    assert originals.struct_id == structure
    assert originals.get_view(view_type='form')['arch']
    menus = business['ir.ui.menu'].browse(list(business['ir.ui.menu']._visible_menu_ids()))
    assert menus.filtered(lambda menu: menu.action and menu.action._name == 'ir.actions.act_window'
                          and menu.action.res_model == 'hr.payslip.run')
    gross = structure.rule_ids.filtered(lambda rule: rule.code == 'GROSS')
    assert len(gross) == 1
    assert gross._compute_rule({'payslip': originals[:1],
                                'categories': {'IMP': 50, 'BASIC': 0, 'ALW': 0}}) == (50, 1.0, 100.0)
    fields = ['code', 'total', 'slip_id']
    previous = originals.line_ids.read(fields)
    computed = []
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        for original in originals:
            draft = original.copy({'state': 'draft', 'move_id': False, 'payslip_run_id': False, 'line_ids': False})
            assert draft.company_id == company and not draft.move_id
            draft.compute_sheet()
            lines = draft.line_ids
            values = {line.code: line.total for line in lines}
            taxable = sum(lines.filtered(lambda line: line.category_id.code == 'IMP'
                                         and line.sequence < gross.sequence).mapped('total'))
            compare = lambda first, second: float_compare(first, second, precision_rounding=company.currency_id.rounding)
            assert taxable > 0 and compare(taxable, values['GROSS']) == 0, values
            assert abs(values['AFP']) > 0 and abs(values['SALUD']) > 0, values
            assert compare(values['NET'], values['GROSS'] + values['habIMP'] - values['TOTAL_DSCTOS']) == 0, values
            computed.append({code: values[code] for code in ('GROSS', 'AFP', 'SALUD', 'NET')})
    assert originals.line_ids.read(fields) == previous
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 181, 'versions': EXPECTED, 'form_and_menu': True,
        'clone_results': computed, 'original_amounts_preserved': True,
    }))
finally:
    env.cr.rollback()
