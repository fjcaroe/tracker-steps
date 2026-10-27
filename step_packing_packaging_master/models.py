from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class Packaging(models.Model):
    _inherit = 'product.packaging'

    step_clamshell_qty = fields.Integer(string='Cantidad clamshell', help='Unidades por caja.')
    step_clamshell_weight_g = fields.Float(string='Peso clamshell (g)', digits=(16, 3))
    step_boxes_per_pallet = fields.Float(string='Cajas por pallet', digits=(16, 2))
    step_pallets_per_container = fields.Float(string='Pallet por contenedor', digits=(16, 2))
    step_boxes_per_container_40 = fields.Float(string='Cajas contenedor 40',
        compute='_compute_capacities', store=True, digits=(16, 2))
    step_net_pallet_weight = fields.Float(string='Peso neto pallet (kg)',
        compute='_compute_capacities', store=True, digits=(16, 3))

    @api.depends('step_boxes_per_pallet', 'step_pallets_per_container', 'step_export_kg_per_box')
    def _compute_capacities(self):
        for row in self:
            row.step_boxes_per_container_40 = row.step_boxes_per_pallet * row.step_pallets_per_container
            row.step_net_pallet_weight = row.step_export_kg_per_box * row.step_boxes_per_pallet

    @api.constrains('step_clamshell_qty', 'step_clamshell_weight_g', 'step_boxes_per_pallet', 'step_pallets_per_container')
    def _check_nonnegative_capacity(self):
        for row in self:
            if any(row[name] < 0 for name in ('step_clamshell_qty', 'step_clamshell_weight_g',
                                             'step_boxes_per_pallet', 'step_pallets_per_container')):
                raise ValidationError(_('Las cantidades, capacidades y pesos del embalaje no pueden ser negativos.'))


class FruitBOM(models.Model):
    _inherit = 'mrp.bom'

    @api.model
    def _packaging_material_domain(self):
        labels = ('6 Materiales de embalaje', '6 Materiales de embalajes',
                  'Materiales de embalaje', 'Materiales de embalajes')
        categories = self.env['product.category'].search(expression.OR([
            [('name', '=ilike', label)] for label in labels]))
        roots = categories.filtered(lambda category: not any(
            category.parent_path.startswith(other.parent_path)
            for other in categories if other != category))
        if len(roots) > 1:
            raise ValidationError(_('Hay varias categorías de materiales de embalaje. Unifique el maestro antes de seleccionar componentes.'))
        return [('categ_id', 'child_of', roots.ids)]
