# -*- coding: utf-8 -*-

from odoo import fields, models


class HrRoute(models.Model):
    _name = 'hr.route'
    _inherit = ['mail.thread']
    _description = 'Recorrido de movilización'

    name = fields.Char(string='Nombre', index=True, required=True)
    company_id = fields.Many2one('res.company', string='Empresa', required=True,
                                  default=lambda self: self.env.company)
    active = fields.Boolean(default=True)
    cod_recorrido = fields.Char(string='Código recorrido')
    km_recorrido = fields.Integer(string='Km recorrido')
    travel_type = fields.Selection(
        string='Tipo viaje',
        selection=[('ida', 'Viaje ida'), ('vuelta', 'Viaje regreso'), ('ida_vuelta', 'Viaje ida y regreso')],
        default='ida')
    time_recorrido = fields.Float(string='Tiempo de viaje (hrs)')
    product_id = fields.Many2one('product.template', 'Servicio relacionado')
    responsable_id = fields.Many2one("res.users", string="Responsable")
    desde = fields.Char(string='Lugar desde')
    hasta = fields.Char(string='Lugar hasta')
    route_note = fields.Text(string="Notas")
    route_line = fields.One2many('hr.route.line', 'route_id', string="Paradas", copy=True, auto_join=True)
