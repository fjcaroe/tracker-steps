"""Read-only registry, effective views and navigation checks for scoped fixes."""
from pathlib import Path
from lxml import etree
from odoo.modules.module import get_module_path

for name, version in EXPECTED.items():
    module = env['ir.module.module'].search([('name', '=', name), ('state', '=', 'installed')])
    assert module.latest_version == version, (name, module.latest_version, version)
    assert Path(get_module_path(name)).resolve() == (Path(ROOT) / name).resolve(), name

if 'step_hr_previred' in EXPECTED:
    from odoo.addons.step_hr_previred_simpledigital.controllers.previred_secure import SecuredPreviredExportController
    assert hasattr(SecuredPreviredExportController, '_canonical_response')
    for model, kinds in [('hr.contract', ('form', 'list')), ('hr.payslip', ('form', 'list'))]:
        for kind in kinds:
            arch = etree.fromstring(env[model].get_view(view_type=kind)['arch'].encode())
            assert arch.xpath("//field[@name='step_employee_rut']"), (model, kind)
    menu = env.ref('l10n_cl_simpledigital_payroll.menu_hr_payroll_previred_txt')
    assert menu.action.res_model == 'step.previred.export.wizard'
else:
    arch = etree.fromstring(env['stock.quant.package'].get_view(view_type='form')['arch'].encode())
    for name in ('step_export_shipment_ids', 'step_guide_ids', 'step_invoice_ids', 'step_dus_shipment_id', 'step_bl_shipment_id', 'step_packing_production_id', 'step_packing_line_id', 'step_process_type_id', 'step_process_order_id', 'step_packing_partner_id'):
        assert env['stock.quant.package']._fields[name].type in ('many2one', 'many2many')
        assert arch.xpath("//field[@name='%s']" % name), name
    for name in ('step_shipment', 'step_dispatch_guide', 'step_dus', 'step_invoice', 'step_bl_awb', 'process_type', 'packing_plant', 'process_line', 'op_folio', 'ot_proceso'):
        nodes = arch.xpath("//field[@name='%s']" % name)
        assert all(node.get('readonly') == '1' for node in nodes), name
print('MANAGEMENT_REGISTRY_OK ticket revisions ' + ','.join(EXPECTED))
