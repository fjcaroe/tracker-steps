from odoo import api, fields, models


class StepExpenseVehicleLine(models.Model):
    _name = "step.expense.vehicle.line"
    _description = "Uso de vehículo en rendición de gastos"
    _order = "date, id"

    sheet_id = fields.Many2one("hr.expense.sheet", required=True, ondelete="cascade", index=True)
    date = fields.Date(string="Fecha", default=fields.Date.context_today)
    route = fields.Char(string="Recorrido")
    start_reading = fields.Float(string="Odo Inicial", digits=(12, 1))
    end_reading = fields.Float(string="Odo final", digits=(12, 1))
    distance = fields.Float(string="Km", digits=(12, 1), compute="_compute_distance", store=True, readonly=False)
    liters = fields.Float(string="Lts", digits=(12, 2))
    yield_km_l = fields.Float(string="Rend.", digits=(12, 2), compute="_compute_yield", store=True)

    @api.depends("start_reading", "end_reading")
    def _compute_distance(self):
        for line in self:
            if line.end_reading or line.start_reading:
                line.distance = max(line.end_reading - line.start_reading, 0.0)

    @api.depends("distance", "liters")
    def _compute_yield(self):
        for line in self:
            line.yield_km_l = line.distance / line.liters if line.liters else 0.0
