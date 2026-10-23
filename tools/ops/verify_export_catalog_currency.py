"""T110/T111 effective native masters, currency bindings and actual-profile forms."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools import config
from odoo.tools.safe_eval import safe_eval

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    previous = config['test_enable']
    config['test_enable'] = True
    try:
        from odoo.tests import Form
    finally:
        config['test_enable'] = previous
    from native_business_profile import scoped_business_environment
    scoped = scoped_business_environment(env)
    user = scoped.user
    prefix = 'step_export_catalog_currency.'
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    for key, model in [('countries', 'res.country'), ('ports', 'l10n_cl.customs_port')]:
        menu = scoped.ref(prefix + key + '_menu')
        assert menu.id in visible and menu.action.res_model == model
        assert menu.parent_id == scoped.ref('step_export.menu_step_export_config_export')
    assert scoped.ref(prefix + 'countries_menu').action == scoped.ref('base.action_country')
    assert scoped['res.country'].has_access('write') and scoped['l10n_cl.customs_port'].has_access('write')
    country = scoped.ref('base.cl')
    assert country._fields['fruit_market_id'].comodel_name == 'step.fruit.market'
    Form(country, view='base.view_country_form')
    port = scoped['l10n_cl.customs_port'].search([], limit=1)
    Form(port or scoped['l10n_cl.customs_port'], view=prefix + 'port_form')
    assert scoped['step.export.export']._fields['origin_port_id'].comodel_name == 'l10n_cl.customs_port'
    programs = scoped['step.export.sales.program']
    listing = etree.fromstring(programs.get_view(view_id=scoped.ref('step_export.view_step_export_sales_program_list').id, view_type='list')['arch'])
    assert not listing.xpath("//field[@name='amount_currency']")
    assert listing.xpath("//field[@name='amount_usd'][@string='Venta USD']")
    form = etree.fromstring(programs.get_view(view_id=scoped.ref('step_export.view_step_export_sales_program_form').id, view_type='form')['arch'])
    for field, currency in [('amount_currency', 'currency_id'), ('amount_usd', 'usd_currency_id')]:
        for node in form.xpath("//field[@name='%s']" % field):
            assert node.get('widget') == 'step_export_amount'
            options = safe_eval(node.get('options'))
            assert options['currency_field'] == currency and options['no_symbol']
    program = programs.search([], limit=1)
    assert program
    Form(program, view='step_export.view_step_export_sales_program_form')
    assert program.currency_id and program.usd_currency_id == scoped.ref('base.USD')
    assets = scoped['ir.asset']._get_asset_paths('web.assets_backend', {})
    assert any('step_export_catalog_currency/static/src/amount.js' in str(path) for path in assets)
    if env.cr.dbname.startswith('MANAGEMENT_QA_'):
        bundle = env['ir.qweb']._get_asset_bundle('web.assets_backend')
        bundle.css(); bundle.js()
        assert not bundle.css_errors
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [110, 111], 'versions': EXPECTED,
          'actual_user_id': user.id, 'scoped_company_id': scoped.company.id, 'target_company_verified': True, 'native_country_and_port_menus': True, 'market_relation': True,
          'native_forms': True, 'usd_list': True, 'operation_usd_bindings': True,
          'numeric_currency_widget': True, 'writes': False}))
finally:
    env.cr.rollback()
