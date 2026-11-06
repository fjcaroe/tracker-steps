"""Check native forms and the unchanged reported open-ended movements."""
from pathlib import Path
from lxml import etree
from odoo.modules.module import get_module_path

for name, version in EXPECTED.items():
    installed = env['ir.module.module'].search([
        ('name', '=', name), ('state', '=', 'installed')])
    assert installed.latest_version == version
    assert Path(get_module_path(name)).resolve() == (Path(ROOT) / name).resolve()
menu = env.ref('l10n_cl_simpledigital_payroll.menu_hr_payroll_previred_txt')
assert menu.action.res_model == 'step.previred.export.wizard'
view = etree.fromstring(env['hr.payslip'].get_view(view_type='form')['arch'].encode())
assert view.xpath("//field[@name='previred_movement_ids']")
assert not env['hr.previred.movement']._fields['date_to'].required
assert hasattr(env['step.previred.extractor'], '_allow_open_ended_movements')
if CASES:
    exec((Path(PROBE_TOOLS) / 'check_payroll_ticket_flows.py').read_text())
env.cr.rollback()
print('MANAGEMENT_REGISTRY_OK open-ended Previred movements')
