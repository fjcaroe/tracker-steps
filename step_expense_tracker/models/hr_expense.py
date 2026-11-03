from datetime import timedelta, timezone
from math import isfinite
from uuid import UUID

from dateutil.parser import isoparse

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError


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

    @api.model
    def action_prepare_tracker_trip(self, draft):
        self.check_access('create')
        user = self.env.user
        company = self.env.company
        if not user.employee_ids.filtered(lambda employee: employee.company_id == company):
            raise AccessError(_('Tu cuenta necesita un empleado asociado en esta compañía para rendir gastos.'))
        if 'step.tracker.asset.link' not in self.env or not hasattr(user, '_tracker_portal_access'):
            raise AccessError(_('La conexión de Tracker con Rendiciones no está disponible en esta compañía.'))
        try:
            asset = str(UUID(draft['asset']))
            start = isoparse(draft['start'])
            end = isoparse(draft['end'])
            if start.tzinfo is None or end.tzinfo is None:
                raise ValueError('Missing timezone')
            start, end = (stamp.astimezone(timezone.utc) for stamp in (start, end))
            km = float(draft['km'])
            origin, destination = (str(draft[key]).strip() for key in ('origin', 'destination'))
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError):
            raise ValidationError(_('Selecciona un tramo válido en Tracker.'))
        if (not timedelta(0) < end - start <= timedelta(days=31)
                or not isfinite(km) or not 0.01 <= km <= 15000
                or not all(0 < len(label) <= 160 for label in (origin, destination))):
            raise ValidationError(_('El tramo seleccionado no tiene datos válidos para rendir.'))
        user._tracker_portal_access(company)
        user._tracker_check_asset(company, asset)
        link = self.env['step.tracker.asset.link'].search([
            ('company_id', '=', company.id), ('asset_id', '=', asset), ('active', '=', True),
        ], limit=1)
        if not link:
            raise ValidationError(_('El GPS seleccionado necesita un vínculo activo con Flota.'))
        vehicle = link.vehicle_id
        vehicle.check_access('read')
        if not any((vehicle.step_fuel_mixed_km_l, vehicle.step_fuel_city_km_l, vehicle.step_fuel_highway_km_l)):
            raise ValidationError(_('Configura primero el rendimiento de este vehículo en Flota.'))
        local_start = fields.Datetime.context_timestamp(self, start.replace(tzinfo=None))
        local_end = fields.Datetime.context_timestamp(self, end.replace(tzinfo=None))
        cycle = next(cycle for cycle in ('mixed', 'highway', 'city') if vehicle['step_fuel_' + cycle + '_km_l'])
        defaults = {
            'allowed_company_ids': [company.id],
            'default_company_id': company.id,
            'default_step_vehicle_id': vehicle.id,
            'default_step_trip_kind': 'special_fuel',
            'default_step_trip_origin': origin,
            'default_step_trip_destination': destination,
            'default_step_trip_km': round(km, 2),
            'default_step_trip_cycle': cycle,
            'default_date': fields.Date.to_string(local_start.date()),
            'default_name': _('Viaje especial GPS · %(start)s a %(end)s',
                              start=local_start.strftime('%d/%m/%Y %H:%M'),
                              end=local_end.strftime('%d/%m/%Y %H:%M')),
        }
        return {
            'type': 'ir.actions.act_window', 'name': _('Rendir viaje especial'),
            'res_model': 'hr.expense', 'views': [(False, 'form')], 'target': 'current',
            'context': defaults,
        }

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
