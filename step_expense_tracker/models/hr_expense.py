from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    step_vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehículo', index=True, check_company=True,
        help='Atribución explícita de este gasto a un vehículo (combustible, peaje, mantención...). '
             'Sin vehículo el gasto no se imputa a ninguno al calcular costos por vehículo.')

    @api.constrains('step_vehicle_id', 'company_id')
    def _check_step_vehicle_company(self):
        for expense in self:
            vehicle = expense.step_vehicle_id
            if vehicle and vehicle.company_id and vehicle.company_id != expense.company_id:
                raise ValidationError(_('El vehículo %s pertenece a otra empresa que el gasto.') % vehicle.display_name)
