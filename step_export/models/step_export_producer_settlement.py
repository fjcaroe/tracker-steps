"""Producer settlement generated from receiver liquidation and fruit-tag ownership."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_is_zero


class GrowerRate(models.Model):
    _inherit = "step.export.grower.rate"

    producer_id = fields.Many2one("res.partner", string="Productor")
    rate_type = fields.Selection([
        ("usd_kg", "USD por kg"), ("fob_percent", "% del FOB"),
    ], default="usd_kg", required=True)
    rate_value = fields.Float(string="Valor de tarifa", digits=(16, 4))
    expense_account_id = fields.Many2one("account.account", string="Cuenta compra de fruta")
    purchase_tax_ids = fields.Many2many("account.tax", string="Impuestos compra de fruta",
                                        domain="[('type_tax_use','=','purchase')]")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            company = self.env["res.company"].browse(vals.get("company_id")) if vals.get("company_id") else self.env.company
            if not vals.get("expense_account_id") and company.step_export_purchase_account_id:
                vals["expense_account_id"] = company.step_export_purchase_account_id.id
            if "purchase_tax_ids" not in vals and company.step_export_purchase_tax_id:
                vals["purchase_tax_ids"] = [(6, 0, company.step_export_purchase_tax_id.ids)]
        return super().create(vals_list)

    def write(self, vals):
        if {"rate_type", "rate_value", "expense_account_id", "purchase_tax_ids"}.intersection(vals):
            if self.env["step.export.producer.settlement"].search_count([
                ("rate_id", "in", self.ids), ("state", "in", ["validated", "accounted"])]):
                raise UserError(_("La tarifa ya se usó en una liquidación validada."))
        return super().write(vals)


class ProducerSettlement(models.Model):
    _name = "step.export.producer.settlement"
    _description = "Liquidación de productor"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default="Nuevo", readonly=True, copy=False)
    state = fields.Selection([
        ("draft", "Creada"), ("validated", "Validada"),
        ("accounted", "Contabilizada"),
    ], default="draft", required=True, tracking=True, copy=False)
    receiver_settlement_id = fields.Many2one("step.export.receiver.settlement", required=True, ondelete="restrict")
    company_id = fields.Many2one(related="receiver_settlement_id.company_id", store=True)
    producer_id = fields.Many2one("res.partner", string="Productor", required=True)
    rate_id = fields.Many2one("step.export.grower.rate", string="Tarifa productor")
    usd_currency_id = fields.Many2one("res.currency", default=lambda self: self.env.ref("base.USD"))
    bill_currency_id = fields.Many2one("res.currency", string="Moneda factura productor",
                                       default=lambda self: self.env.company.currency_id)
    purchase_journal_id = fields.Many2one("account.journal", string="Diario de compras",
                                          domain="[('type','=','purchase')]")
    supplier_document_code = fields.Char(string="Código DTE proveedor", default="33")
    supplier_invoice_folio = fields.Char(string="Folio factura productor")
    initial_bill_ids = fields.Many2many("account.move", string="Facturas previas del productor",
                                        domain="[('move_type','in',['in_invoice','in_refund']),('state','=','posted')]")
    initial_bills_reviewed = fields.Boolean(string="Facturas previas revisadas")
    initial_billed_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_initial_billed")
    adjustment_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_initial_billed")
    line_ids = fields.One2many("step.export.producer.settlement.line", "settlement_id", string="Tarjas")
    discount_line_ids = fields.One2many("step.export.producer.settlement.discount", "settlement_id",
                                        string="Descuentos")
    bill_id = fields.Many2one("account.move", string="Factura productor", readonly=True, copy=False)
    total_kg = fields.Float(compute="_compute_totals", store=True)
    gross_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_totals", store=True)
    discount_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_totals", store=True)
    net_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_totals", store=True)

    _sql_constraints = [
        ("producer_receiver_unique", "unique(receiver_settlement_id, producer_id)",
         "El productor ya tiene una liquidación para este recibidor."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.export.producer.settlement") or "Nuevo"
            if not vals.get("rate_id") and vals.get("producer_id") and vals.get("receiver_settlement_id"):
                receiver = self.env["step.export.receiver.settlement"].browse(vals["receiver_settlement_id"])
                rate = self.env["step.export.grower.rate"].search([
                    ("producer_id", "=", vals["producer_id"]),
                    ("season_id", "=", receiver.season_id.id),
                    ("species_id", "=", receiver.species_id.id),
                ], order="date desc, id desc", limit=1)
                if rate:
                    vals["rate_id"] = rate.id
            if not vals.get("purchase_journal_id") and vals.get("receiver_settlement_id"):
                receiver = self.env["step.export.receiver.settlement"].browse(vals["receiver_settlement_id"])
                if receiver.company_id.step_export_purchase_journal_id:
                    vals["purchase_journal_id"] = receiver.company_id.step_export_purchase_journal_id.id
        return super().create(vals_list)

    @api.depends("line_ids.kg_qty", "line_ids.amount_usd", "discount_line_ids.amount_usd")
    def _compute_totals(self):
        for record in self:
            record.total_kg = sum(record.line_ids.mapped("kg_qty"))
            record.gross_usd = sum(record.line_ids.mapped("amount_usd"))
            record.discount_usd = sum(record.discount_line_ids.mapped("amount_usd"))
            record.net_usd = record.gross_usd - record.discount_usd

    @api.depends("initial_bill_ids.amount_untaxed", "initial_bill_ids.currency_id",
                 "initial_bill_ids.move_type", "net_usd")
    def _compute_initial_billed(self):
        for record in self:
            amount = 0
            for bill in record.initial_bill_ids:
                value = bill.currency_id._convert(
                    bill.amount_untaxed, record.usd_currency_id,
                    record.company_id, bill.invoice_date or record.receiver_settlement_id.date)
                amount += value if bill.move_type == "in_invoice" else -value
            record.initial_billed_usd = amount
            record.adjustment_usd = record.net_usd - amount

    def action_validate(self):
        for record in self:
            if record.state != "draft" or not record.line_ids:
                raise UserError(_("La liquidación de productor debe tener tarjas."))
            if record.receiver_settlement_id.state not in ("validated", "accounted"):
                raise UserError(_("Primero valide la liquidación del recibidor."))
            if not record.rate_id or record.rate_id.rate_value <= 0 or not record.rate_id.expense_account_id:
                raise ValidationError(_("Configure una tarifa positiva y su cuenta de compra de fruta."))
            if record.net_usd < 0:
                raise ValidationError(_("Los descuentos no pueden superar la liquidación bruta."))
            if any(line.tag_id.owner_id != record.producer_id for line in record.line_ids):
                raise ValidationError(_("Todas las tarjas deben pertenecer al productor."))
            if any(bill.state != "posted" or bill.partner_id != record.producer_id or
                   bill.company_id != record.company_id for bill in record.initial_bill_ids):
                raise ValidationError(_("Las facturas previas deben estar publicadas y pertenecer al productor y empresa."))
            record.state = "validated"
        return True

    def action_account(self):
        for record in self:
            if record.state != "validated":
                raise UserError(_("Valide la liquidación del productor antes de contabilizar."))
            if not record.initial_bills_reviewed:
                raise UserError(_("Revise y vincule las facturas previas del productor antes de contabilizar."))
            if float_is_zero(record.adjustment_usd, precision_rounding=record.usd_currency_id.rounding):
                record.state = "accounted"
                continue
            if not record.supplier_invoice_folio:
                raise UserError(_("Registre el folio del documento tributario del productor."))
            expected_code = "33" if not record.initial_bill_ids else (
                "56" if record.adjustment_usd > 0 else "61")
            if record.supplier_document_code != expected_code:
                raise UserError(_("El código DTE esperado para este ajuste es %s.") % expected_code)
            if record.company_id.account_fiscal_country_id.code == "CL" and not record.rate_id.purchase_tax_ids:
                raise UserError(_("Configure los impuestos de compra de fruta en la tarifa del productor."))
            if not record.bill_id:
                purchase_journal = record.purchase_journal_id or self.env["account.journal"].search([
                    ("company_id", "=", record.company_id.id), ("type", "=", "purchase")], limit=1)
                if not purchase_journal:
                    raise UserError(_("Configure un diario de compras para contabilizar al productor."))
                lines = [(0, 0, {
                    "name": _("Fruta exportación %s / tarja %s") % (record.name, line.tag_id.name),
                    "account_id": record.rate_id.expense_account_id.id,
                    "quantity": 1, "price_unit": record.usd_currency_id._convert(
                        line.amount_usd, record.bill_currency_id, record.company_id,
                        record.receiver_settlement_id.date),
                    "tax_ids": [(6, 0, record.rate_id.purchase_tax_ids.ids)],
                }) for line in record.line_ids]
                for discount in record.discount_line_ids:
                    if not discount.item_id.account_id:
                        raise UserError(_("Configure la cuenta contable del descuento %s.") % discount.item_id.name)
                    lines.append((0, 0, {
                        "name": discount.item_id.name,
                        "account_id": discount.item_id.account_id.id,
                        "quantity": 1, "price_unit": -record.usd_currency_id._convert(
                            discount.amount_usd, record.bill_currency_id, record.company_id,
                            record.receiver_settlement_id.date),
                        "tax_ids": [(6, 0, record.rate_id.purchase_tax_ids.ids)],
                    }))
                if record.initial_bill_ids:
                    lines = [(0, 0, {
                        "name": _("Ajuste final de precio de fruta %s") % record.name,
                        "account_id": record.rate_id.expense_account_id.id,
                        "quantity": 1,
                        "price_unit": record.usd_currency_id._convert(
                            abs(record.adjustment_usd), record.bill_currency_id,
                            record.company_id, record.receiver_settlement_id.date),
                        "tax_ids": [(6, 0, record.rate_id.purchase_tax_ids.ids)],
                    })]
                vals = {
                    "move_type": "in_invoice" if record.adjustment_usd > 0 else "in_refund",
                    "company_id": record.company_id.id,
                    "partner_id": record.producer_id.id, "journal_id": purchase_journal.id,
                    "currency_id": record.bill_currency_id.id,
                    "invoice_date": record.receiver_settlement_id.date,
                    "ref": record.supplier_invoice_folio,
                    "invoice_origin": record.name, "invoice_line_ids": lines,
                }
                bill = self.env["account.move"].create(vals)
                if "l10n_latam_document_type_id" in bill._fields and record.company_id.account_fiscal_country_id.code == "CL":
                    document_type = self.env["l10n_latam.document.type"].search([
                        ("code", "=", record.supplier_document_code)], limit=1)
                    if not document_type:
                        raise UserError(_("El tipo DTE del productor no está configurado."))
                    bill.l10n_latam_document_type_id = document_type
                record.bill_id = bill
            record.bill_id.action_post()
            record.state = "accounted"
        return True

    def write(self, vals):
        frozen = {"producer_id", "rate_id", "line_ids", "discount_line_ids", "receiver_settlement_id"}
        if frozen.intersection(vals) and any(record.state != "draft" for record in self):
            raise UserError(_("La liquidación validada conserva productor, tarifa y tarjas."))
        if vals and any(record.state == "accounted" for record in self):
            raise UserError(_("La liquidación contabilizada no puede modificarse."))
        return super().write(vals)


class ProducerSettlementLine(models.Model):
    _name = "step.export.producer.settlement.line"
    _description = "Tarja en liquidación de productor"

    settlement_id = fields.Many2one("step.export.producer.settlement", required=True, ondelete="cascade")
    tag_id = fields.Many2one("stock.quant.package", string="Tarja", required=True)
    kg_qty = fields.Float(string="Kilos liquidados", required=True,
                          help="Cantidad fijada al generar la liquidación; no cambia con movimientos de inventario.")
    allocated_fob_usd = fields.Float(string="FOB asignado USD", required=True)
    usd_currency_id = fields.Many2one(related="settlement_id.usd_currency_id")
    amount_usd = fields.Monetary(currency_field="usd_currency_id", compute="_compute_amount", store=True)

    @api.depends("kg_qty", "allocated_fob_usd", "settlement_id.rate_id.rate_type",
                 "settlement_id.rate_id.rate_value")
    def _compute_amount(self):
        for record in self:
            rate = record.settlement_id.rate_id
            record.amount_usd = (
                record.kg_qty * rate.rate_value if rate.rate_type == "usd_kg"
                else record.allocated_fob_usd * rate.rate_value / 100)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "kg_qty" not in vals and vals.get("tag_id"):
                vals["kg_qty"] = self.env["stock.quant.package"].browse(vals["tag_id"]).kilos_total
        parents = self.env["step.export.producer.settlement"].browse([
            vals["settlement_id"] for vals in vals_list if vals.get("settlement_id")])
        if any(parent.state != "draft" for parent in parents):
            raise UserError(_("No agregue tarjas a liquidaciones validadas."))
        return super().create(vals_list)

    @api.constrains("kg_qty")
    def _check_kg(self):
        for line in self:
            if line.kg_qty <= 0:
                raise ValidationError(_("Los kilos de la tarja deben ser positivos."))

    def write(self, vals):
        if vals and any(line.settlement_id.state != "draft" for line in self):
            raise UserError(_("No modifique tarjas de liquidaciones validadas."))
        return super().write(vals)

    def unlink(self):
        if any(line.settlement_id.state != "draft" for line in self):
            raise UserError(_("No elimine tarjas de liquidaciones validadas."))
        return super().unlink()


class ProducerSettlementDiscount(models.Model):
    _name = "step.export.producer.settlement.discount"
    _description = "Descuento de liquidación de productor"

    settlement_id = fields.Many2one("step.export.producer.settlement", required=True, ondelete="cascade")
    item_id = fields.Many2one("step.export.grower.discount", string="Concepto", required=True)
    usd_currency_id = fields.Many2one(related="settlement_id.usd_currency_id")
    amount_usd = fields.Monetary(currency_field="usd_currency_id", required=True)

    @api.constrains("amount_usd")
    def _check_amount(self):
        for record in self:
            if record.amount_usd < 0:
                raise ValidationError(_("El descuento debe ser positivo."))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env["step.export.producer.settlement"].browse([
            vals["settlement_id"] for vals in vals_list if vals.get("settlement_id")])
        if any(parent.state != "draft" for parent in parents):
            raise UserError(_("No agregue descuentos a liquidaciones validadas."))
        return super().create(vals_list)

    def write(self, vals):
        if vals and any(line.settlement_id.state != "draft" for line in self):
            raise UserError(_("No modifique descuentos de liquidaciones validadas."))
        return super().write(vals)

    def unlink(self):
        if any(line.settlement_id.state != "draft" for line in self):
            raise UserError(_("No elimine descuentos de liquidaciones validadas."))
        return super().unlink()
