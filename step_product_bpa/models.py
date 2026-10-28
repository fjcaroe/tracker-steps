from odoo import fields, models


class PesticideAptitude(models.Model):
    _name = 'step.agriculture.pesticide.aptitude'
    _description = 'Aptitud plaguicida'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, id'

    name = fields.Char(string='Aptitud plaguicida', required=True, translate=True)
    active = fields.Boolean(default=True)
    code = fields.Char(string='Código aptitud')
    notes = fields.Html(string='Observación')
    sequence = fields.Integer(string='Secuencia')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    registration_concentration = fields.Char(string='Concentración')
    registration_formulation = fields.Char(string='Formulación')
    registration_formulation_code = fields.Char(string='Código formulación')
    registration_aptitude_id = fields.Many2one('step.agriculture.pesticide.aptitude', string='Aptitud plaguicida', ondelete='set null')
    registration_authorization_holder = fields.Char(string='Titular autorización')
    registration_first_authorized_on = fields.Date(string='Primera autorización')
    registration_authorization_expires_on = fields.Date(string='Vencimiento autorización')
