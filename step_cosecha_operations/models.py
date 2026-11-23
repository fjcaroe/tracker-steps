"""Keep harvest rates on the native product and unit selected by the operator."""
from odoo import api, models


class HarvestPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    def _harvest_rate_values(self, values, current=None):
        values = dict(values)
        parent = self.env['product.pricelist'].browse(
            values.get('pricelist_id') or (current.pricelist_id.id if current else False)
            or self.env.context.get('default_pricelist_id'))
        if not parent.cosecha:
            return values
        template = self.env['product.template']
        if values.get('product_id'):
            template = self.env['product.product'].browse(values['product_id']).product_tmpl_id
        elif values.get('product_tmpl_id'):
            template = template.browse(values['product_tmpl_id'])
        elif values.get('labor_id'):
            template = template.browse(values['labor_id'])
        elif current:
            template = current.product_id.product_tmpl_id or current.product_tmpl_id or current.labor_id
        if template:
            # Both fields refer to the same original product.template, not to
            # another catalog. Native price lookup consumes product_tmpl_id.
            values['labor_id'] = template.id
            if current and current.product_id and not values.get('product_id') and (
                    {'labor_id', 'product_tmpl_id'} & values.keys()) and current.product_id.product_tmpl_id != template:
                values['product_id'] = False
                values.setdefault('applied_on', '1_product')
            if not values.get('product_id') and not (current and current.product_id and
                    not {'labor_id', 'product_tmpl_id'} & values.keys()):
                values['product_tmpl_id'] = template.id
                if values.get('applied_on', current.applied_on if current else '1_product') == '1_product':
                    values.setdefault('applied_on', '1_product')
            if not values.get('uom_id') and not (current and current.uom_id):
                values['uom_id'] = template.uom_id.id
        return values

    @api.model_create_multi
    def create(self, values_list):
        return super().create([self._harvest_rate_values(values) for values in values_list])

    def write(self, values):
        incoming = self.env['product.pricelist'].browse(values.get('pricelist_id'))
        ordinary = self.filtered(lambda row: not (incoming or row.pricelist_id).cosecha)
        if ordinary:
            super(HarvestPricelistItem, ordinary).write(values)
        for record in self - ordinary:
            super(HarvestPricelistItem, record).write(self._harvest_rate_values(values, record))
        return True

    @api.onchange('labor_id')
    def _onchange_harvest_labor(self):
        if self.labor_id and (self.pricelist_id.cosecha or
                self.env.context.get('step_propio_cosecha') or self.env.context.get('step_contra_cosecha')):
            self.product_tmpl_id = self.labor_id
            self.product_id = False
            self.applied_on = '1_product'
            if not self.uom_id or self.uom_id.category_id != self.labor_id.uom_id.category_id:
                self.uom_id = self.labor_id.uom_id
