"""T104/T105 effective source, bank forms and existing season-master navigation."""
import importlib
import json
from pathlib import Path
from lxml import etree

try:
    for name, version in EXPECTED.items():
        record = env['ir.module.module'].search([('name', '=', name)])
        assert record.state == 'installed' and record.latest_version == version
        assert Path(importlib.import_module('odoo.addons.' + name).__file__).resolve().parent == Path(ROOT) / name
    form = etree.fromstring(env['account.batch.payment'].get_view(
        view_id=env.ref('account_batch_payment.view_batch_payment_form').id, view_type='form')['arch'])
    assert form.xpath("//button[@name='action_export_security_xls']")
    assert form.xpath("//button[@name='action_export_bancoestado_xlsx']")
    assert form.xpath("//field[@name='security_description']")
    bank = env['res.partner.bank'].get_view(view_id=env.ref('base.view_partner_bank_form').id, view_type='form')['arch']
    assert 'step_security_credit_type' in bank
    action = env.ref('step_hr.action_step_temporada')
    assert action.res_model == 'step.temporada'
    for key in ('export', 'packing', 'producer'):
        menu = env.ref('step_season_navigation.menu_' + key + '_seasons')
        assert menu.action == action and menu.active
        assert menu.id in env['ir.ui.menu']._visible_menu_ids()
    for kind, xmlid in [('form', 'view_temporada_form'), ('list', 'view_step_temporada_list')]:
        assert env['step.temporada'].get_view(view_id=env.ref('step_hr.' + xmlid).id, view_type=kind)['arch']
    env['step.temporada'].search([], limit=5).web_read({'name': {}})
    print('MANAGEMENT_REGISTRY_OK ' + json.dumps({'tickets': [104, 105], 'versions': EXPECTED,
          'security_button': True, 'account_type_field': True, 'bank_form': True,
          'season_menus': 3, 'existing_season_master': True, 'season_forms': True}))
finally:
    env.cr.rollback()
