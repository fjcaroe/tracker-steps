# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError

class Pricelist(models.Model):
    _inherit = "product.pricelist"

    @api.model
    def default_get(self, fields):
        res = super(Pricelist, self).default_get(fields)
        if self.env.context.get('step_default_contratista'):
            res.update({
                'group_type': 'contratista'
            })
        if self.env.context.get('step_default_propio'):
            res.update({
                'group_type': 'propio'
            })
        if self.env.context.get('step_default_movi'):
            res.update({
                'group_type': 'contratista',
                'moviliza': True
            })
        if self.env.context.get('step_contra_cosecha'):
            res.update({
                'group_type': 'contratista',
                'cosecha': True
            })
        if self.env.context.get('step_propio_cosecha'):
            res.update({
                'group_type': 'propio',
                'cosecha': True
            })
        return res

    group_type = fields.Selection(string='Tipo tarifa',
                                  selection=[('propio', 'Propio'),
                                             ('contratista', 'Contratista')])
    date_init = fields.Date(string='Inicio Vigencia')
    date_end = fields.Date(string='Final Vigencia')
    # tags_ids
    escalonado = fields.Boolean(
        string="Escalonado",
        default=False,
        help="Si esta check esta opcion el precio de los productos va a realizarse escalonadamente.")
    partner_id = fields.Many2one('res.partner', 'Contratista')
    partner_ids = fields.Many2many('res.partner', 'partner_pricelist_rel', 'partner_id',
                                         'pricelist_id', string='Contratistas')
    responsable_id = fields.Many2one("res.users", string="Creada por")
    user_id = fields.Many2one('hr.employee', string='Autoriza', tracking=True)
    especie_id = fields.Many2one('step.especie',
                                 string="Especie",
                                 required=False, ondelete='cascade', copy=False)
    grupo_variedad_id = fields.Many2one('step.grupo.variedad',
        string="Grupo Variedad",
        required=False, ondelete='cascade', copy=False)
    grupo_variedad_id_domain = fields.Many2many('step.grupo.variedad', 'grupo_variedad_pricelist_rel', 'grupo_variedad_id',
                                         'pricelist_id', string='Grupo Variedad')
    moviliza = fields.Boolean(string='Es movilización?')
    cosecha = fields.Boolean(string='Es Cosecha?')
    transporte_id = fields.Many2one('res.partner', 'Transportista')
    move_item = fields.One2many(
        comodel_name='product.pricelist.move.line',
        inverse_name='pricelist_id',
        string="Moves Lines",
        copy=True, auto_join=True)
    cost_ids = fields.Many2many(comodel_name='account.analytic.account', relation='step_analytic_pricelist_rel', string='Centro costos')