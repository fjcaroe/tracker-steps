"""T162 verifies the actual report action and the identified detached record."""
import importlib
import json
from pathlib import Path

from lxml import etree

from odoo.tools.safe_eval import safe_eval
from native_business_profile import scoped_business_environment


try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    packages = env['stock.quant.package'].search([('name', '=', 'FC2110260017')])
    orders = packages.step_packing_production_id
    assert len(orders) <= 1
    scoped = scoped_business_environment(env, company=orders.company_id if orders else None)
    menu = scoped.ref('step_packing_ticket_revision.tag_report')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    domain = safe_eval(menu.sudo().action.domain)
    assert ('step_packing_detached_duplicate', '=', False) in domain
    order_model = scoped['step.packing.production']
    order_form = scoped.ref('step_packing_operations.view_packing_production_form')
    arch = etree.fromstring(order_model.get_view(view_id=order_form.id, view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_reopen_quadrature']")
    assert 'action_reopen_close' in etree.tostring(order_form._get_combined_arch(), encoding='unicode')
    summary = {'tickets': [162, 163], 'versions': EXPECTED}
    if len(packages) > 1:
        result = scoped['stock.quant.package'].search(domain + [('id', 'in', packages.ids)])
        assert result.ids == (orders.step_packing_output_tag_ids & packages).ids
        assert len(result) == 1 and len(packages.exists()) == len(packages)
        summary.update(folio=result.name, historical_records=len(packages), report_rows=len(result))
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps(summary))
finally:
    env.cr.rollback()
