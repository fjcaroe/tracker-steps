"""Odoo shell verification against a private clone; all fixtures roll back."""
import json

from odoo import api
from odoo.tests import Form

try:
    if MODE == 'community':
        company = env.company
        user = env.ref('base.user_admin')
        assert not env['ir.module.module'].search_count([('state', '=', 'installed'), ('license', '=', 'OEEL-1')])
        assert not env['ir.module.module'].search_count([('name', '=', 'step_hr'), ('state', '=', 'installed')])
    else:
        company = env['res.company'].search([('vat', '=', '76943293-0')], limit=1)
        assert company, 'Canonical Cerro company missing'
        # Use an existing business profile; never grant groups to make this pass.
        candidates = env['res.users'].search([('active', '=', True), ('share', '=', False),
                                              ('company_ids', 'in', company.ids), ('id', '>', 1)], order='id')
        user = candidates.filtered(lambda u: u.has_group('stock.group_stock_user') and
                                    env['step.temporada'].with_user(u).has_access('read'))[:1]
        assert user, 'No existing authorized business user'
    scoped = api.Environment(env.cr, user.id, dict(env.context, allowed_company_ids=company.ids), su=False)
    assert not scoped.su and company in scoped.user.company_ids
    checks = []
    for model, action_name, view_name in [
        ('step.temporada', 'action_step_temporada', 'view_temporada_form'),
        ('step.fundo', 'action_step_fundo', 'view_step_fundo_form'),
        ('step.especie', 'action_step_especie', 'view_step_especie_form'),
        ('step.grupo.variedad', 'action_step_grupo_variedad', 'view_step_grupo_variedad_form'),
        ('step.variedad', 'action_step_variedad', 'view_step_variedad_form'),
        ('account.analytic.account', 'action_step_centro_costo_analytic', 'step_view_account_analytic_account_form'),
    ]:
        target = scoped[model]
        target.check_access('read')
        action = scoped.ref('step_hr.' + action_name)
        assert action.res_model == model
        view = scoped.ref('step_hr.' + view_name)
        target.get_view(view.id, 'form')
        checks.append({'model': model, 'action': action.id, 'view': view.id,
                       'accessible_records': target.search_count([])})
    scoped['stock.picking'].get_view(scoped.ref('step_packing.view_picking_form_packing_fruit').id, 'form')
    with Form(scoped['step.packing.campo']) as native:
        native.name = 'Private Community packing verification'
    assert native.record.id
    root = scoped.ref('step_agriculture_core.menu_agriculture_core')
    if MODE == 'community':
        assert root.id in scoped['ir.ui.menu']._visible_menu_ids()
    else:
        assert not root.active, 'Existing menu restrictions must not be bypassed'
    print('AGRICULTURE_NATIVE_OK ' + json.dumps({'uid': user.id, 'company_id': company.id,
          'su': scoped.su, 'checks': checks, 'packing_form': True}))
finally:
    env.cr.rollback()
