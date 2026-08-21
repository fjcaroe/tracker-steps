import calendar
from datetime import date

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


MONTH_SELECTION = [
    ("01", "Enero"), ("02", "Febrero"), ("03", "Marzo"),
    ("04", "Abril"), ("05", "Mayo"), ("06", "Junio"),
    ("07", "Julio"), ("08", "Agosto"), ("09", "Septiembre"),
    ("10", "Octubre"), ("11", "Noviembre"), ("12", "Diciembre"),
]


def default_conversion_currency(env):
    usd = env.ref("base.USD", raise_if_not_found=False)
    return usd if usd and usd.active else env.company.currency_id


class StepManagementExchangeRate(models.Model):
    _name = "step.management.exchange.rate"
    _description = "Tipo de cambio estimado mensual de gestión"
    _order = "year desc, month desc, currency_id"
    _rec_name = "name"

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company", string="Empresa", required=True,
        default=lambda self: self.env.company, index=True,
    )
    company_currency_id = fields.Many2one(
        related="company_id.currency_id", string="Moneda empresa", store=True,
    )
    currency_id = fields.Many2one(
        "res.currency", string="Moneda", required=True, index=True,
        default=lambda self: default_conversion_currency(self.env),
        domain="[('active', '=', True)]",
    )
    year = fields.Integer(
        string="Año", required=True,
        default=lambda self: fields.Date.context_today(self).year, index=True,
    )
    month = fields.Selection(
        MONTH_SELECTION, string="Mes", required=True,
        default=lambda self: "%02d" % fields.Date.context_today(self).month, index=True,
    )
    rate_date = fields.Date(string="Mes de vigencia", compute="_compute_date", store=True, index=True)
    company_value_per_unit = fields.Float(
        string="Valor de 1 unidad en moneda empresa", required=True, digits=(16, 6),
        help="Ejemplo: si 1 USD equivale a 920 CLP, ingrese 920.",
    )
    inverse_value = fields.Float(
        string="Unidades por moneda empresa", compute="_compute_inverse", digits=(16, 10),
    )
    source = fields.Selection(
        [("manual", "Estimación manual"), ("odoo", "Copiada desde tasa real Odoo")],
        string="Origen de la estimación", default="manual", required=True,
    )
    notes = fields.Char(string="Observación")
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "currency_period_company_unique",
            "unique(currency_id, year, month, company_id)",
            "Ya existe un tipo de cambio para esta moneda, empresa, año y mes.",
        ),
    ]

    @api.depends("currency_id", "year", "month")
    def _compute_name(self):
        month_labels = dict(MONTH_SELECTION)
        for record in self:
            currency = record.currency_id.name or _("Moneda")
            record.name = "%s · %s %s" % (
                currency, month_labels.get(record.month, record.month or ""), record.year or "",
            )

    @api.depends("year", "month")
    def _compute_date(self):
        for record in self:
            record.rate_date = (
                date(record.year, int(record.month), 1)
                if record.year and record.month else False
            )

    @api.depends("company_value_per_unit")
    def _compute_inverse(self):
        for record in self:
            record.inverse_value = (
                1.0 / record.company_value_per_unit if record.company_value_per_unit else 0.0
            )

    @api.constrains("year", "company_value_per_unit", "currency_id", "company_id")
    def _check_values(self):
        current_year = fields.Date.context_today(self).year
        for record in self:
            if record.year < 1900 or record.year > current_year + 20:
                raise ValidationError("Ingrese un año válido.")
            if record.company_value_per_unit <= 0:
                raise ValidationError("El valor mensual de la moneda debe ser mayor que cero.")
            if record.currency_id == record.company_id.currency_id and record.company_value_per_unit != 1:
                raise ValidationError("La moneda de la empresa siempre debe tener valor 1.")

    def action_load_odoo_rate(self):
        for record in self:
            if not record.currency_id or not record.company_id or not record.year or not record.month:
                continue
            last_day = calendar.monthrange(record.year, int(record.month))[1]
            rate_date = date(record.year, int(record.month), last_day)
            value = record.currency_id._convert(
                1.0, record.company_id.currency_id, record.company_id, rate_date, round=False,
            )
            record.write({
                "company_value_per_unit": value,
                "source": "odoo",
                "notes": _("Estimación inicial copiada desde la tasa real Odoo al cierre del mes."),
            })

    @api.model
    def _currency_value(self, currency, company, conversion_date, rate_type="estimated"):
        if not currency or not company:
            return 0.0
        if currency == company.currency_id:
            return 1.0
        conversion_date = fields.Date.to_date(conversion_date) or fields.Date.context_today(self)
        if rate_type == "actual":
            return currency._convert(
                1.0, company.currency_id, company, conversion_date, round=False,
            )
        rate = self.search([
            ("company_id", "=", company.id),
            ("currency_id", "=", currency.id),
            ("year", "=", conversion_date.year),
            ("month", "=", "%02d" % conversion_date.month),
            ("active", "=", True),
        ], limit=1)
        return rate.company_value_per_unit if rate else 0.0

    @api.model
    def get_conversion(
        self, amount, source_currency, target_currency, company, conversion_date,
        rate_type="estimated",
    ):
        if not source_currency or not target_currency or not company:
            return {"available": False, "amount": 0.0, "factor": 0.0, "target_value": 0.0}
        if source_currency == target_currency:
            return {"available": True, "amount": amount, "factor": 1.0, "target_value": 1.0}
        source_value = self._currency_value(source_currency, company, conversion_date, rate_type)
        target_value = self._currency_value(target_currency, company, conversion_date, rate_type)
        available = bool(source_value and target_value)
        factor = source_value / target_value if available else 0.0
        return {
            "available": available,
            "amount": amount * factor if available else 0.0,
            "factor": factor,
            "source_value": source_value,
            "target_value": target_value,
        }
