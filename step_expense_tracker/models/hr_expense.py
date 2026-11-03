from math import isfinite

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrExpense(models.Model):
    _inherit = 'hr.expense'

    step_vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Vehículo', index=True, check_company=True,
        help='Atribución explícita de este gasto a un vehículo (combustible, peaje, mantención...). '
             'Sin vehículo el gasto no se imputa a ninguno al calcular costos por vehículo.')

    step_trip_kind = fields.Selection(
        [('regular', 'Normal'), ('special_fuel', 'Viaje especial · combustible')],
        string='Tipo de gasto', default='regular', required=True, index=True)
    step_trip_origin = fields.Char(string='Origen')
    step_trip_destination = fields.Char(string='Destino')
    step_trip_km = fields.Float(string='Distancia del tramo (km)', digits=(12, 2))
    step_trip_cycle = fields.Selection(
        [('city', 'Ciudad'), ('highway', 'Carretera'), ('mixed', 'Mixto')],
        string='Tipo de recorrido', default='mixed')
    step_trip_yield_km_l = fields.Float(
        string='Rendimiento de referencia (km/L)', digits=(8, 2),
        compute='_compute_step_trip_yield', store=True)
    step_trip_liters = fields.Float(
        string='Litros estimados del tramo', digits=(12, 2),
        compute='_compute_step_trip_liters', store=True,
        help='Distancia dividida por el rendimiento de referencia. El importe de la rendición se registra desde el comprobante.')

    @api.depends('step_trip_kind', 'step_trip_cycle', 'step_vehicle_id')
    def _compute_step_trip_yield(self):
        # Keep the rate used for this expense if the fleet master changes later.
        fields_by_cycle = {
            'city': 'step_fuel_city_km_l',
            'highway': 'step_fuel_highway_km_l',
            'mixed': 'step_fuel_mixed_km_l',
        }
        for expense in self:
            field = fields_by_cycle.get(expense.step_trip_cycle)
            expense.step_trip_yield_km_l = (
                expense.step_vehicle_id[field]
                if expense.step_trip_kind == 'special_fuel' and expense.step_vehicle_id and field else 0
            )

    @api.depends('step_trip_km', 'step_trip_yield_km_l')
    def _compute_step_trip_liters(self):
        for expense in self:
            rate = expense.step_trip_yield_km_l
            expense.step_trip_liters = expense.step_trip_km / rate if rate > 0 else 0

    @api.constrains('step_trip_kind', 'step_vehicle_id', 'step_trip_origin',
                    'step_trip_destination', 'step_trip_km', 'step_trip_cycle')
    def _check_step_special_trip(self):
        for expense in self.filtered(lambda row: row.step_trip_kind == 'special_fuel'):
            if not expense.step_vehicle_id or not all(
                (value or '').strip() for value in (expense.step_trip_origin, expense.step_trip_destination)
            ):
                raise ValidationError(_('Indica el vehículo, el origen y el destino del viaje especial.'))
            if not isfinite(expense.step_trip_km) or expense.step_trip_km <= 0:
                raise ValidationError(_('La distancia del tramo debe ser mayor que cero.'))
            if expense.step_trip_yield_km_l <= 0:
                raise ValidationError(_('Configura en Flota el rendimiento para el tipo de recorrido seleccionado.'))

    @api.constrains('step_vehicle_id', 'company_id')
    def _check_step_vehicle_company(self):
        for expense in self:
            vehicle = expense.step_vehicle_id
            if vehicle and vehicle.company_id and vehicle.company_id != expense.company_id:
                raise ValidationError(_('El vehículo %s pertenece a otra empresa que el gasto.') % vehicle.display_name)
