"""Five-week export forecast combining programme, shipments and producers."""

from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ExportForecast(models.Model):
    _name = "step.export.forecast"
    _description = "Forecast de exportación"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "cutoff_week desc, id desc"

    name = fields.Char(required=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    season_id = fields.Many2one("step.temporada", required=True)
    species_ids = fields.Many2many("step.especie", string="Especies")
    sales_program_ids = fields.Many2many("step.export.sales.program", string="Programas")
    cutoff_week = fields.Date(string="Semana de corte", required=True)
    usd_currency_id = fields.Many2one("res.currency", default=lambda self: self.env.ref("base.USD"))
    line_ids = fields.One2many("step.export.forecast.line", "forecast_id", string="Semanas")
    actual_shipped_kg = fields.Float(readonly=True)
    actual_sales_usd = fields.Monetary(currency_field="usd_currency_id", readonly=True)
    actual_price_adjustment_usd = fields.Monetary(currency_field="usd_currency_id", readonly=True)
    actual_received_kg = fields.Float(readonly=True)
    actual_purchase_usd = fields.Monetary(currency_field="usd_currency_id", readonly=True)
    actual_operating_cost_usd = fields.Monetary(currency_field="usd_currency_id", readonly=True)
    remaining_kg = fields.Float(compute="_compute_totals")
    projected_sales_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_totals")
    projected_margin_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_totals")

    @api.depends("actual_sales_usd", "actual_price_adjustment_usd", "actual_operating_cost_usd",
                 "actual_purchase_usd",
                 "line_ids.program_kg", "line_ids.program_sales_usd", "line_ids.estimated_purchase_usd",
                 "line_ids.standard_operating_cost_usd")
    def _compute_totals(self):
        for record in self:
            record.remaining_kg = sum(record.line_ids.mapped("program_kg"))
            future_sales = sum(record.line_ids.mapped("program_sales_usd"))
            future_purchases = sum(record.line_ids.mapped("estimated_purchase_usd"))
            future_cost = sum(record.line_ids.mapped("standard_operating_cost_usd"))
            record.projected_sales_usd = (record.actual_sales_usd +
                                          record.actual_price_adjustment_usd + future_sales)
            record.projected_margin_usd = (record.projected_sales_usd -
                                           record.actual_operating_cost_usd -
                                           record.actual_purchase_usd -
                                           future_purchases - future_cost)

    def action_generate(self):
        for forecast in self:
            cutoff = forecast.cutoff_week
            if cutoff.weekday() != 0:
                raise UserError(_("La semana de corte debe comenzar un lunes."))
            programs = forecast.sales_program_ids or self.env["step.export.sales.program"].search([
                ("company_id", "=", forecast.company_id.id),
                ("season_id", "=", forecast.season_id.id), ("state", "=", "current")])
            programs = programs.filtered(lambda p: p.state == "current" and p.season_id == forecast.season_id
                                         and (not forecast.species_ids or p.species_id in forecast.species_ids))
            if not programs:
                raise UserError(_("No hay programas vigentes para el filtro del forecast."))
            shipments = self.env["step.export.export"].search([
                ("sales_program_id", "in", programs.ids),
                ("date", "<", cutoff + timedelta(days=7)),
                ("state", "in", ["dispatched", "shipped", "invoiced", "settled"]),
            ])
            invoices = shipments.mapped("invoice_ids").filtered(
                lambda move: move.state == "posted" and move.move_type == "out_invoice"
                and not move.step_export_settlement_id)
            actual_sales = sum(move.currency_id._convert(
                move.amount_untaxed, forecast.usd_currency_id, forecast.company_id,
                move.invoice_date or cutoff) for move in invoices)
            actual_ivv = sum(sum(ship.settlement_id.line_ids.filtered(
                lambda line: line.shipment_id == ship).mapped("difference_usd")) for ship in shipments)
            tags = self.env["stock.quant.package"].search([
                ("is_fruit_tag", "=", True), ("step_export_season_id", "=", forecast.season_id.id),
                ("create_date", "<", cutoff + timedelta(days=7)),
            ])
            if forecast.species_ids:
                tags = tags.filtered(lambda tag: tag.especie_id in forecast.species_ids)
            producer_settlements = shipments.mapped("settlement_id.producer_settlement_ids")
            settled_tag_ids = set(producer_settlements.mapped("line_ids.tag_id").ids)
            actual_purchase = sum(producer_settlements.mapped("net_usd"))
            for tag in tags.filtered(lambda item: item.id not in settled_tag_ids):
                rate = self.env["step.export.grower.rate"].search([
                    ("producer_id", "=", tag.owner_id.id),
                    ("season_id", "=", forecast.season_id.id),
                    ("species_id", "=", tag.especie_id.id),
                ], order="date desc, id desc", limit=1)
                if rate.rate_type == "usd_kg":
                    actual_purchase += tag.kilos_total * rate.rate_value
            expense_lines = self.env["account.move.line"].search([
                ("step_export_shipment_id", "in", shipments.ids),
                ("parent_state", "=", "posted"),
                ("account_id.account_type", "in", ["expense", "expense_direct_cost"]),
            ])
            actual_cost = sum(forecast.company_id.currency_id._convert(
                line.balance, forecast.usd_currency_id, forecast.company_id,
                line.date or cutoff) for line in expense_lines)
            estimates = self.env["step.export.estimate"].search([
                ("company_id", "=", forecast.company_id.id),
                ("season_id", "=", forecast.season_id.id), ("state", "=", "current")])
            if forecast.species_ids:
                estimates = estimates.filtered(lambda estimate: any(
                    line.species_id in forecast.species_ids for line in estimate.estimate_line_ids))
            packaging = self.env["step.export.packaging.program"].search([
                ("sales_program_id", "in", programs.ids), ("state", "=", "valued")])
            week_vals = []
            weeks = [cutoff + timedelta(days=7 * step) for step in range(1, 6)]
            for week in weeks + [False]:
                p_lines = programs.mapped("line_ids").filtered(
                    lambda line: (line.week_start == week if week else line.week_start > weeks[-1]))
                e_lines = estimates.mapped("estimate_line_ids").mapped("week_line_ids").filtered(
                    lambda line: (line.week_start == week if week else line.week_start > weeks[-1]))
                export_kg = sum(p_lines.mapped("kg_qty"))
                purchase_kg = sum(e_lines.mapped("export_kg"))
                purchase_usd = 0
                for estimate in estimates:
                    for estimate_line in estimate.estimate_line_ids:
                        weekly_kg = sum(estimate_line.week_line_ids.filtered(
                            lambda line: (line.week_start == week if week else line.week_start > weeks[-1])
                        ).mapped("export_kg"))
                        if not weekly_kg:
                            continue
                        rate = self.env["step.export.grower.rate"].search([
                            ("producer_id", "=", estimate.producer_id.id),
                            ("season_id", "=", forecast.season_id.id),
                            ("species_id", "=", estimate_line.species_id.id),
                        ], order="date desc, id desc", limit=1)
                        if rate.rate_type == "usd_kg":
                            purchase_usd += weekly_kg * rate.rate_value
                        elif rate.rate_type == "fob_percent" and export_kg:
                            purchase_usd += weekly_kg * (
                                sum(p_lines.mapped("amount_usd")) / export_kg) * rate.rate_value / 100
                cost = 0
                for program in packaging:
                    program_kg = sum(p_lines.filtered(
                        lambda line: line.program_id == program.sales_program_id).mapped("kg_qty"))
                    if program.kg_qty:
                        cost += program.standard_cost_usd * program_kg / program.kg_qty
                week_vals.append((0, 0, {
                    "week_start": week, "other_weeks": not bool(week),
                    "program_kg": export_kg,
                    "program_sales_usd": sum(p_lines.mapped("amount_usd")),
                    "estimate_purchase_kg": purchase_kg,
                    "estimated_purchase_usd": purchase_usd,
                    "standard_operating_cost_usd": cost,
                }))
            forecast.write({
                "actual_shipped_kg": sum(shipments.mapped("kg_qty")),
                "actual_sales_usd": actual_sales,
                "actual_price_adjustment_usd": actual_ivv,
                "actual_received_kg": sum(tags.mapped("kilos_total")),
                "actual_purchase_usd": actual_purchase,
                "actual_operating_cost_usd": actual_cost,
                "line_ids": [(5, 0, 0)] + week_vals,
            })
        return True


class ExportForecastLine(models.Model):
    _name = "step.export.forecast.line"
    _description = "Semana de forecast de exportación"
    _order = "other_weeks, week_start"

    forecast_id = fields.Many2one("step.export.forecast", required=True, ondelete="cascade")
    week_start = fields.Date(string="Semana")
    other_weeks = fields.Boolean(string="Otras semanas")
    program_kg = fields.Float(string="Kg por embarcar")
    estimate_purchase_kg = fields.Float(string="Kg por recibir")
    usd_currency_id = fields.Many2one(related="forecast_id.usd_currency_id")
    program_sales_usd = fields.Monetary(string="Ventas por embarcar USD", currency_field="usd_currency_id")
    estimated_purchase_usd = fields.Monetary(string="Compra fruta estimada USD", currency_field="usd_currency_id")
    standard_operating_cost_usd = fields.Monetary(string="Costo operación estándar USD", currency_field="usd_currency_id")


class ForecastFruitTag(models.Model):
    _inherit = "stock.quant.package"

    step_export_season_id = fields.Many2one("step.temporada", string="Temporada de exportación")


class ForecastAccountMoveLine(models.Model):
    _inherit = "account.move.line"

    step_export_shipment_id = fields.Many2one("step.export.export", string="Embarque de costo")
