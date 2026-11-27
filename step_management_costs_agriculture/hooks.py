from odoo.exceptions import ValidationError


def adopt_cost_center_bindings(env):
    action = env.ref('step_management_costs.action_cost_center')
    bindings = env['ir.actions.act_window.view']
    data = env['ir.model.data']
    for mode in ('list', 'form'):
        expected = env.ref('step_agriculture_core.step_view_account_analytic_account_' + mode)
        matched = bindings.search([('act_window_id', '=', action.id), ('view_mode', '=', mode)])
        alias = 'step_management_costs_agriculture.cost_center_' + mode + '_binding'
        previous = env.ref(alias, raise_if_not_found=False)
        if previous and previous != matched:
            raise ValidationError('Cambió la identidad de la vista del centro de costo: ' + mode)
        if not matched:
            continue
        if len(matched) != 1 or matched.view_id != expected:
            raise ValidationError('La acción de centros de costo tiene otra vista de ' + mode + '.')
        if not previous:
            data._update_xmlids([{'xml_id': alias, 'record': matched, 'noupdate': False}])
