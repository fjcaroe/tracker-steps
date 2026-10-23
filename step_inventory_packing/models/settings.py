from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    step_fruit_inventory_enabled = fields.Boolean(
        string="Recepción y tarjas de fruta Steps", default=True)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    step_fruit_inventory_enabled = fields.Boolean(
        related="company_id.step_fruit_inventory_enabled", readonly=False)
