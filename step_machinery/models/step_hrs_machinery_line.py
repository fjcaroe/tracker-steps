# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StepHrsMachineryLine(models.Model):
    _name = "step.hrs.machinery.line"
    _description = "Detalle de horas máquina"
    _rec_name = "machinery_ids"
    _check_company_auto = True

    machinery_ids = fields.Many2one("fleet.vehicle", string="Maquinaria", required=True, ondelete="restrict", index=True)
    implement_id = fields.Many2one("step.machinery.implement", string="Implemento", ondelete="restrict")
    employee_id = fields.Many2one("hr.employee", string="Conductor")
    cost_id = fields.Many2one("account.analytic.account", string="Centro de costos")
    labor_id = fields.Many2one("step.labor", string="Labor")
    actividad_id = fields.Many2one(related="labor_id.actividad_id", string="Actividad", store=True)
    uom_id = fields.Many2one(related="labor_id.uom_id", string="UdM")
    odometer_init = fields.Float(string="Horómetro inicial", copy=False)
    odometer_end = fields.Float(string="Horómetro final", copy=False)
    hrs_maquina = fields.Float(string="Horas máquina")
    lrts_combustible = fields.Float(string="Litros combustible")
    machinery_id = fields.Many2one("step.hrs.machinery", string="Registro", required=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="machinery_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    date = fields.Date(related="machinery_id.date", store=True)
    fundo_id = fields.Many2one(related="machinery_id.fundo_id", store=True)
    temp_id = fields.Many2one(related="machinery_id.temp_id", store=True)
    name_parent = fields.Char(related="machinery_id.name", store=True)
    state = fields.Selection(related="machinery_id.state", store=True)
    progress_cost = fields.Boolean(string="Procesado", default=False, copy=False)

    fuel_unit_cost = fields.Monetary(string="Costo unitario combustible", copy=False)
    fuel_total_cost = fields.Monetary(string="Costo combustible", copy=False)
    oil_unit_cost = fields.Monetary(string="Costo unitario estándar aceite y lubricantes", copy=False)
    oil_total_cost = fields.Monetary(string="Costo total estándar aceite y lubricantes", copy=False)
    spare_unit_cost = fields.Monetary(string="Costo unitario estándar repuestos", copy=False)
    spare_total_cost = fields.Monetary(string="Costo total estándar repuestos", copy=False)
    corrective_unit_cost = fields.Monetary(string="Costo unitario estándar mantención correctiva", copy=False)
    corrective_total_cost = fields.Monetary(string="Costo total estándar mantención correctiva", copy=False)
    labor_unit_cost = fields.Monetary(string="Costo unitario estándar mano de obra", copy=False)
    labor_total_cost = fields.Monetary(string="Costo total estándar mano de obra", copy=False)
    rental_unit_cost = fields.Monetary(string="Costo unitario estándar arriendo", copy=False)
    rental_total_cost = fields.Monetary(string="Costo total estándar arriendo", copy=False)
    preventive_unit_cost = fields.Monetary(string="Costo unitario estándar mantención preventiva", copy=False)
    preventive_total_cost = fields.Monetary(string="Costo total estándar mantención preventiva", copy=False)
    depreciation_unit_cost = fields.Monetary(string="Costo unitario estándar depreciación", copy=False)
    depreciation_total_cost = fields.Monetary(string="Costo total estándar depreciación", copy=False)
    total_machine_cost = fields.Monetary(string="Costo total máquina", copy=False)
    total_hour_cost = fields.Monetary(string="Costo total HrMq", copy=False)

    # Alias conservados para informes e integraciones existentes.
    cost_odometer = fields.Monetary(string="Costo horómetro", related="total_hour_cost", store=True)
    cost_hrs_maquina = fields.Monetary(string="Costo estándar", related="total_machine_cost", store=True)
    cost_lrts_combustible = fields.Monetary(string="Costeo litros combustible", related="fuel_total_cost", store=True)

    @api.constrains("odometer_init", "odometer_end", "hrs_maquina", "lrts_combustible")
    def _check_values(self):
        for line in self:
            if min(line.odometer_init, line.odometer_end, line.hrs_maquina, line.lrts_combustible) < 0:
                raise ValidationError(_("Horas, horómetros y combustible no pueden ser negativos."))
            if line.odometer_end and line.odometer_init and line.odometer_end < line.odometer_init:
                raise ValidationError(_("El horómetro final no puede ser menor al inicial."))

    @api.onchange("machinery_ids")
    def _onchange_machinery(self):
        for line in self:
            if not line.machinery_ids:
                continue
            odometer = self.env["fleet.vehicle.odometer"].search(
                [("vehicle_id", "=", line.machinery_ids.id)], order="date desc, id desc", limit=1
            )
            line.odometer_init = odometer.value if odometer else 0.0

    @api.onchange("odometer_init", "odometer_end")
    def _onchange_odometer(self):
        for line in self:
            if line.odometer_end >= line.odometer_init and line.odometer_end:
                line.hrs_maquina = line.odometer_end - line.odometer_init

    def _hourly_cost_by_code(self):
        self.ensure_one()
        vehicle = self.machinery_ids
        result = {}
        for source in (vehicle.consumption_line, vehicle.radio_line):
            for item in source:
                code = item.service_machinery_id.cod
                if not code:
                    continue
                hourly = item.cost_hr_amount
                if not hourly and vehicle.step_total_hrs_mes:
                    hourly = item.concept_amount / vehicle.step_total_hrs_mes
                result[code] = result.get(code, 0.0) + hourly
        return result

    def _apply_standard_cost(self):
        for line in self:
            if not line.hrs_maquina and line.odometer_end >= line.odometer_init:
                line.hrs_maquina = line.odometer_end - line.odometer_init
            if line.hrs_maquina <= 0:
                raise UserError(_("Indique horas máquina válidas para %s.") % line.machinery_ids.display_name)
            vehicle = line.machinery_ids
            product = vehicle.step_product_id
            fuel_unit = product.standard_price if product else 0.0
            hourly = line._hourly_cost_by_code()
            vals = {"fuel_unit_cost": fuel_unit, "fuel_total_cost": fuel_unit * line.lrts_combustible}
            mapping = {
                "02": ("oil_unit_cost", "oil_total_cost"),
                "03": ("spare_unit_cost", "spare_total_cost"),
                "04": ("corrective_unit_cost", "corrective_total_cost"),
                "05": ("labor_unit_cost", "labor_total_cost"),
                "06": ("rental_unit_cost", "rental_total_cost"),
                "07": ("preventive_unit_cost", "preventive_total_cost"),
                "08": ("depreciation_unit_cost", "depreciation_total_cost"),
            }
            for code, (unit_field, total_field) in mapping.items():
                vals[unit_field] = hourly.get(code, 0.0)
                vals[total_field] = hourly.get(code, 0.0) * line.hrs_maquina
            total_fields = ["fuel_total_cost"] + [item[1] for item in mapping.values()]
            vals["total_machine_cost"] = sum(vals[field] for field in total_fields)
            vals["total_hour_cost"] = vals["total_machine_cost"] / line.hrs_maquina
            vals["progress_cost"] = True
            line.write(vals)

    def _cost_components(self):
        self.ensure_one()
        return {"01": self.fuel_total_cost, "02": self.oil_total_cost,
                "03": self.spare_total_cost, "04": self.corrective_total_cost,
                "05": self.labor_total_cost, "06": self.rental_total_cost,
                "07": self.preventive_total_cost, "08": self.depreciation_total_cost}

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records.filtered(lambda r: r.machinery_ids and r.odometer_end):
            self.env["fleet.vehicle.odometer"].create({
                "date": record.date or fields.Date.context_today(record),
                "vehicle_id": record.machinery_ids.id,
                "driver_id": record.employee_id.id,
                "value": record.odometer_end,
            })
        return records
