import math

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools import float_round


class HarvestOrder(models.Model):
    _inherit = 'step.cosecha.registry'

    mobile_standard_weight = fields.Boolean(string='Peso estándar Harvest', copy=False)
    mobile_packaging_id = fields.Many2one('product.packaging', string='Envase de cosecha',
        check_company=True, ondelete='restrict', copy=False)
    mobile_kg_per_box = fields.Float(string='Kg estándar por caja', digits=(12, 3), copy=False)

    @api.constrains('mobile_standard_weight', 'mobile_packaging_id', 'mobile_kg_per_box', 'company_id', 'product_uom_id')
    def _check_mobile_standard_weight(self):
        for order in self:
            if order.mobile_packaging_id and order.mobile_packaging_id.step_packaging_group != 'harvest':
                raise ValidationError(_('Seleccione un embalaje del grupo Cosecha.'))
            if order.mobile_standard_weight and (not order.mobile_packaging_id
                    or not math.isfinite(order.mobile_kg_per_box) or order.mobile_kg_per_box <= 0
                    or order.product_uom_id != self.env.ref('uom.product_uom_unit')):
                raise ValidationError(_('El peso estándar requiere un envase de cosecha con kilos por caja y unidad de conteo.'))


class HarvestDelivery(models.Model):
    _inherit = 'step.cosecha.tarja.registry.line'

    @api.model_create_multi
    def create(self, values_list):
        prepared = []
        for values in values_list:
            order = self.env['step.cosecha.registry'].browse(values.get('registry_id'))
            if values.get('mobile_uid') and order.mobile_standard_weight:
                boxes = float(values.get('qty_caja') or 0)
                if not math.isfinite(boxes) or boxes <= 0 or not boxes.is_integer():
                    raise ValidationError(_('Indique un número entero de cajas mayor que cero.'))
                kilos = float_round(boxes * order.mobile_kg_per_box, precision_digits=2)
                if kilos <= 0:
                    raise ValidationError(_('El peso estándar de la entrega debe ser de al menos 0,01 kg.'))
                values = dict(values, qty_kg=kilos, quantity=boxes)
            prepared.append(values)
        return super().create(prepared)
