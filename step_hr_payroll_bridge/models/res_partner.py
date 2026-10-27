# © 2025 Jamie Escalante
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Preserve the legacy column/type until the HR retirement audit.
    # Pure Community keeps the native computed relation from account.
    duplicate_bank_partner_ids = fields.Boolean() # bug
