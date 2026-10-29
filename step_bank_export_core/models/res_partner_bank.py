from odoo import fields, models


class PartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    step_bancoestado_payment_method = fields.Selection([
        ('01', '01 - Cuenta BancoEstado u otro banco'),
        ('02', '02 - Cuenta de ahorro BancoEstado'),
    ], string='Forma de pago BancoEstado', default='01',
       help='Código usado por Pago 7 Columnas. La opción 02 sólo es válida para cuentas de ahorro BancoEstado.')
    step_security_credit_type = fields.Selection([
        ('1', 'Cuenta corriente'), ('2', 'Cuenta vista'), ('3', 'Cuenta de ahorro'),
        ('4', 'Vale vista'), ('5', 'Vale vista On-Line'),
    ], string='Tipo de abono Security')
