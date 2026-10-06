from odoo import fields, models


class ResPartnerBank(models.Model):
    _inherit = "res.partner.bank"

    step_bancoestado_payment_method = fields.Selection(
        [("01", "01 - Cuenta BancoEstado u otro banco"),
         ("02", "02 - Cuenta de ahorro BancoEstado")],
        string="Forma de pago BancoEstado", default="01",
        help="Código usado por Pago 7 Columnas. La opción 02 sólo es válida para "
             "cuentas de ahorro BancoEstado.",
    )
