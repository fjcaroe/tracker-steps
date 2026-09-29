"""Envases de cosecha en ubicaciones internas por productor.

Los traslados nativos conservan inventario y valoración de la empresa;
los saldos se leen de stock.quant, sin un libro paralelo de unidades.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    step_is_harvest_container = fields.Boolean(string="Es envase de cosecha")


class StockLocation(models.Model):
    _inherit = "stock.location"

    step_producer_id = fields.Many2one("res.partner", string="Productor de envases", index=True)

    @api.constrains("step_producer_id", "usage")
    def _check_step_container_location(self):
        for location in self:
            if location.step_producer_id and location.usage != "internal":
                raise ValidationError(_("La ubicación de envases del productor debe ser interna."))


class ResPartner(models.Model):
    _inherit = "res.partner"

    def action_step_container_location(self):
        self.ensure_one()
        if not self.company_id and not self.env.company:
            raise UserError(_("Seleccione una empresa para el productor."))
        company = self.company_id or self.env.company
        location = self.env["stock.location"].search([
            ("step_producer_id", "=", self.id), ("company_id", "=", company.id),
        ], limit=1)
        if not location:
            warehouse = self.env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
            if not warehouse:
                raise UserError(_("La empresa necesita una bodega antes de crear la ubicación de envases."))
            location = self.env["stock.location"].create({
                "name": "Envases en productor: %s" % self.display_name,
                "usage": "internal",
                "location_id": warehouse.view_location_id.id,
                "company_id": company.id,
                "step_producer_id": self.id,
            })
        return {
            "type": "ir.actions.act_window", "name": _("Envases en productor"),
            "res_model": "stock.location", "res_id": location.id,
            "view_mode": "form", "target": "current",
        }
