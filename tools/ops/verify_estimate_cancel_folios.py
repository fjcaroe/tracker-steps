"""T107/T108: effective source, actual profile, menus and native forms (read only)."""
import importlib
import json
from pathlib import Path
from lxml import etree
from odoo.tools.safe_eval import safe_eval

try:
    for name, version in EXPECTED.items():
        module = env['ir.module.module'].search([('name', '=', name)])
        assert module.state == 'installed' and module.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    user = env.ref('base.user_admin')
    assert user.active and not user.share and user.id != 1
    scoped = env(user=user, su=False, context=dict(env.context, allowed_company_ids=user.company_ids.ids))
    previous_test = importlib.import_module('odoo').tools.config['test_enable']
    importlib.import_module('odoo').tools.config['test_enable'] = True
    from odoo.tests import Form
    importlib.import_module('odoo').tools.config['test_enable'] = previous_test
    estimate_view = scoped.ref('step_export.view_step_export_estimate_t35_form')
    arch = etree.fromstring(scoped['step.export.estimate'].get_view(view_id=estimate_view.id, view_type='form')['arch'])
    assert arch.xpath("//button[@name='action_cancel_estimate']")
    assert arch.xpath("//field[@name='estimate_cancelled_at']")
    assert 'cancelled' in arch.xpath("//header/field[@name='state']")[0].get('statusbar_visible')
    assert ('cancelled', 'Anulada') in scoped['step.producer.estimate.report']._fields['state']._description_selection(scoped)
    records = scoped['step.export.estimate'].search([], limit=1)
    assert records, 'Expected an existing estimate for the real-profile form check'
    Form(records, view=estimate_view)
    visible = scoped['ir.ui.menu']._visible_menu_ids()
    estimate_actions = scoped['ir.actions.act_window'].search([('res_model', '=', 'step.export.estimate')])
    assert any(menu.id in visible and menu.action in estimate_actions for menu in scoped['ir.ui.menu'].search([('action', '!=', False)]))
    action = scoped.ref('step_export_shipping_design.folio_company_action')
    menu = scoped.ref('step_export_shipping_design.folio_company_menu')
    assert menu.id in visible and menu.action == action
    assert [mode for _, mode in action.views] == ['list', 'form']
    assert safe_eval(action.context) == {'create': False, 'delete': False}
    listing = etree.fromstring(scoped['res.company'].get_view(view_id=action.views[0][0], view_type='list')['arch'])
    assert listing.get('create') == listing.get('delete') == 'false'
    companies = scoped['res.company'].search(safe_eval(action.domain, {'allowed_company_ids': scoped.companies.ids}))
    assert companies and set(companies.ids) <= set(scoped.companies.ids)
    Form(companies[0], view='step_export_shipping_design.folio_company_form')
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [107, 108], 'versions': EXPECTED,
          'actual_user_id': user.id, 'estimate_menu_and_form': True, 'cancel_button_and_audit': True,
          'cancelled_report_state': True, 'folio_menu_existing_company_form': True,
          'company_creation_disabled': True, 'writes': False}))
finally:
    env.cr.rollback()
