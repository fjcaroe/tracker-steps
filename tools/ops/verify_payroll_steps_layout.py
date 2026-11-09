"""Check the native payslip action and render the approved company's receipt."""
import importlib
import json
from pathlib import Path

from lxml import html


try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    company = env['res.company'].browse(PAYROLL_CASE['company_id']).exists()
    batch = env['hr.payslip.run'].browse(PAYROLL_CASE['batch_id']).exists()
    assert company and batch.company_id == company and batch.slip_ids
    candidates = env['res.users'].search([
        ('share', '=', False), ('id', '!=', 1), ('company_ids', 'in', company.ids),
    ])
    user = candidates.filtered(lambda actor: actor.has_group('hr_payroll.group_hr_payroll_manager')
                               and actor.has_group('hr.group_hr_user'))[:1]
    assert user, 'Use an existing payroll manager in the reported company'
    scoped = env(user=user, su=False, context=dict(env.context, allowed_company_ids=company.ids, lang='es_CL'))
    reports = scoped['ir.actions.report']
    action = scoped.ref('hr_payroll.action_report_payslip')
    assert action.id in {row['id'] for row in reports.get_bindings('hr.payslip')['report']}
    slip = batch.with_env(scoped).slip_ids[:1]
    assert slip.company_id == company and slip.struct_id.report_id == action
    assert slip.get_view(view_type='form')['arch']
    menus = scoped['ir.ui.menu'].browse(list(scoped['ir.ui.menu']._visible_menu_ids()))
    assert menus.filtered(lambda menu: menu.action and menu.action._name == 'ir.actions.act_window'
                          and menu.action.res_model == 'hr.payslip.run')
    assert slip._step_uses_steps_payroll_layout()
    amounts_before = slip.line_ids.read(['code', 'total'])
    rendered, _ = reports._render_qweb_html(action.report_name, slip.ids)
    document = html.fromstring(rendered)
    for marker in ('steps_payslip_title', 'steps_payslip_information', 'steps_payslip_signatures',
                   'payslip_lines_table'):
        assert document.xpath('//*[@id=$marker]', marker=marker), marker
    assert not document.xpath('//*[@id="infos_table"]')
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        pdf, kind = reports._render_qweb_pdf(action.report_name, res_ids=slip.ids)
        assert kind == 'pdf' and pdf.startswith(b'%PDF-')
        (Path(OUTPUT) / 't180-receipt.pdf').write_bytes(pdf)
        alternative = env['res.company'].search([('id', '!=', company.id)], limit=1)
        assert alternative
        assert not env['hr.payslip'].new({'company_id': alternative.id})._step_uses_steps_payroll_layout()
    assert slip.line_ids.read(['code', 'total']) == amounts_before
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({
        'ticket': 180, 'versions': EXPECTED, 'native_action': action.id, 'form_and_menu': True,
        'steps_layout': True, 'stored_amounts_preserved': True,
    }))
finally:
    env.cr.rollback()
