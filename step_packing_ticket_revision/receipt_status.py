from odoo import api, fields, models


class Picking(models.Model):
    _inherit = 'stock.picking'
    step_has_fruit_return = fields.Boolean(string='Recepción con devolución',
        compute='_compute_fruit_return', search='_search_fruit_return')

    @api.depends('return_ids.state', 'step_fruit_reversal_id.state')
    def _compute_fruit_return(self):
        for picking in self:
            picking.step_has_fruit_return = bool((picking.return_ids | picking.step_fruit_reversal_id).filtered(lambda p: p.state == 'done'))

    def _search_fruit_return(self, operator, value):
        if operator not in ('=', '!=') or not isinstance(value, bool):
            raise ValueError('Unsupported return status comparison')
        domain = ['|', ('return_ids.state', '=', 'done'), ('step_fruit_reversal_id.state', '=', 'done')]
        return domain if (operator == '=') == value else ['!'] + domain
