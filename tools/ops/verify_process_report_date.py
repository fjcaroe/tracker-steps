"""Verify the deployed Packing report against existing validated receipts."""
import importlib
import json
from pathlib import Path

from lxml import etree
from odoo import fields
from odoo.tools import float_is_zero
from odoo.tools.safe_eval import safe_eval

from native_business_profile import scoped_business_environment


name = 'step_producer_fruit_reports'
module = env['ir.module.module'].search([('name', '=', name), ('state', '=', 'installed')])
assert module.latest_version == EXPECTED[name]
assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
scoped = scoped_business_environment(env)
visible = scoped['ir.ui.menu']._visible_menu_ids()
results = {}
for kind in ('process', 'packed'):
    menu = scoped.ref('step_packing_ticket_revision.' + kind + '_receptions')
    action = scoped.ref(name + '.action_' + kind)
    assert menu.id in visible and menu.action == action
    assert menu.parent_id == scoped.ref('step_packing_ticket_revision.reports')
    assert action.view_mode == 'pivot,list' and safe_eval(action.context)['search_default_done'] == 1
    domain = safe_eval(action.domain)
    assert ('picking_id.step_has_fruit_return', '=', False) in domain
    report = scoped[action.res_model].with_context(tz='America/Santiago')
    pivot = etree.fromstring(report.get_view(view_id=dict((kind, view) for view, kind in action.views)['pivot'],
                                             view_type='pivot')['arch'])
    assert pivot.xpath("/pivot/field[@name='reception_date'][@type='col'][@interval='week']")
    search = etree.fromstring(report.get_view(view_id=action.search_view_id.id, view_type='search')['arch'])
    assert search.xpath("//filter[@name='done']") and search.xpath("//filter[@date='reception_date']")
    rows = report.search(domain + [('state', '=', 'done')], limit=50)
    different = 0
    for picking in rows.picking_id:
        receipt_rows = rows.filtered(lambda row: row.picking_id == picking)
        expected = (picking.scheduled_date or picking.date_done if kind == 'process'
                    else picking.date_done or picking.scheduled_date) or picking.date
        assert set(receipt_rows.mapped('reception_date')) == {expected}
        different += bool(picking.date_done and picking.scheduled_date
                          and picking.date_done.date() != picking.scheduled_date.date())
        group, = report.read_group([('id', 'in', receipt_rows.ids)], ['packaging_qty:sum', 'kilos:sum'],
                                   ['reception_date:day'])
        day = fields.Datetime.context_timestamp(report, expected).date().isoformat()
        assert group['__range']['reception_date:day']['from'][:10] == day
        assert all(float_is_zero(group[metric] - sum(receipt_rows.mapped(metric)), precision_digits=6)
                   for metric in ('packaging_qty', 'kilos'))
    results[kind] = {'receipts_checked': len(rows.picking_id), 'distinct_dates': different}
print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 216, 'version': module.latest_version,
      'packing_menus': True, 'pivot_and_search': True, 'results': results}))
