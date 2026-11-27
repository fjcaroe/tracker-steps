from odoo import fields, models


class PackingProcessType(models.Model):
    _inherit = "step.packing.process.type"

    step_category = fields.Selection([
        ("selection", "Selección"), ("packing", "Embalaje"), ("correction", "Corrección"),
    ], string="Categoría de proceso", default="packing", required=True)
