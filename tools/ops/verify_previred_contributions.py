"""Verify the deployed canonical export, views and privately supplied cases."""
from pathlib import Path
from lxml import etree
from odoo.modules.module import get_module_path

for name, version in EXPECTED.items():
    module = env['ir.module.module'].search([
        ('name', '=', name), ('state', '=', 'installed')])
    assert module.latest_version == version
    assert Path(get_module_path(name)).resolve() == (Path(ROOT) / name).resolve()

menu = env.ref('l10n_cl_simpledigital_payroll.menu_hr_payroll_previred_txt')
assert menu.action.res_model == 'step.previred.export.wizard'
arch = etree.fromstring(env['step.previred.export.wizard'].get_view(view_type='form')['arch'].encode())
assert arch.xpath("//field[@name='company_id']")
assert arch.xpath("//field[@name='date_from']")
assert hasattr(env['step.previred.extractor'], '_restore_ccaf_fields')
if CASES:
    exec((Path(PROBE_TOOLS) / 'check_payroll_ticket_flows.py').read_text())
env.cr.rollback()
print('MANAGEMENT_REGISTRY_OK canonical Previred contributions')
