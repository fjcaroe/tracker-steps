# Copyright (C) 2025 - TODAY, jamie.escalante7@gmail.com
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re
from odoo import models, fields, api

class Sector(models.Model):
    _name = "res.sector"
    _inherit = ['mail.thread']

    @api.depends('country_id')
    def _compute_country(self):
        for record in self:
            #record.tax_country_code = record.tax_country_id.code
            return False

    name = fields.Char(string='Sector', track_visibility="onchange")
    # country_id = fields.Many2one(
    #     comodel_name='res.country',
    #     compute='_compute_country',
    # )
    state_id = fields.Many2one(
        'res.country.state', 'Ciudad', required=True)
    city_id = fields.Many2one('res.city', 'Comuna')

    @api.onchange('city_id')
    def onchange_city_id(self):
        if self.city_id:
            # self.city = self.city_id.name
            self.state_id = self.city_id.state_id.id