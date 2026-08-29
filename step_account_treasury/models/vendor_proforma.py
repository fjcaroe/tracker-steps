# -*- coding: utf-8 -*-
"""Proforma de proveedor.

Se auditaron los tres ambientes y no existe ningún modelo de proforma de
proveedor instalado, así que este módulo aporta uno mínimo. Si en el futuro
apareciera un motor de proformas de terceros, este modelo se sustituye por un
adaptador sin tocar el resto de Tesorería: el flujo sólo consume
`_treasury_pending_proformas()`.
"""

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StepVendorProforma(models.Model):
    _name = "step.vendor.proforma"
    _description = "Proforma de proveedor"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Número", required=True, copy=False, readonly=True,
        default=lambda self: _("Nuevo"), index=True,
    )
    partner_id = fields.Many2one(
        "res.partner", string="Proveedor", required=True, tracking=True,
        domain=[("is_company", "in", (True, False))],
    )
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True, index=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", required=True,
        default=lambda self: self.env.company.currency_id,
    )
    date = fields.Date(string="Fecha", default=fields.Date.context_today, required=True)
    date_due = fields.Date(string="Vencimiento", tracking=True)
    reference = fields.Char(string="Referencia del proveedor")
    line_ids = fields.One2many("step.vendor.proforma.line", "proforma_id", string="Líneas")
    amount_untaxed = fields.Monetary(string="Base", compute="_compute_amounts", store=True)
    amount_tax = fields.Monetary(string="Impuestos", compute="_compute_amounts", store=True)
    amount_total = fields.Monetary(string="Total", compute="_compute_amounts", store=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("approved", "Aprobada"),
         ("invoiced", "Facturada"), ("cancelled", "Anulada")],
        string="Estado", default="draft", required=True, tracking=True, index=True, copy=False,
    )
    move_id = fields.Many2one(
        "account.move", string="Factura final", readonly=True, copy=False,
        check_company=True, help="Factura de proveedor que reemplazó a esta proforma.",
    )
    note = fields.Text(string="Notas")

    @api.depends("line_ids.price_subtotal", "line_ids.price_tax")
    def _compute_amounts(self):
        for record in self:
            record.amount_untaxed = sum(record.line_ids.mapped("price_subtotal"))
            record.amount_tax = sum(record.line_ids.mapped("price_tax"))
            record.amount_total = record.amount_untaxed + record.amount_tax

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Nuevo"):
                company_id = vals.get("company_id") or self.env.company.id
                vals["name"] = self.env["ir.sequence"].with_company(company_id).next_by_code(
                    "step.vendor.proforma") or _("Nuevo")
        return super().create(vals_list)

    def action_approve(self):
        for record in self:
            if record.state != "draft":
                raise UserError(_("Sólo se puede aprobar una proforma en borrador."))
            if not record.line_ids:
                raise UserError(_("Agregue al menos una línea antes de aprobar."))
        self.write({"state": "approved"})
        return True

    def action_draft(self):
        self.filtered(lambda r: r.state in ("approved", "cancelled")).write({"state": "draft"})
        return True

    def action_cancel(self):
        self.filtered(lambda r: r.state != "invoiced").write({"state": "cancelled"})
        return True

    def action_mark_invoiced(self):
        """Marca la proforma como facturada. No emite ningún documento real."""
        for record in self:
            if record.state != "approved":
                raise UserError(_("Sólo una proforma aprobada puede marcarse como facturada."))
        self.write({"state": "invoiced"})
        return True

    @api.model
    def _treasury_pending_proformas(self, company, date_from=None):
        """Proformas que deben proyectarse: aprobadas y aún no facturadas."""
        domain = [
            ("company_id", "=", company.id),
            ("state", "=", "approved"),
            ("move_id", "=", False),
        ]
        return self.search(domain)


class StepVendorProformaLine(models.Model):
    _name = "step.vendor.proforma.line"
    _description = "Línea de proforma de proveedor"
    _order = "proforma_id, sequence, id"
    _check_company_auto = True

    proforma_id = fields.Many2one(
        "step.vendor.proforma", string="Proforma", required=True,
        ondelete="cascade", index=True,
    )
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Descripción", required=True)
    product_id = fields.Many2one("product.product", string="Producto")
    quantity = fields.Float(string="Cantidad", default=1.0)
    price_unit = fields.Float(string="Precio unitario")
    tax_ids = fields.Many2many("account.tax", string="Impuestos", check_company=True)
    company_id = fields.Many2one(related="proforma_id.company_id", store=True, index=True)
    currency_id = fields.Many2one(related="proforma_id.currency_id", store=True)
    price_subtotal = fields.Monetary(string="Subtotal", compute="_compute_price", store=True)
    price_tax = fields.Monetary(string="Importe impuestos", compute="_compute_price", store=True)
    price_total = fields.Monetary(string="Total", compute="_compute_price", store=True)

    @api.depends("quantity", "price_unit", "tax_ids", "currency_id")
    def _compute_price(self):
        for line in self:
            base = line.quantity * line.price_unit
            taxes = line.tax_ids.compute_all(
                line.price_unit, currency=line.currency_id, quantity=line.quantity,
                product=line.product_id, partner=line.proforma_id.partner_id,
            ) if line.tax_ids else None
            if taxes:
                line.price_subtotal = taxes["total_excluded"]
                line.price_total = taxes["total_included"]
            else:
                line.price_subtotal = base
                line.price_total = base
            line.price_tax = line.price_total - line.price_subtotal
