"""Read-only destination acceptance for native dispatch and receipt status."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools.safe_eval import safe_eval

module_name = 'step_packing_interplant'
module = env['ir.module.module'].search([('name', '=', module_name), ('state', '=', 'installed')])
assert module.latest_version == EXPECTED[module_name]
assert Path(importlib.import_module('odoo.addons.' + module_name).__file__).resolve().parent == Path(ROOT) / module_name
if tuple(map(int, module.latest_version.split('.'))) >= (18, 0, 1, 0, 3):
    assert not env['stock.quant.package'].sudo().search_count([
        ('is_fruit_tag', '=', True), ('company_id', '!=', False),
        ('step_packing_company_id', '=', False)]), 'Legacy tag company migration incomplete'
scoped = scoped_business_environment(env)
menu = scoped.ref('step_packing_interplant.receipts_menu')
assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
assert menu.action.res_model == 'stock.picking'
arch = etree.fromstring(scoped['step.dispatch.guide'].get_view(view_type='form')['arch'])
names = [node.get('name') for node in arch.xpath('//sheet//field')]
assert names.index('dispatch_type_id') < names.index('partner_id')
assert arch.xpath('//field[@name="step_destination_picking_id"]')
warehouse_field = arch.xpath('//field[@name="step_destination_warehouse_id"]')[0]
assert safe_eval(warehouse_field.get('context'), {'step_destination_company_id': scoped.company.id}) == {'allowed_company_ids': scoped.company.ids}
assert 'step_packing_interplant.tag_list' in arch.xpath('//field[@name="load_tag_ids"]')[0].get('context')
for field in ('step_tag_kind', 'name', 'step_producer_id', 'box_count', 'step_actual_kg'):
    assert field in scoped.ref('step_packing_interplant.tag_list').arch_db
receipt_form = etree.fromstring(scoped['stock.picking'].get_view(view_type='form')['arch'])
assert receipt_form.xpath('//page[@name="interplant_tags"]')
returned = scoped['stock.picking'].search([('step_fruit_reception_kind', 'in', ['process', 'packed']), ('step_has_fruit_return', '=', True)])
assert not scoped['stock.picking'].search([('id', 'in', returned.ids), ('step_has_fruit_return', '=', False)])
for suffix in ('process', 'packed'):
    action = scoped.ref('step_producer_fruit_reports.action_' + suffix)
    domain = safe_eval(action.domain)
    assert ('picking_id.step_has_fruit_return', '=', False) in domain
    assert not scoped[action.res_model].search(domain + [('picking_id', 'in', returned.ids)])
    receipt_action = scoped.ref('step_inventory_packing.action_steps_fruit_' + suffix + '_reception')
    assert safe_eval(receipt_action.context)['search_default_fruit_current'] == 1
    assert ('step_has_fruit_return', '=', False) in safe_eval(receipt_action.domain)
print('INTERPLANT_REGISTRY_OK ' + json.dumps({'version': module.latest_version,
    'native_form_menu_selector': True, 'pending_receipt_form': True, 'returned_receipts_excluded': len(returned)}))

if env.cr.dbname.startswith('MANAGEMENT_QA_CERRO_'):
    exec(compile((Path(PROBE_TOOLS) / 'probe_interplant_customer_copy.py').read_text(),
        'probe_interplant_customer_copy.py', 'exec'))
