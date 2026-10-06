"""Shared agricultural attributes owned by Productores, with original field names."""
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'
    step_export_packing = fields.Boolean(string='Packing')
    step_export_packing_type = fields.Selection([
        ('own', 'Propio'), ('grower', 'Productor'), ('third_party', 'Tercero'),
    ], string='Tipo de packing')
    step_export_fundo_ids = fields.One2many('step.fundo', 'partner_id', string='Fundos')


class ProductTemplate(models.Model):
    _inherit = 'product.template'
    step_export_enabled = fields.Boolean(string='Es exportación')
    step_export_species_id = fields.Many2one('step.especie', string='Especie')


class StockPackageType(models.Model):
    _inherit = 'stock.package.type'
    step_export_boxes_per_pallet = fields.Float(string='Cajas por pallet', digits=(12, 2))


class ProductPackaging(models.Model):
    _inherit = 'product.packaging'
    step_export_kg_per_box = fields.Float(string='Kg por caja', digits=(12, 3))


class StockQuantPackage(models.Model):
    _inherit = 'stock.quant.package'

    def _step_liquidation_kg(self):
        self.ensure_one()
        return self.kilos_total

    def _step_producer_shares(self):
        self.ensure_one()
        return [(self.owner_id, 1.0)] if self.owner_id else []
