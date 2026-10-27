"""T126 same species records, native forms and existing business profile."""
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
    model = scoped['step.especie']
    arch = etree.fromstring(model.get_view(view_id=scoped.ref('step_hr.view_step_especie_form').id,
                                          view_type='form')['arch'])
    assert arch.xpath("//field[@name='tariff_code']")
    menu = scoped.ref('step_packing_operations.menu_packing_config_species')
    assert menu.action.res_model == 'step.especie'
    assert menu.id in scoped['ir.ui.menu']._visible_menu_ids()
    previous = config['test_enable']; config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    row = model.search([], limit=1)
    assert row, 'Existing business profile cannot access any species'
    Form(row, view='step_hr.view_step_especie_form')
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        before = row.read(['id', 'name', 'cod_especie', 'company_ids'])[0]
        with Form(row, view='step_hr.view_step_especie_form') as form:
            form.tariff_code = '000123.45/A'
        assert row.tariff_code == '000123.45/A'
        assert row.read(['id', 'name', 'cod_especie', 'company_ids'])[0] == before
        print('T126_OPERATOR_NATIVE_FORM_FLOW_OK rollback_required=True')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [126], 'versions': EXPECTED,
        'existing_profile': scoped.uid, 'company_id': scoped.company.id,
        'native_menu_and_form': True, 'same_master': True, 'writes': False}))
finally:
    env.cr.rollback()
