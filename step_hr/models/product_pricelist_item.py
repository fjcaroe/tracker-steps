# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command

class PricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    @api.depends('product_id')
    def compute_product_template_domain(self):
        domain = []
        if self.env.context.get('step_default_contratista') or self.env.context.get('step_default_propio'):
            domain = [('is_labor', '=', True)]
        if self.env.context.get('step_contra_cosecha') or self.env.context.get('step_propio_cosecha'):
            domain = [('cosecha', '=', True)]
        self.product_id_domain = self.env['product.template'].search(domain).ids

    labor_id = fields.Many2one(
        comodel_name='product.template',
        string="Labor / Tarea",
        required=True, ondelete='cascade', index=True, copy=False)
    can_std = fields.Float(string='Cantidad Standar')
    can_max = fields.Float(string='Cantidad Máxima')
    tarifa_trato = fields.Float(string='Tarifa trato')
    uom_id = fields.Many2one('uom.uom', 'UdM', required=True)
    uom_trato = fields.Many2one('uom.uom', 'Relación Trato', required=False)
    product_id_domain = fields.Many2many('product.template', 'product_pricelist_rel', 'product_id',
                                          'pricelist_id', string='Productos domain', compute='compute_product_template_domain', store=True)