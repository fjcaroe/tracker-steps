"""Verify the partial C-tag split with an existing operator in a private copy."""
import importlib
import json
from pathlib import Path

from lxml import etree
from odoo.tools import config
from native_business_profile import scoped_business_environment

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    scoped = scoped_business_environment(env)
    menu = scoped.ref('step_packing_operations.menu_packing_production')
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    view = scoped.ref('step_packing_operations.view_packing_production_form')
    arch = etree.fromstring(scoped['step.packing.production'].get_view(view_id=view.id, view_type='form')['arch'])
    assert arch.xpath("//page[@name='inputs']/button[@name='action_split_input_tag']")
    clone = env.cr.dbname.startswith('MANAGEMENT_QA_')
    if clone:
        config['test_enable'] = True
        from odoo.addons.step_packing_tag_split.tests.test_split import exercise_split
        exercise_split(env, scoped)
        print('T154_PARTIAL_STOCK_FLOW_OK')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'ticket':154, 'versions':EXPECTED,
        'existing_profile':scoped.uid, 'company_id':scoped.company.id, 'writes':False,
        'native_menu_and_form':True, 'clone_flow':clone}))
finally:
    env.cr.rollback()
