from math import isfinite

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    step_expense_count = fields.Integer(string='Gastos', compute='_compute_step_expense_count')
    step_expense_sheet_count = fields.Integer(string='Rendiciones', compute='_compute_step_expense_count')
    step_fuel_city_km_l = fields.Float(string='Ciudad (km/L)', digits=(8, 2))
    step_fuel_highway_km_l = fields.Float(string='Carretera (km/L)', digits=(8, 2))
    step_fuel_mixed_km_l = fields.Float(string='Mixto (km/L)', digits=(8, 2))
    step_fuel_yield_source = fields.Char(string='Fuente del rendimiento')

    @api.constrains('step_fuel_city_km_l', 'step_fuel_highway_km_l', 'step_fuel_mixed_km_l')
    def _check_step_fuel_yield(self):
        for vehicle in self:
            if any(not isfinite(value) or value < 0 for value in (
                vehicle.step_fuel_city_km_l, vehicle.step_fuel_highway_km_l, vehicle.step_fuel_mixed_km_l,
            )):
                raise ValidationError(_('El rendimiento debe ser un número no negativo.'))

    @api.depends('company_id')
    def _compute_step_expense_count(self):
        # Se calcula con los permisos del usuario: sin acceso a gastos los botones ni se muestran.
        Expense = self.env['hr.expense']
        can_read = Expense.has_access('read')
        for vehicle in self:
            if not can_read:
                vehicle.step_expense_count = vehicle.step_expense_sheet_count = 0
                continue
            expenses = Expense.search(vehicle._step_expense_domain())
            vehicle.step_expense_count = len(expenses)
            vehicle.step_expense_sheet_count = len(expenses.sheet_id)

    def _step_expense_domain(self):
        self.ensure_one()
        domain = [('step_vehicle_id', '=', self.id)]
        if self.company_id:
            domain.append(('company_id', '=', self.company_id.id))
        return domain

    def action_open_step_expenses(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window', 'name': _('Gastos de %s') % self.display_name,
            'res_model': 'hr.expense', 'view_mode': 'list,form',
            'domain': self._step_expense_domain(), 'context': {'default_step_vehicle_id': self.id},
        }

    def action_open_step_expense_sheets(self):
        self.ensure_one()
        sheets = self.env['hr.expense'].search(self._step_expense_domain()).sheet_id
        return {
            'type': 'ir.actions.act_window', 'name': _('Rendiciones de %s') % self.display_name,
            'res_model': 'hr.expense.sheet', 'view_mode': 'list,form', 'domain': [('id', 'in', sheets.ids)],
        }
