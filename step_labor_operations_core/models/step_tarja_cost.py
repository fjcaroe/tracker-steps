# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

from odoo import api, Command, fields, models, _

class StepTarjaCost(models.Model):
    _name = 'step.tarja.cost'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True)
    tarja_type = fields.Selection(string='Tipo Tarea',
                                  selection=[('propio', 'Propio'),
                                             ('contratista', 'Contratista')], default='propio')
    partner_id = fields.Many2one('res.partner', 'Contratista')
    folio = fields.Char(string='Folio', index=True)
    date = fields.Date(string='Fecha')
    employee_id = fields.Many2one('hr.employee', 'Usuario')
    fundo_id = fields.Many2one('step.fundo',
                               string="Fundo",
                               required=True, ondelete='cascade', copy=False)
    super_id = fields.Many2one('hr.employee', 'Supervisor')
    auto_id = fields.Many2one('hr.employee', 'Autorizador')
    company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)
    note = fields.Html(string="Nota")
    tarja_cost_line = fields.One2many(
        comodel_name='step.tarja.cost.line',
        inverse_name='tarja_cost_id',
        string="tarja Lines",
        copy=True, auto_join=True)
    state = fields.Selection(
        selection=[
            ('in', 'Ingresado'),
            ('auto', 'Autorizado'),
            ('conta', 'Contabilizada'),
            ('pag', 'Pagada'),
        ],
        string='Estado',
        required=True,
        readonly=False,
        copy=False,
        default='in',
    )

    def action_in(self):
        for salary in self:
            salary.write({'state': 'in'})

    def action_auto(self):
        for salary in self:
            salary.write({'state': 'auto'})

    def action_conta(self):
        for salary in self:
            salary.write({'state': 'conta'})

    def action_pag(self):
        for salary in self:
            salary.write({'state': 'pag'})