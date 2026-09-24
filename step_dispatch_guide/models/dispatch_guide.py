from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class StepDispatchDriver(models.Model):
    _name = "step.dispatch.driver"
    _description = "Chofer de despacho"
    _order = "name"

    name = fields.Char(required=True)
    vat = fields.Char(string="RUT", required=True)
    phone = fields.Char(string="Teléfono")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company,
    )

    _sql_constraints = [
        ("vat_company_unique", "unique(vat, company_id)",
         "Ya existe un chofer con este RUT en la empresa."),
    ]


class StepDispatchGuide(models.Model):
    _name = "step.dispatch.guide"
    _description = "Guía de despacho interna"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _check_company_auto = True

    name = fields.Char(
        string="Referencia", default=lambda self: _("Nueva"), readonly=True,
        copy=False, index=True,
    )
    external_folio = fields.Char(
        string="Folio externo", required=True, copy=False, tracking=True,
        help="Folio asignado por el proveedor DTE externo. Esta guía es de uso interno.",
    )
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    state = fields.Selection(
        [("draft", "Borrador"), ("confirmed", "Confirmada"), ("cancelled", "Anulada")],
        default="draft", required=True, tracking=True, copy=False,
    )
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company, index=True,
    )
    currency_id = fields.Many2one(related="company_id.currency_id", store=True)
    partner_id = fields.Many2one("res.partner", string="Receptor", required=True, tracking=True)
    receiver_activity = fields.Char(string="Giro receptor")
    origin_address = fields.Char(string="Dirección de origen", required=True)
    destination_address = fields.Char(string="Dirección de destino", required=True)
    transfer_reason = fields.Char(string="Motivo del traslado", required=True)
    reference = fields.Char(string="Referencia")
    carrier_id = fields.Many2one(
        "res.partner", string="Transportista", required=True,
        domain="[('supplier_rank', '>', 0)]",
    )
    driver_id = fields.Many2one("step.dispatch.driver", string="Chofer", required=True)
    truck_plate = fields.Char(string="Patente camión", required=True)
    trailer_plate = fields.Char(string="Patente carro/remolque")
    picking_id = fields.Many2one("stock.picking", string="Operación de inventario", copy=False)
    freight_order_id = fields.Many2one("x_orden_de_flete", string="Orden de flete", copy=False)
    line_ids = fields.One2many("step.dispatch.guide.line", "guide_id", string="Detalle", copy=True)
    total_bins = fields.Float(compute="_compute_totals", store=True)
    total_kilos = fields.Float(compute="_compute_totals", store=True)
    amount_untaxed = fields.Monetary(compute="_compute_totals", store=True)
    empty_bins_return = fields.Float(string="Bins vacíos devolución")
    globalgap_certified = fields.Boolean(string="Fruta certificada GLOBALG.A.P.")
    ggn = fields.Char(string="GGN")
    csg = fields.Char(string="CSG")
    note = fields.Html(string="Observaciones")

    _sql_constraints = [
        ("external_folio_company_unique", "unique(external_folio, company_id)",
         "El folio externo ya está registrado para esta empresa."),
    ]

    @api.depends("line_ids.bin_count", "line_ids.quantity_kg", "line_ids.subtotal")
    def _compute_totals(self):
        for guide in self:
            guide.total_bins = sum(guide.line_ids.mapped("bin_count"))
            guide.total_kilos = sum(guide.line_ids.mapped("quantity_kg"))
            guide.amount_untaxed = sum(guide.line_ids.mapped("subtotal"))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == _("Nueva"):
                company = self.env["res.company"].browse(vals.get("company_id")) or self.env.company
                vals["name"] = self.env["ir.sequence"].with_company(company).next_by_code(
                    "step.dispatch.guide") or _("Nueva")
        return super().create(vals_list)

    def action_confirm(self):
        for guide in self:
            if guide.company_id.dispatch_dte_provider != "third_party":
                raise UserError(_(
                    "La emisión DTE tipo 52 con proveedor Odoo aún no está habilitada. "
                    "Use el modo Tercero con un folio emitido externamente."))
            if not guide.line_ids:
                raise UserError(_("Agregue al menos una línea antes de confirmar."))
        self.write({"state": "confirmed"})
        return True

    def action_cancel(self):
        self.write({"state": "cancelled"})
        return True

    def action_draft(self):
        self.write({"state": "draft"})
        return True


class StepDispatchGuideLine(models.Model):
    _name = "step.dispatch.guide.line"
    _description = "Línea de guía de despacho"
    _order = "sequence, id"

    guide_id = fields.Many2one(
        "step.dispatch.guide", required=True, ondelete="cascade", index=True,
    )
    sequence = fields.Integer(default=10)
    product_id = fields.Many2one("product.product", string="Producto", required=True)
    description = fields.Char(required=True)
    product_uom_id = fields.Many2one("uom.uom", string="UM", required=True)
    quantity = fields.Float(required=True, default=1.0)
    price_unit = fields.Monetary(string="Precio unitario")
    subtotal = fields.Monetary(compute="_compute_subtotal", store=True)
    bin_count = fields.Float(string="Bins")
    quantity_kg = fields.Float(string="Kilos")
    currency_id = fields.Many2one(related="guide_id.currency_id", store=True)

    @api.onchange("product_id")
    def _onchange_product_id(self):
        if self.product_id:
            self.description = self.product_id.display_name
            self.product_uom_id = self.product_id.uom_id

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.price_unit

    @api.constrains("quantity", "bin_count", "quantity_kg")
    def _check_non_negative(self):
        for line in self:
            if line.quantity <= 0 or line.bin_count < 0 or line.quantity_kg < 0:
                raise ValidationError(_("Las cantidades deben ser positivas y los totales no negativos."))

