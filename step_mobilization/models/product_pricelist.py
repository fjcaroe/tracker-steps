# -*- coding: utf-8 -*-

from odoo import api, fields, models


class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    moviliza = fields.Boolean(string='¿Es movilización?')
    transporte_id = fields.Many2one('res.partner', 'Transportista',
                                     domain=[('step_trans_person', '=', True)])
    move_item = fields.One2many('product.pricelist.move.line', 'pricelist_id',
                                 string="Tarifas por recorrido", copy=True, auto_join=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if self.env.context.get('step_default_movi'):
            res.update({'group_type': 'contratista', 'moviliza': True})
        return res
