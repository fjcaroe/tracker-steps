from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class StepColacionTariff(models.Model):
    _name = "step.colacion.tariff"
    _description = "Tarifa de colaciones"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "valid_from desc, id desc"

    name = fields.Char(required=True, tracking=True, default=lambda self: _("Nueva tarifa"))
    supplier_id = fields.Many2one(
        "res.partner",
        string="Proveedor",
        required=True,
        tracking=True,
        domain="[('is_meal_supplier', '=', True)]",
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        "res.currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )
    valid_from = fields.Date(string="Vigente desde", required=True, default=fields.Date.context_today, tracking=True)
    valid_to = fields.Date(string="Vigente hasta", tracking=True)
    line_ids = fields.One2many("step.colacion.tariff.line", "tariff_id", string="Productos", copy=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("active", "Vigente"), ("closed", "Cerrada")],
        default="draft",
        required=True,
        tracking=True,
        index=True,
    )
    active = fields.Boolean(default=True)
    notes = fields.Html(string="Notas")
    legacy_ref = fields.Char(copy=False, index=True)

    _sql_constraints = [
        ("legacy_ref_unique", "unique(legacy_ref)", "La tarifa de origen ya fue migrada."),
    ]

    @api.constrains("valid_from", "valid_to")
    def _check_dates(self):
        for tariff in self:
            if tariff.valid_to and tariff.valid_to < tariff.valid_from:
                raise ValidationError(_("La fecha final no puede ser anterior a la fecha inicial."))

    def _check_overlaps(self):
        for tariff in self:
            if not tariff.line_ids:
                raise UserError(_("Agregue al menos un producto con precio antes de activar la tarifa."))
            product_ids = tariff.line_ids.mapped("product_tmpl_id").ids
            candidates = self.search([
                ("id", "!=", tariff.id),
                ("state", "=", "active"),
                ("active", "=", True),
                ("company_id", "=", tariff.company_id.id),
                ("supplier_id", "=", tariff.supplier_id.id),
                ("line_ids.product_tmpl_id", "in", product_ids),
                "|", ("valid_to", "=", False), ("valid_to", ">=", tariff.valid_from),
            ])
            for other in candidates:
                if tariff.valid_to and other.valid_from > tariff.valid_to:
                    continue
                repeated = tariff.line_ids.mapped("product_tmpl_id") & other.line_ids.mapped("product_tmpl_id")
                if repeated:
                    raise ValidationError(_(
                        "Existe otra tarifa vigente y solapada para %(products)s con este proveedor.",
                        products=", ".join(repeated.mapped("display_name")),
                    ))

    def action_activate(self):
        self._check_overlaps()
        self.write({"state": "active", "active": True})

    def action_close(self):
        self.write({"state": "closed"})

    def action_draft(self):
        self.write({"state": "draft"})

    @api.model
    def find_rate(self, product_tmpl, supplier, company, on_date):
        on_date = fields.Date.to_date(on_date)
        tariff = self.search([
            ("supplier_id", "=", supplier.id),
            ("company_id", "=", company.id),
            ("state", "=", "active"),
            ("active", "=", True),
            ("valid_from", "<=", on_date),
            "|", ("valid_to", "=", False), ("valid_to", ">=", on_date),
            ("line_ids.product_tmpl_id", "=", product_tmpl.id),
        ], order="valid_from desc, id desc", limit=1)
        return tariff.line_ids.filtered(
            lambda line: line.product_tmpl_id == product_tmpl
        )[:1]


class StepColacionTariffLine(models.Model):
    _name = "step.colacion.tariff.line"
    _description = "Precio de producto de colación"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    tariff_id = fields.Many2one("step.colacion.tariff", required=True, ondelete="cascade", index=True)
    product_tmpl_id = fields.Many2one(
        "product.template",
        string="Producto",
        required=True,
        domain="[('is_meal', '=', True)]",
    )
    price = fields.Monetary(string="Precio unitario", required=True, currency_field="currency_id")
    currency_id = fields.Many2one(related="tariff_id.currency_id", store=True, readonly=True)
    company_id = fields.Many2one(related="tariff_id.company_id", store=True, readonly=True)

    _sql_constraints = [
        ("tariff_product_unique", "unique(tariff_id, product_tmpl_id)", "El producto solo puede aparecer una vez por tarifa."),
        ("price_nonnegative", "check(price >= 0)", "El precio de la colación no puede ser negativo."),
    ]
