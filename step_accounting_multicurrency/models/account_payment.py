from odoo import api, fields, models


def _conversion_values(record, date):
    company = record.company_id or record.env.company
    operational = company.operational_currency_id
    values = {
        "operational_currency_id": operational,
        "observed_exchange_rate": 0.0,
        "conversion_amount": 0.0,
        "conversion_currency_id": False,
    }
    if not operational:
        return values
    date = date or fields.Date.context_today(record)
    rate = record.env["res.currency"]._get_conversion_rate(
        operational, company.currency_id, company, date
    )
    values["observed_exchange_rate"] = rate
    if record.currency_id == company.currency_id:
        values["conversion_currency_id"] = operational
        values["conversion_amount"] = record.amount / rate if rate else 0.0
    elif record.currency_id == operational:
        values["conversion_currency_id"] = company.currency_id
        values["conversion_amount"] = record.amount * rate
    else:
        values["conversion_currency_id"] = operational
        values["conversion_amount"] = record.currency_id._convert(
            record.amount, operational, company, date
        )
    return values


class AccountPayment(models.Model):
    _inherit = "account.payment"

    operational_currency_id = fields.Many2one(
        "res.currency", string="Moneda operacional",
        compute="_compute_operational_payment", store=True,
    )
    observed_exchange_rate = fields.Float(
        string="Dólar observado", digits=(16, 6),
        compute="_compute_operational_payment", store=True,
    )
    conversion_amount = fields.Monetary(
        string="Valor conversión", currency_field="conversion_currency_id",
        compute="_compute_operational_payment", store=True,
    )
    conversion_currency_id = fields.Many2one(
        "res.currency", string="Moneda de conversión",
        compute="_compute_operational_payment", store=True,
    )

    @api.depends("company_id", "currency_id", "amount", "date")
    def _compute_operational_payment(self):
        for payment in self:
            for name, value in _conversion_values(payment, payment.date).items():
                payment[name] = value


class AccountPaymentRegister(models.TransientModel):
    _inherit = "account.payment.register"

    operational_currency_id = fields.Many2one(
        "res.currency", string="Moneda operacional",
        compute="_compute_operational_payment",
    )
    observed_exchange_rate = fields.Float(
        string="Dólar observado", digits=(16, 6),
        compute="_compute_operational_payment",
    )
    conversion_amount = fields.Monetary(
        string="Valor conversión", currency_field="conversion_currency_id",
        compute="_compute_operational_payment",
    )
    conversion_currency_id = fields.Many2one(
        "res.currency", string="Moneda de conversión",
        compute="_compute_operational_payment",
    )

    @api.depends("company_id", "currency_id", "amount", "payment_date")
    def _compute_operational_payment(self):
        for payment in self:
            values = _conversion_values(payment, payment.payment_date)
            for name, value in values.items():
                payment[name] = value
