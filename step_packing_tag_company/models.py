from odoo import api, models
from odoo.exceptions import ValidationError
from odoo import _


class Package(models.Model):
    _inherit = 'stock.quant.package'

    @api.depends('quant_ids.location_id', 'quant_ids.company_id',
                 'step_packing_production_id.company_id', 'step_tag_kind', 'is_fruit_tag')
    def _compute_package_info(self):
        super()._compute_package_info()
        for tag in self:
            production = tag.step_packing_production_id
            if production and tag.is_fruit_tag and tag.step_tag_kind in ('E', 'N'):
                # Inventory remains authoritative whenever the package contains stock.
                if tag.quant_ids and any(q.company_id != production.company_id for q in tag.quant_ids):
                    raise ValidationError(_('Las existencias de la tarja deben pertenecer a la compañía de su OT.'))
                tag.company_id = production.company_id
