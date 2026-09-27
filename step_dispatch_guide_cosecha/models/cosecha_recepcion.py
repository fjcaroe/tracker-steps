from odoo import _, fields, models
from odoo.exceptions import UserError


class StepDispatchGuide(models.Model):
    _inherit = "step.dispatch.guide"

    cosecha_recepcion_id = fields.Many2one(
        "step.cosecha.recepcion", string="Recepción de cosecha", copy=False, index=True,
    )


class StepCosechaRecepcion(models.Model):
    _inherit = "step.cosecha.recepcion"

    dispatch_guide_ids = fields.One2many(
        "step.dispatch.guide", "cosecha_recepcion_id", string="Guías de despacho",
    )
    dispatch_guide_count = fields.Integer(compute="_compute_dispatch_guide_count")

    def _compute_dispatch_guide_count(self):
        for reception in self:
            reception.dispatch_guide_count = len(reception.dispatch_guide_ids)

    def _dispatch_guide_line_vals(self):
        self.ensure_one()
        lines = []
        for line in self.recep_line.filtered(lambda item: item.product_id and item.quantity > 0):
            product = line.product_id.product_variant_id
            description = product.display_name
            if line.tarja:
                description = _("%(product)s - tarja %(tarja)s", product=description, tarja=line.tarja)
            lines.append(fields.Command.create({
                "product_id": product.id,
                "description": description,
                "packaging_id": line.packaging_id.id,
                "bin_count": line.boxes,
                "product_uom_id": (line.uom_id or product.uom_id).id,
                "quantity": line.quantity,
                "quantity_kg": line.quantity,
            }))
        return lines

    def action_create_dispatch_guide(self):
        """Guía de traslado de fruta: razón 5 (traslado interno), del fundo al packing."""
        self.ensure_one()
        lines = self._dispatch_guide_line_vals()
        if not lines:
            raise UserError(_("La recepción no tiene líneas con producto y kilos para trasladar."))
        registry = self.registry_id
        reason = self.env["step.dispatch.transfer.reason"].search([("code", "=", "5")], limit=1)
        origin = registry.fundo_id.display_name if registry and registry.fundo_id else ""
        if registry and registry.cuartel_id:
            origin = f"{origin} - {registry.cuartel_id.display_name}".strip(" -")
        return {
            "type": "ir.actions.act_window",
            "name": _("Nueva guía de despacho"),
            "res_model": "step.dispatch.guide",
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_cosecha_recepcion_id": self.id,
                "default_company_id": self.company_id.id,
                "default_partner_id": self.company_id.partner_id.id,
                "default_transfer_reason_id": reason.id,
                "default_date": self.date,
                "default_origin_address": origin or self.company_id.partner_id.contact_address.replace("\n", ", "),
                "default_destination_address": _("Packing"),
                "default_reference": self.name,
                "default_line_ids": lines,
            },
        }

    def action_view_dispatch_guides(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window", "name": _("Guías de despacho"),
            "res_model": "step.dispatch.guide", "view_mode": "list,form",
            "domain": [("cosecha_recepcion_id", "=", self.id)],
            "context": {"default_cosecha_recepcion_id": self.id},
        }
