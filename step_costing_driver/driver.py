from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CostingDriver(models.Model):
    # Keep the existing technical identity for installations of Aserradero.
    _name = "step.sawmill.costing.driver"
    _description = "Driver de costeo"
    _order = "sequence, name"

    name = fields.Char(string="Nombre", required=True, translate=True)
    sequence = fields.Integer(string="Secuencia", default=10)
    active = fields.Boolean(string="Activo", default=True)
    company_id = fields.Many2one("res.company", string="Empresa")
    uom_id = fields.Many2one("uom.uom", string="Unidad de medida")

    @api.constrains("name", "company_id")
    def _check_unique_name(self):
        for driver in self:
            if self.with_context(active_test=False).search_count([
                ("id", "!=", driver.id), ("name", "=ilike", driver.name),
                ("company_id", "=", driver.company_id.id),
            ], limit=1):
                raise ValidationError(_("Ya existe el driver %s para esta empresa.") % driver.display_name)
