"""Name existing action-view bindings before replacing destructive XML commands."""
from odoo import api, SUPERUSER_ID
from odoo.exceptions import UserError


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    action = env.ref('step_management_costs.action_cost_center')
    data = env['ir.model.data']
    for mode in ('list', 'form'):
        binding = action.view_ids.filtered(lambda row: row.view_mode == mode)
        if len(binding) != 1:
            raise UserError('El centro de costo debe conservar una única vista %s.' % mode)
        name = 'cost_center_%s_binding' % mode
        existing = data.search([('module', '=', 'step_management_costs_agriculture'), ('name', '=', name)])
        if existing:
            if existing.model != binding._name or existing.res_id != binding.id:
                raise UserError('Identificador de vista de centro de costo en conflicto: %s' % name)
        else:
            data.create({'module': 'step_management_costs_agriculture', 'name': name,
                         'model': binding._name, 'res_id': binding.id})
