import math
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class Production(models.Model):
    _inherit = 'step.packing.production'

    step_packing_overweight_kg = fields.Float(string='Sobrepeso', digits='Stock Weight', copy=False,
        help='Total adicional en kilogramos, ya calculado para todas las cajas. Admite valor positivo o negativo. No cambia el peso estándar del embalaje.')
    step_packing_input_percent = fields.Float(compute='_compute_balance_percent', string='% a proceso')
    step_packing_export_percent = fields.Float(compute='_compute_balance_percent', string='% exportación')
    step_packing_overweight_percent = fields.Float(compute='_compute_balance_percent', string='% sobrepeso')
    step_packing_commercial_percent = fields.Float(compute='_compute_balance_percent', string='% comercial')
    step_packing_precaliber_percent = fields.Float(compute='_compute_balance_percent', string='% precalibre')
    step_packing_waste_percent = fields.Float(compute='_compute_balance_percent', string='% desecho')
    step_packing_loss_percent = fields.Float(compute='_compute_balance_percent', string='% merma')

    @api.depends('step_packing_input_tag_ids.step_tag_line_ids.kilos',
                 'step_packing_output_tag_ids.step_tag_line_ids.kilos',
                 'step_packing_output_tag_ids.step_packing_result', 'step_packing_overweight_kg')
    def _compute_packing_balance(self):
        super()._compute_packing_balance()
        for production in self:
            production.step_packing_loss_kg -= production.step_packing_overweight_kg

    @api.depends('step_packing_input_kg', 'step_packing_export_kg', 'step_packing_overweight_kg',
                 'step_packing_commercial_kg', 'step_packing_precaliber_kg', 'step_packing_waste_kg', 'step_packing_loss_kg')
    def _compute_balance_percent(self):
        for production in self:
            for concept in ('input', 'export', 'overweight', 'commercial', 'precaliber', 'waste', 'loss'):
                production['step_packing_%s_percent' % concept] = (
                    production['step_packing_%s_kg' % concept] / production.step_packing_input_kg * 100
                    if production.step_packing_input_kg else 0)

    @api.constrains('step_packing_overweight_kg')
    def _check_overweight(self):
        if any(not math.isfinite(production.step_packing_overweight_kg) for production in self):
            raise ValidationError(_('El sobrepeso debe ser una cantidad finita en kilogramos.'))

    def write(self, vals):
        if 'step_packing_overweight_kg' in vals and any(production.state != 'created' for production in self):
            raise UserError(_('Reabra la cuadratura antes de modificar el sobrepeso.'))
        return super().write(vals)
