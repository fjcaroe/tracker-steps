# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class HrRoute(models.Model):
    _name = 'hr.route'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True)
    cod_recorrido = fields.Char(string='Código recorrido')
    km_recorrido = fields.Integer(string='Km recorrido')
    travel_type = fields.Selection(string='Tipo viaje',
                                  selection=[('ida', 'Viaje Ida'),
                                             ('vuelta', 'Viaje Regreso'),('ida_vuelta', 'Viaje Ida y Regreso')], default='ida')
    time_recorrido = fields.Float(string='Tiempo de viaje')
    product_id = fields.Many2one('product.template', 'Servicio relacionado', required=False)
    responsable_id = fields.Many2one("res.users", string="Responsable")
    desde = fields.Char(string='Lugar desde')
    hasta = fields.Char(string='Lugar hasta')
    route_note = fields.Text(string="Notas")
    route_line = fields.One2many(
        comodel_name='hr.route.line',
        inverse_name='route_id',
        string="Route Lines",
        copy=True, auto_join=True)