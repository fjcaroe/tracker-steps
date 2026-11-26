from odoo import fields, models


class MrpBom(models.Model):
    _inherit = 'mrp.bom'

    # Preserve Cerro's original technical name, label and independent relation.
    x_studio_compaia = fields.Many2one('res.company', string='Compa\u00f1ia', ondelete='set null', copy=True)
