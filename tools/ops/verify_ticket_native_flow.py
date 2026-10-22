"""Read actual destination forms/actions with its existing business admin.

Run with Odoo shell and TICKETS injected by the caller. All ORM activity is
rolled back. Mutating business flows are covered in the isolated destination
copy; this probe never creates payments, seasons or documents in production.
"""
import json
from lxml import etree
from odoo.tests import Form

try:
    user = env.ref('base.user_admin')
    assert user.active and not user.share and user.id != 1
    scoped = env(user=user, su=False, context=dict(env.context,
        allowed_company_ids=user.company_ids.ids))
    results = {}
    if set(TICKETS) & {104, 105}:
        assert user.has_group('account.group_account_manager')
        batch = scoped['account.batch.payment']
        assert batch.has_access('read') and batch.has_access('create')
        action = scoped.ref('step_account_treasury_batch.menu_treasury_vendor_batch').action
        assert action.res_model == batch._name
        view = scoped.ref('account_batch_payment.view_batch_payment_form')
        arch = etree.fromstring(batch.get_view(view_id=view.id, view_type='form')['arch'])
        assert arch.xpath("//button[@name='action_export_security_xls']")
        # No context manager: its __exit__ saves. Construct only, so this
        # exercises real defaults/bindings without creating a financial record.
        form = Form(batch.with_context(default_batch_type='outbound'), view=view.id)
        assert form.batch_type == 'outbound'
        assert not form.security_description
        bank = scoped['res.partner.bank']
        assert 'step_security_credit_type' in bank.get_view(
            view_id=scoped.ref('base.view_partner_bank_form').id, view_type='form')['arch']
        Form(bank, view=scoped.ref('base.view_partner_bank_form').id)
        results['104'] = {'native_form': True, 'menu_action': True, 'existing_profile': user.id,
                          'financial_records_created': False}
        visible = scoped['ir.ui.menu']._visible_menu_ids()
        season_action = scoped.ref('step_hr.action_step_temporada')
        season = scoped['step.temporada'].search([], limit=1)
        for key in ('export', 'packing', 'producer'):
            menu = scoped.ref('step_season_navigation.menu_' + key + '_seasons')
            assert menu.id in visible and menu.action == season_action
            assert season_action.res_model == 'step.temporada'
            form = Form(season or scoped['step.temporada'], view=scoped.ref('step_hr.view_temporada_form').id)
            if season:
                season.web_read({'name': {}})
                assert form.name == season.name
        assert scoped.ref('step_season_navigation.menu_packing_seasons').parent_id == scoped.ref(
            'step_packing_operations.menu_packing_operations_config')
        results['105'] = {'native_form': True, 'menu_actions': 3, 'same_master': True,
                          'existing_profile': user.id, 'existing_record_read': bool(season),
                          'master_empty': not bool(season)}
    if 103 in TICKETS:
        from odoo.addons.step_agriculture_records.models.cost_center import ACTIVITIES
        center = scoped['account.analytic.account'].search([], limit=1)
        assert center
        checked = 0
        for key, (_, model, relation) in ACTIVITIES.items():
            if scoped[model].has_access('read'):
                action = center.with_context(agriculture_activity=key).action_agriculture_activity()
                assert action['res_model'] == model and action['domain'] == [(relation, '=', center.id)]
                scoped[model].search(action['domain'], limit=1).web_read({'display_name': {}})
                checked += 1
        assert checked == 13
        application = scoped['step.agriculture.application'].search([], limit=1)
        if application:
            application.web_read({'name': {}, 'company_id': {}})
            form = Form(application, view=scoped.ref('step_agriculture_records.view_application_form').id)
            assert form.name == application.name
        results['103'] = {'native_form': True, 'cost_center_actions': checked,
                          'existing_profile': user.id, 'existing_application_read': bool(application)}
    assert all(str(ticket) in results for ticket in TICKETS)
    print('TICKET_NATIVE_FLOW_OK ' + json.dumps({'database': scoped.cr.dbname, 'tickets': results}))
finally:
    env.cr.rollback()
