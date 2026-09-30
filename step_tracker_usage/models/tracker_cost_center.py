from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StepTrackerCostCenter(models.Model):
    _name = 'step.tracker.cost_center'
    _description = 'Centro de costo de Web Tracker (sincronizado)'
    _order = 'name'

    tracker_id = fields.Integer(string='ID en Web Tracker', required=True, index=True)
    name = fields.Char(string='Nombre', required=True)
    external_id = fields.Char(string='ID externo')
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Cuenta analítica',
        domain="[('company_id', 'in', [False, company_id])]",
        help='Correspondencia explícita con la cuenta analítica de Odoo. Nunca se '
             'completa por coincidencia de nombre.')
    last_sync = fields.Datetime(string='Última sincronización')
    company_id = fields.Many2one('res.company', string='Empresa', required=True, index=True,
                                 default=lambda self: self.env.company)

    _sql_constraints = [
        ('tracker_id_company_uniq', 'unique(tracker_id, company_id)',
         'Este centro de costo ya está sincronizado para esta empresa.'),
    ]

    @api.constrains('analytic_account_id', 'company_id')
    def _check_analytic_company(self):
        for rec in self:
            account = rec.analytic_account_id
            if account and account.company_id and account.company_id != rec.company_id:
                raise ValidationError(_(
                    'La cuenta analítica %(account)s pertenece a otra empresa.'
                ) % {'account': account.display_name})
