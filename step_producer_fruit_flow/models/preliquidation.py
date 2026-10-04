"""Foto de preliquidación: fruta, cuenta corriente y cuotas pendientes."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProducerPreliquidation(models.Model):
    _name = "step.producer.preliquidation"
    _description = "Preliquidación de productor"
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(required=True, default=lambda self: _("Nueva preliquidación"))
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    producer_id = fields.Many2one("res.partner", string="Productor", required=True)
    season_id = fields.Many2one("step.temporada", string="Temporada", required=True)
    species_id = fields.Many2one("step.especie", string="Especie", required=True)
    date = fields.Date(string="Fecha de corte", required=True, default=fields.Date.context_today)
    usd_currency_id = fields.Many2one("res.currency", required=True,
                                      default=lambda self: self.env.ref("base.USD"))
    contract_ids = fields.Many2many("step.producer.purchase.contract",
                                    "step_preliq_contract_rel", "preliq_id", "contract_id",
                                    string="Contratos considerados")
    line_ids = fields.One2many("step.producer.preliquidation.line", "preliquidation_id",
                               string="Proyección por etapa", copy=False)
    state = fields.Selection([("draft", "Borrador"), ("generated", "Calculada")],
                             default="draft", required=True)
    account_balance_usd = fields.Monetary(string="Saldo cuenta corriente USD",
                                          currency_field="usd_currency_id", readonly=True)
    pending_installments_usd = fields.Monetary(string="Cuotas pendientes USD",
                                               currency_field="usd_currency_id", readonly=True)
    estimated_return_usd = fields.Monetary(string="Retorno estimado USD",
                                           currency_field="usd_currency_id", compute="_compute_summary")
    projected_balance_usd = fields.Monetary(string="Saldo proyectado USD",
                                            currency_field="usd_currency_id", compute="_compute_summary")

    @api.depends("line_ids.return_usd", "account_balance_usd", "pending_installments_usd")
    def _compute_summary(self):
        for record in self:
            record.estimated_return_usd = sum(record.line_ids.mapped("return_usd"))
            record.projected_balance_usd = (record.estimated_return_usd -
                                            record.account_balance_usd -
                                            record.pending_installments_usd)

    def _price_and_cost(self, variety, product, when):
        self.ensure_one()
        if not variety:
            raise UserError(_("Indique variedad en la estimación o tarja antes de calcular la preliquidación."))
        price_line = self.env["step.producer.preliq.price"].resolve_price(
            self.company_id, self.season_id, self.species_id, variety, when, product=product)
        kg_uom = self.env.ref("uom.product_uom_kgm")
        if price_line.uom_id.category_id != kg_uom.category_id:
            raise UserError(_("El precio de preliquidación debe usar una unidad de peso."))
        kg_per_price_unit = price_line.uom_id._compute_quantity(1.0, kg_uom)
        if kg_per_price_unit <= 0:
            raise UserError(_("La unidad del precio no tiene conversión válida a kg."))
        price_usd = price_line.currency_id._convert(
            price_line.price, self.usd_currency_id, self.company_id, when)
        price_per_kg = price_usd / kg_per_price_unit
        cost_per_kg = self.env["step.export.grower.rate"].resolve_preliq_cost(
            self.company_id, self.season_id, self.species_id, self.producer_id,
            variety, product, price_per_kg)
        return price_per_kg, cost_per_kg

    def _line_values(self, phase, variety, product, source_kg, export_percent,
                     boxes=0, package=False, actual_fob=False, actual_return=False):
        self.ensure_one()
        export_kg = source_kg * export_percent
        if export_kg <= 0:
            return False
        if actual_fob is False:
            price, cost = self._price_and_cost(variety, product, self.date)
            fob = export_kg * price
            expense = export_kg * cost
        else:
            fob = actual_fob
            expense = fob - actual_return
            price = fob / export_kg
            cost = expense / export_kg
        return {
            "preliquidation_id": self.id, "phase": phase,
            "variety_id": variety.id, "product_id": product.id,
            "package_id": package.id if package else False,
            "source_kg": source_kg, "export_percent": export_percent,
            "export_kg": export_kg, "box_qty": boxes,
            "price_usd_per_kg": price, "cost_usd_per_kg": cost,
            "fob_usd": fob, "cost_usd": expense, "return_usd": fob - expense,
        }

    def _received_percent(self, tag, estimates):
        self.ensure_one()
        matches = estimates.mapped("estimate_line_ids").filtered(
            lambda line: line.delivery_kind == "process" and
            line.variety_id == tag.variedad_id)
        rates = {round(line.export_percentage, 6) for line in matches}
        if len(rates) != 1:
            raise UserError(_("Defina un único porcentaje de exportación para la variedad %s.") %
                            tag.variedad_id.display_name)
        return rates.pop()

    def _snapshot_account_balance(self):
        self.ensure_one()
        lines = self.env["account.move.line"].search([
            ("partner_id", "=", self.producer_id.id),
            ("company_id", "=", self.company_id.id),
            ("parent_state", "=", "posted"), ("date", "<=", self.date),
        ])
        return sum(self.company_id.currency_id._convert(
            line.balance, self.usd_currency_id, self.company_id, line.date)
            for line in lines)

    def _snapshot_pending_installments(self):
        self.ensure_one()
        total = 0.0
        for contract in self.contract_ids:
            if contract.company_id != self.company_id or contract.partner_id != self.producer_id:
                raise ValidationError(_("Los contratos deben ser de la misma empresa y productor."))
            if contract.state == "draft" or contract.is_superseded:
                raise ValidationError(_("Use contratos confirmados y vigentes."))
            for installment in contract.installment_ids.filtered(
                    lambda line: line.active and line.state != "accounted"):
                total += contract.currency_id._convert(
                    installment.amount, self.usd_currency_id, self.company_id, self.date)
        return total

    def action_generate(self):
        for record in self:
            record.line_ids.sudo().unlink()
            estimates = self.env["step.export.estimate"].search([
                ("company_id", "=", record.company_id.id),
                ("producer_id", "=", record.producer_id.id),
                ("season_id", "=", record.season_id.id),
                ("state", "=", "current"),
            ])
            values = []
            for line in estimates.mapped("estimate_line_ids").filtered(
                    lambda item: item.species_id == record.species_id and
                    not item.step_delivery_closed and item.step_pending_kg > 0):
                percent = line.export_percentage if line.delivery_kind == "process" else 1.0
                vals = record._line_values("pending", line.variety_id, line.product_id,
                                           line.step_pending_kg, percent)
                if vals:
                    values.append(vals)
            tags = self.env["stock.quant.package"].search([
                ("is_fruit_tag", "=", True),
                ("step_export_season_id", "=", record.season_id.id),
                ("especie_id", "=", record.species_id.id),
                ("step_tag_kind", "in", ["C", "E"]),
                ("step_tag_state", "in", ["validated", "dispatched", "liquidated"]),
                ("step_tag_line_ids.producer_id", "=", record.producer_id.id),
            ])
            for tag in tags:
                if tag.step_tag_state == "validated" and not any(
                        quant.quantity > 0 for quant in tag.quant_ids):
                    continue
                for detail in tag.step_tag_line_ids.filtered(
                        lambda item: item.producer_id == record.producer_id):
                    if tag.step_tag_kind == "C":
                        phase = "packing"
                        percent = record._received_percent(tag, estimates)
                    else:
                        phase = {"validated": "export_ready", "dispatched": "exported",
                                 "liquidated": "liquidated"}[tag.step_tag_state]
                        percent = 1.0
                    actual_fob = False
                    actual_return = False
                    if phase == "liquidated":
                        settled = self.env["step.export.producer.settlement.line"].search([
                            ("tag_id", "=", tag.id),
                            ("settlement_id.producer_id", "=", record.producer_id.id),
                            ("settlement_id.company_id", "=", record.company_id.id),
                            ("settlement_id.receiver_settlement_id.season_id", "=", record.season_id.id),
                            ("settlement_id.receiver_settlement_id.species_id", "=", record.species_id.id),
                        ], limit=1)
                        if not settled:
                            raise UserError(_("La tarja %s figura liquidada sin reparto FOB de productor.") %
                                            tag.name)
                        if not settled.settlement_id.rate_id:
                            raise UserError(_("Configure la tarifa de la liquidación del productor para la tarja %s.") %
                                            tag.name)
                        actual_fob = settled.allocated_fob_usd
                        discount_share = (settled.settlement_id.discount_usd * settled.kg_qty /
                                          settled.settlement_id.total_kg)
                        actual_return = settled.amount_usd - discount_share
                    vals = record._line_values(phase, tag.variedad_id, detail.product_id,
                                               detail.kilos, percent, detail.boxes,
                                               tag, actual_fob, actual_return)
                    if vals:
                        values.append(vals)
            self.env["step.producer.preliquidation.line"].sudo().create(values)
            record.write({
                "account_balance_usd": record._snapshot_account_balance(),
                "pending_installments_usd": record._snapshot_pending_installments(),
                "state": "generated",
            })
        return True


class ProducerPreliquidationLine(models.Model):
    _name = "step.producer.preliquidation.line"
    _description = "Etapa de fruta en preliquidación"
    _order = "phase, id"

    preliquidation_id = fields.Many2one("step.producer.preliquidation", required=True,
                                        ondelete="cascade", index=True)
    company_id = fields.Many2one(related="preliquidation_id.company_id", store=True)
    phase = fields.Selection([
        ("pending", "Fruta por entregar"), ("packing", "Fruta por embalar"),
        ("export_ready", "Fruta por exportar"), ("exported", "Fruta exportada"),
        ("liquidated", "Fruta liquidada"),
    ], required=True)
    variety_id = fields.Many2one("step.variedad", string="Variedad", required=True)
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    package_id = fields.Many2one("stock.quant.package", string="Tarja")
    source_kg = fields.Float(string="Kilos de origen", digits="Stock Weight")
    export_percent = fields.Float(string="Factor exportación", digits=(8, 4))
    export_kg = fields.Float(string="Kilos exportables", digits="Stock Weight")
    box_qty = fields.Float(string="Cajas", digits="Product Unit of Measure")
    price_usd_per_kg = fields.Float(string="FOB USD/kg", digits=(16, 4))
    cost_usd_per_kg = fields.Float(string="Gasto USD/kg", digits=(16, 4))
    usd_currency_id = fields.Many2one(related="preliquidation_id.usd_currency_id")
    fob_usd = fields.Monetary(string="FOB USD", currency_field="usd_currency_id")
    cost_usd = fields.Monetary(string="Gasto USD", currency_field="usd_currency_id")
    return_usd = fields.Monetary(string="Retorno USD", currency_field="usd_currency_id")
