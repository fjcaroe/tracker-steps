"""T109 installed package, native pivot/list/form and actual business profile."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    user = env.ref('base.user_admin')
    assert user.active and not user.share and user.id != 1
    scoped = env(user=user, su=False, context=dict(env.context, allowed_company_ids=user.company_ids.ids))
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
    assert rows, 'Expected current weekly source rows in the destination'
    Form(rows, view=prefix + 'report_form')
    model.read_group([], ['sale_kg:sum', 'estimate_kg:sum'], ['week_start:week'], lazy=False)
    assert not model.has_access('write') and not model.has_access('create') and not model.has_access('unlink')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket': 109, 'versions': EXPECTED,
          'actual_user_id': user.id, 'menu': True, 'pivot_weekly_two_measures': True,
          'native_list_form': True, 'live_grouped_flow': True, 'read_only': True, 'writes': False}))
finally:
    env.cr.rollback()
