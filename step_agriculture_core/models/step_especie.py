# © 2025 (Jamie Escalante <jamie.escalante7@gmail.com>)
# -*- coding: utf-8 -*-

import base64
from odoo import api, fields, models, tools, SUPERUSER_ID, _, Command


class StepEspecie(models.Model):
    _name = 'step.especie'
    _inherit = ['mail.thread']

    name = fields.Char(string='Nombre', index=True, required=True)
    cod_especie = fields.Char(string='Código Especie')
    date_init = fields.Date(string='Inicio Cosecha')
    date_end = fields.Date(string='Final Cosecha')
    plan_id = fields.Many2one(
        'account.analytic.plan', "Plan Analítico")
    kg_caja = fields.Float(string='Kg Caja Base')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    type_especie = fields.Selection(
        selection=[
            ('frutal', 'Frutales'),
            ('hortali', 'Hortalizas'),
            ('otro', 'Otros'),
        ],
        string='Tipo Especie',
        required=True,
        readonly=False,
        copy=False,
    )
    group_especie = fields.Selection(
        selection=[
            ('fruta_h', 'Frutas de Hueso'),
            ('poma', 'Pomáceas'),
            ('citri', 'Cítricos'),
            ('baya', 'Bayas - Berries'),
            ('seco', 'Frutos Secos'),
            ('exo', 'Tropicales - Exótica'),
            ('palta', 'Paltas'),
            ('uva', 'Uvas'),
        ],
        string='Grupo especie',
        required=True,
        readonly=False,
        copy=False,
    )
    cost_id = fields.Many2one(
        'account.analytic.account', "Cuenta analítica",
        check_company=True)
    plu = fields.Char(string='PLU')
    note = fields.Text(string="Notas")
    especie_line = fields.One2many(
        comodel_name='step.especie.line',
        inverse_name='especie_id',
        string="Especie Lines",
        copy=True, auto_join=True)

    @api.depends('name', 'user_ids.share', 'image_1920', 'is_company', 'type')
    def _compute_avatar_1920(self):
        super()._compute_avatar_1920()

    @api.depends('name', 'user_ids.share', 'image_1024', 'is_company', 'type')
    def _compute_avatar_1024(self):
        super()._compute_avatar_1024()

    @api.depends('name', 'user_ids.share', 'image_512', 'is_company', 'type')
    def _compute_avatar_512(self):
        super()._compute_avatar_512()

    @api.depends('name', 'user_ids.share', 'image_256', 'is_company', 'type')
    def _compute_avatar_256(self):
        super()._compute_avatar_256()

    @api.depends('name', 'user_ids.share', 'image_128', 'is_company', 'type')
    def _compute_avatar_128(self):
        super()._compute_avatar_128()

    def _compute_avatar(self, avatar_field, image_field):
        partners_with_internal_user = self.filtered(
            lambda partner: partner.user_ids - partner.user_ids.filtered('share'))
        super(StepEspecie, partners_with_internal_user)._compute_avatar(avatar_field, image_field)
        partners_without_image = (self - partners_with_internal_user).filtered(lambda p: not p[image_field])
        for _, group in tools.groupby(partners_without_image, key=lambda p: p._avatar_get_placeholder_path()):
            group_partners = self.env['step.especie'].concat(*group)
            group_partners[avatar_field] = base64.b64encode(group_partners[0]._avatar_get_placeholder())

        for partner in self - partners_with_internal_user - partners_without_image:
            partner[avatar_field] = partner[image_field]

    def _avatar_get_placeholder_path(self):
        if self.is_company:
            return "base/static/img/company_image.png"
        if self.type == 'delivery':
            return "base/static/img/truck.png"
        if self.type == 'invoice':
            return "base/static/img/money.png"
        return super()._avatar_get_placeholder_path()