"""Compara estimación vigente con kilos efectivamente recibidos en Inventario."""

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class StepExportEstimateLine(models.Model):
    _inherit = "step.export.estimate.line"

    step_delivery_closed = fields.Boolean(string="Entrega cerrada", copy=False)
    step_received_kg = fields.Float(string="Kilos recibidos", compute="_compute_step_delivery_balance",
                                    digits="Stock Weight")
    step_pending_kg = fields.Float(string="Saldo por entregar", compute="_compute_step_delivery_balance",
                                   digits="Stock Weight")
    step_excess_kg = fields.Float(string="Exceso recibido", compute="_compute_step_delivery_balance",
                                  digits="Stock Weight")

    def action_step_close_delivery(self):
        for line in self:
            if line.estimate_id.state != "current":
                raise UserError(_("Solo puede cerrar la entrega de una estimación vigente."))
            line.write({"step_delivery_closed": True})
        return True

    def _step_receipt_domain(self):
        self.ensure_one()
        estimate = self.estimate_id
        domain = [
            ("picking_id.state", "=", "done"),
            ("picking_id.company_id", "=", estimate.company_id.id),
            ("picking_id.fruit_fundo_id", "=", estimate.fundo_id.id),
            ("picking_id.fruit_species_id", "=", self.species_id.id),
            ("picking_id.fruit_season_id", "=", estimate.season_id.id),
            ("picking_id.step_fruit_reception_kind", "=", self.delivery_kind),
            ("product_id", "=", self.product_id.id),
        ]
        if self.variety_id:
            domain.append(("picking_id.fruit_variety_id", "=", self.variety_id.id))
        return domain

    @api.depends("estimate_id.fundo_id", "estimate_id.season_id", "estimate_id.company_id",
                 "delivery_kind", "species_id", "variety_id", "product_id", "process_kg", "export_kg")
    def _compute_step_delivery_balance(self):
        receipts = self.env["step.packing.picking.tag.line"]
        for line in self:
            received = sum(receipts.search(line._step_receipt_domain()).mapped("kilos"))
            expected = line.process_kg if line.delivery_kind == "process" else line.export_kg
            line.step_received_kg = received
            line.step_pending_kg = max(0.0, expected - received)
            line.step_excess_kg = max(0.0, received - expected)


class StepExportEstimateWeek(models.Model):
    _inherit = "step.export.estimate.week"

    step_received_kg = fields.Float(string="Kilos recibidos", compute="_compute_step_week_balance",
                                    digits="Stock Weight")
    step_pending_kg = fields.Float(string="Saldo semana", compute="_compute_step_week_balance",
                                   digits="Stock Weight")

    @api.depends("line_id", "week_start", "export_kg", "line_id.export_percentage")
    def _compute_step_week_balance(self):
        receipts = self.env["step.packing.picking.tag.line"]
        for week in self:
            start = fields.Date.to_date(week.week_start)
            if not start or not week.line_id:
                week.step_received_kg = week.step_pending_kg = 0
                continue
            end = start + timedelta(days=7)
            domain = week.line_id._step_receipt_domain() + [
                ("picking_id.date_done", ">=", start),
                ("picking_id.date_done", "<", end),
            ]
            received = sum(receipts.search(domain).mapped("kilos"))
            expected = (week.export_kg / week.line_id.export_percentage
                        if week.line_id.delivery_kind == "process" and week.line_id.export_percentage
                        else week.export_kg)
            week.step_received_kg = received
            week.step_pending_kg = max(0.0, expected - received)
