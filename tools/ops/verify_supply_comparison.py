"""T109 installed package, native pivot/list/form and actual business profile."""
import importlib
import json
import math
from pathlib import Path
from lxml import etree
from odoo.tools import config

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    from native_business_profile import scoped_business_environment
    scoped = scoped_business_environment(env)
    user = scoped.user
    previous = config['test_enable']
    config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    prefix = 'step_export_supply_comparison.'
    action = scoped.ref(prefix + 'report_action')
    menu = scoped.ref(prefix + 'report_menu')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids() and menu.action == action
    assert menu.parent_id == scoped.ref('step_export.menu_step_export_ops')
    assert action.res_model == 'step.export.supply.comparison' and action.view_mode == 'pivot,list,form'
    model = scoped[action.res_model]
    for mode in ('pivot', 'list', 'form', 'search'):
        arch = etree.fromstring(model.get_view(view_id=scoped.ref(prefix + 'report_' + mode).id, view_type=mode)['arch'])
        assert arch.tag == mode
        if mode == 'pivot':
            assert arch.xpath("//field[@type='measure']/@name") == ['sale_kg', 'estimate_kg']
            assert arch.xpath("//field[@type='col']/@interval") == ['week']
    rows = model.search([], limit=1)
    programs = scoped['step.export.sales.program'].search([('state', '=', 'current')])
    estimates = scoped['step.export.estimate'].search([('state', '=', 'current')])
    sale_weeks = programs.mapped('line_ids')
    estimate_weeks = estimates.mapped('estimate_line_ids.week_line_ids')
    assert model.search_count([]) == len(sale_weeks) + len(estimate_weeks)
    total = model.read_group([], ['sale_kg:sum', 'estimate_kg:sum'], [])[0]
    assert math.isclose(total['sale_kg'] or 0, sum(sale_weeks.mapped('kg_qty')), rel_tol=1e-9, abs_tol=1e-6)
    assert math.isclose(total['estimate_kg'] or 0, sum(estimate_weeks.mapped('export_kg')), rel_tol=1e-9, abs_tol=1e-6)
    # An empty result is valid when neither source has current weekly rows.
    # Constructing Form without saving also verifies that empty-state binding.
    Form(rows or model, view=prefix + 'report_form')
    model.read_group([], ['sale_kg:sum', 'estimate_kg:sum'], ['week_start:week'], lazy=False)
    assert not model.has_access('write') and not model.has_access('create') and not model.has_access('unlink')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 109, 'versions': EXPECTED,
          'actual_user_id': user.id, 'scoped_company_id': scoped.company.id, 'target_company_verified': True, 'menu': True, 'pivot_weekly_two_measures': True,
          'native_list_form': True, 'live_grouped_flow': True, 'read_only': True, 'source_totals_match': True, 'empty_report': not bool(rows), 'writes': False}))
finally:
    env.cr.rollback()
