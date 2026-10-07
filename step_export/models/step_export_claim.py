"""Customer claims linked to shipments and fruit tags."""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ExportClaim(models.Model):
    _inherit = "step.export.customer.claim"

    state = fields.Selection([
        ("entered", "Ingresado"), ("accepted", "Aceptado"),
        ("rejected", "Rechazado"),
    ], required=True, default="entered", tracking=True)
    receiver_id = fields.Many2one("res.partner", string="Recibidor", required=True)
    shipment_ids = fields.Many2many("step.export.export", string="Embarques")
    tag_ids = fields.Many2many("stock.quant.package", string="Tarjas")
    available_tag_ids = fields.Many2many("stock.quant.package", compute="_compute_available_tags")
    line_ids = fields.One2many("step.export.claim.line", "claim_id", string="Detalle del reclamo por tarja")
    claim_date = fields.Date(default=fields.Date.context_today, required=True)
    description = fields.Html(string="Descripción")
    claimed_amount_usd = fields.Monetary(string="Monto reclamado USD", currency_field="usd_currency_id")
    accepted_amount_usd = fields.Monetary(string="Monto aceptado USD", currency_field="usd_currency_id")
    usd_currency_id = fields.Many2one("res.currency", default=lambda self: self.env.ref("base.USD"))

    @api.depends("shipment_ids.tag_ids")
    def _compute_available_tags(self):
        for claim in self:
            claim.available_tag_ids = claim.shipment_ids.mapped("tag_ids")

    @api.constrains("shipment_ids", "tag_ids", "line_ids")
    def _check_tag_membership(self):
        for claim in self:
            if (claim.tag_ids | claim.line_ids.mapped("tag_id")) - claim.shipment_ids.mapped("tag_ids"):
                raise ValidationError(_("Las tarjas reclamadas deben pertenecer a los embarques indicados."))

    def action_load_shipment_tags(self):
        self.ensure_one()
        if self.state != "entered" or not self.shipment_ids:
            raise UserError(_("Seleccione los embarques de un reclamo ingresado."))
        existing = self.line_ids.mapped("tag_id")
        self.write({"line_ids": [(0, 0, {"tag_id": tag.id}) for tag in self.available_tag_ids - existing]})
        return True

    def _sync_line_amounts(self):
        for claim in self:
            selected = claim.line_ids.filtered(lambda line: line.claimed_amount_usd or line.accepted_amount_usd)
            claim.write({"claimed_amount_usd": sum(claim.line_ids.mapped("claimed_amount_usd")),
                         "accepted_amount_usd": sum(claim.line_ids.mapped("accepted_amount_usd")),
                         "tag_ids": [(6, 0, selected.mapped("tag_id").ids)]})

    @api.onchange("line_ids", "line_ids.claimed_amount_usd", "line_ids.accepted_amount_usd")
    def _onchange_line_amounts(self):
        if self.line_ids:
            self.claimed_amount_usd = sum(self.line_ids.mapped("claimed_amount_usd"))
            self.accepted_amount_usd = sum(self.line_ids.mapped("accepted_amount_usd"))
            self.tag_ids = self.line_ids.filtered(lambda line: line.claimed_amount_usd or line.accepted_amount_usd).mapped("tag_id")

    def action_accept(self):
        for claim in self:
            if claim.line_ids:
                claim._sync_line_amounts()
            if claim.state != "entered" or not claim.shipment_ids:
                raise UserError(_("El reclamo debe estar ingresado y tener embarques asociados."))
            if claim.accepted_amount_usd < 0 or claim.accepted_amount_usd > claim.claimed_amount_usd:
                raise UserError(_("El monto aceptado debe estar entre cero y el monto reclamado."))
            if claim.tag_ids - claim.shipment_ids.mapped("tag_ids"):
                raise UserError(_("Las tarjas reclamadas deben pertenecer a los embarques indicados."))
            if any(shipment.settlement_id for shipment in claim.shipment_ids):
                raise UserError(_("El embarque ya está liquidado; registre un ajuste posterior separado."))
            claim.shipment_ids.write({"claim_ids": [(4, claim.id)]})
            claim.tag_ids.write({"step_export_claim_ids": [(4, claim.id)]})
            claim.state = "accepted"
        return True

    def action_reject(self):
        if any(claim.state != "entered" for claim in self):
            raise UserError(_("Solo puede rechazar reclamos ingresados."))
        self.write({"state": "rejected"})
        return True

    def write(self, vals):
        locked = {"receiver_id", "shipment_ids", "tag_ids", "line_ids", "claimed_amount_usd",
                  "accepted_amount_usd", "claim_date"}
        if locked.intersection(vals) and any(claim.state != "entered" for claim in self):
            raise UserError(_("El reclamo resuelto conserva sus antecedentes."))
        return super().write(vals)


class ExportClaimLine(models.Model):
    _name = "step.export.claim.line"
    _description = "Detalle de reclamo por tarja"

    claim_id = fields.Many2one("step.export.customer.claim", required=True, ondelete="cascade")
    company_id = fields.Many2one(related="claim_id.company_id", store=True)
    usd_currency_id = fields.Many2one(related="claim_id.usd_currency_id")
    tag_id = fields.Many2one("stock.quant.package", string="Tarja", required=True, ondelete="restrict")
    producer_id = fields.Many2one(related="tag_id.owner_id", string="Productor")
    variety_id = fields.Many2one(related="tag_id.variedad_id", string="Variedad")
    category_id = fields.Many2one(related="tag_id.fruit_category_id", string="Categoría")
    caliber_id = fields.Many2one(related="tag_id.fruit_caliber_id", string="Calibre")
    product_id = fields.Many2one("product.product", compute="_compute_tag_details", string="Producto")
    uom_id = fields.Many2one(related="product_id.uom_id", string="UdM")
    packaging_id = fields.Many2one("product.packaging", compute="_compute_tag_details", string="Embalaje")
    lot_names = fields.Char(compute="_compute_tag_details", string="Lotes")
    box_qty = fields.Integer(related="tag_id.box_count", string="Cajas")
    kg_qty = fields.Float(related="tag_id.kilos_total", string="Kilos")
    claimed_amount_usd = fields.Monetary(string="Reclamado USD", currency_field="usd_currency_id")
    accepted_amount_usd = fields.Monetary(string="Aceptado USD", currency_field="usd_currency_id")
    description = fields.Char(string="Observación")

    _sql_constraints = [("claim_tag_unique", "unique(claim_id, tag_id)", "La tarja ya está en este reclamo.")]

    @api.depends("tag_id", "tag_id.quant_ids.product_id", "tag_id.quant_ids.lot_id")
    def _compute_tag_details(self):
        for line in self:
            tag = line.tag_id
            line.product_id = tag.step_result_product_id if "step_result_product_id" in tag._fields and tag.step_result_product_id else tag.quant_ids.product_id[:1]
            line.packaging_id = tag.step_packaging_id if "step_packaging_id" in tag._fields else False
            line.lot_names = ", ".join(tag.quant_ids.lot_id.mapped("name"))

    @api.constrains("tag_id", "claim_id", "claimed_amount_usd", "accepted_amount_usd")
    def _check_line(self):
        for line in self:
            if line.tag_id not in line.claim_id.shipment_ids.mapped("tag_ids"):
                raise ValidationError(_("La tarja debe pertenecer al embarque reclamado."))
            if line.claimed_amount_usd < 0 or not 0 <= line.accepted_amount_usd <= line.claimed_amount_usd:
                raise ValidationError(_("El monto aceptado debe estar entre cero y el reclamado por tarja."))

    @api.model_create_multi
    def create(self, vals_list):
        claims = self.env["step.export.customer.claim"].browse([vals["claim_id"] for vals in vals_list if vals.get("claim_id")])
        if any(claim.state != "entered" for claim in claims):
            raise UserError(_("El reclamo resuelto conserva sus antecedentes."))
        lines = super().create(vals_list)
        lines.claim_id._sync_line_amounts()
        return lines

    def write(self, vals):
        claims = self.claim_id
        if any(claim.state != "entered" for claim in claims):
            raise UserError(_("El reclamo resuelto conserva sus antecedentes."))
        if vals.get("claim_id") and self.env["step.export.customer.claim"].browse(vals["claim_id"]).state != "entered":
            raise UserError(_("El reclamo resuelto conserva sus antecedentes."))
        result = super().write(vals)
        (claims | self.claim_id)._sync_line_amounts()
        return result

    def unlink(self):
        claims = self.claim_id
        if any(claim.state != "entered" for claim in claims):
            raise UserError(_("El reclamo resuelto conserva sus antecedentes."))
        result = super().unlink()
        claims._sync_line_amounts()
        return result
