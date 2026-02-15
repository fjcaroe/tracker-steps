# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class AccountAnalyticAccount(models.Model):
    _inherit = 'account.analytic.account'

    # cod_costo = fields.Char(string='Código C Costo', required=True)
    type_costo = fields.Selection(
        selection=[
            ('fruta', 'Frutales'),
            ('cultivo', 'Cultivo Anual'),
            ('maquinaria', 'Maquinaria'),
            ('operacional', 'Operacional'),
            ('admin', 'Administrativo')
        ],
        string='Tipo C Costo',
        required=True,
        readonly=False,
        copy=False,
    )
    etapa_costo = fields.Selection(
        selection=[
            ('inver', 'Inversion'),
            ('cre', 'Crecimiento'),
            ('ope', 'Operacion')
        ],
        string='Etapa C Costo',
        required=True,
        readonly=False,
        copy=False,
    )
    fundo_id = fields.Many2one('step.fundo',
                               string="Fundo",
                               required=True, ondelete='cascade', copy=False)
    # sector_id = fields.Many2one('step.sector',
    #     string="Sector",
    #     required=True, ondelete='cascade', copy=False)
    plan_id = fields.Many2one(
        'account.analytic.plan', "Plan Analítico")
    cost_id = fields.Many2one(
        'account.analytic.account', "Cuenta analítica",
    )
    # account_id = fields.Many2one('account.account', string='Cuenta Contable')
    note = fields.Html(string="Notas")
    date = fields.Date(string='Fecha')
    responsable_id = fields.Many2one("res.users", string="Responsable")
    # partner_id = fields.Many2one('res.partner', 'Contacto')
    date_init = fields.Date(string='Fecha de Inicio')
    # tags_ids
    # company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)
    tipo_fruta = fields.Selection(
        selection=[
            ('conven', 'Convencional'),
            ('orga', 'Organico')
        ],
        string='Tipo Fruta',
        required=True,
        readonly=False,
        copy=False,
    )
    maquina_id = fields.Many2one('fleet.vehicle', string='Enlace maquinaria', required=False)
    rendimiento_line = fields.One2many(
        comodel_name='step.rendimiento.line',
        inverse_name='centro_id',
        string="Centro de costo Lines",
        copy=True, auto_join=True)
    cuartel_line = fields.One2many(
        comodel_name='step.cuartel.line',
        inverse_name='centro_id',
        string="Cuarteles Lines",
        copy=True, auto_join=True)
    hilera_line = fields.One2many(
        comodel_name='step.hilera.line',
        inverse_name='centro_id',
        string="Hileras Lines",
        copy=True, auto_join=True)
    # Datos Agricolas
    id_cost = fields.Integer(string='ID')
    cost_id = fields.Many2one(
        'account.analytic.account', "Cuenta analítica",
    )
    especie_id = fields.Many2one(
        'step.especie', "Especie",
    )
    grupo_variedad_id = fields.Many2one('step.grupo.variedad',
                                        string="Grupo Variedad",
                                        required=False, ondelete='cascade', copy=False)
    variedad_id = fields.Many2one('step.variedad',
                                  string="Variedad",
                                  required=False, ondelete='cascade', copy=False)
    date_plant = fields.Date(string='Año Plantación')
    date_prod = fields.Date(string='Año Producción')
    date_prodtivos = fields.Date(string='Años Productivos')
    has_cost = fields.Integer(string='Has CCosto')
    plant_cost = fields.Integer(string='Plantas CCosto')
    date_init_co = fields.Date(string='Fecha Ini Cosecha')
    date_end_co = fields.Date(string='Fecha Fin Cosecha')

class StepCentroCosto(models.Model):
    _name = 'step.centro.costo'

    name = fields.Char(string='Nombre', index=True, required=True)
    # cod_costo = fields.Char(string='Código C Costo', required=True)
    # type_costo = fields.Selection(
    #     selection=[
    #         ('fruta', 'Frutales'),
    #         ('cultivo', 'Cultivo Anual'),
    #         ('maquinaria', 'Maquinaria'),
    #         ('operacional', 'Operacional'),
    #         ('admin', 'Administrativo')
    #     ],
    #     string='Tipo C Costo',
    #     required=True,
    #     readonly=False,
    #     copy=False,
    # )
    # etapa_costo = fields.Selection(
    #     selection=[
    #         ('inver', 'Inversion'),
    #         ('cre', 'Crecimiento'),
    #         ('ope', 'Operacion')
    #     ],
    #     string='Etapa C Costo',
    #     required=True,
    #     readonly=False,
    #     copy=False,
    # )
    # fundo_id = fields.Many2one('step.fundo',
    #     string="Fundo",
    #     required=True, ondelete='cascade', copy=False)
    # # sector_id = fields.Many2one('step.sector',
    # #     string="Sector",
    # #     required=True, ondelete='cascade', copy=False)
    # plan_id = fields.Many2one(
    #     'account.analytic.plan', "Plan Analítico")
    # cost_id = fields.Many2one(
    #     'account.analytic.account', "Cuenta analítica",
    # )
    # account_id = fields.Many2one('account.account', string='Cuenta Contable')
    # note = fields.Html(string="Notas")
    # date = fields.Date(string='Fecha')
    # responsable_id = fields.Many2one("res.users", string="Responsable")
    # partner_id = fields.Many2one('res.partner', 'Contacto')
    # date_init = fields.Date(string='Fecha de Inicio')
    # # tags_ids
    # company_id = fields.Many2one('res.company', string='Empresa', required=True, default=lambda self: self.env.company)
    # tipo_fruta = fields.Selection(
    #     selection=[
    #         ('conven', 'Convencional'),
    #         ('orga', 'Organico')
    #     ],
    #     string='Tipo Fruta',
    #     required=True,
    #     readonly=False,
    #     copy=False,
    # )
    # maquina_id = fields.Many2one('fleet.vehicle', string='Enlace maquinaria', required=False)
    # rendimiento_line = fields.One2many(
    #     comodel_name='step.rendimiento.line',
    #     inverse_name='centro_id',
    #     string="Centro de costo Lines",
    #     copy=True, auto_join=True)
    # cuartel_line = fields.One2many(
    #     comodel_name='step.cuartel.line',
    #     inverse_name='centro_id',
    #     string="Cuarteles Lines",
    #     copy=True, auto_join=True)
    # hilera_line = fields.One2many(
    #     comodel_name='step.hilera.line',
    #     inverse_name='centro_id',
    #     string="Hileras Lines",
    #     copy=True, auto_join=True)
    # #Datos Agricolas
    # id_cost = fields.Integer(string='ID')
    # cost_id = fields.Many2one(
    #     'account.analytic.account', "Cuenta analítica",
    # )
    # especie_id = fields.Many2one(
    #     'step.especie', "Especie",
    # )
    # grupo_variedad_id = fields.Many2one('step.grupo.variedad',
    #                                     string="Grupo Variedad",
    #                                     required=True, ondelete='cascade', copy=False)
    # variedad_id = fields.Many2one('step.variedad',
    #     string="Variedad",
    #     required=True, ondelete='cascade', copy=False)
    # date_plant = fields.Date(string='Año Plantación')
    # date_prod = fields.Date(string='Año Producción')
    # date_prodtivos = fields.Date(string='Años Productivos')
    # has_cost = fields.Integer(string='Has CCosto')
    # plant_cost = fields.Integer(string='Plantas CCosto')
    # date_init_co = fields.Date(string='Fecha Ini Cosecha')
    # date_end_co = fields.Date(string='Fecha Fin Cosecha')
