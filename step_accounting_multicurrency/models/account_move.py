from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class AccountMove(models.Model):
    _inherit = "account.move"

    operational_currency_id = fields.Many2one(
        "res.currency",
        string="Moneda operacional",
        copy=False,
        readonly=True,
    )
    operational_rate_date = fields.Date(
        string="Fecha tipo de cambio",
        compute="_compute_operational_rate",
        store=True,
    )
    observed_exchange_rate = fields.Float(
        string="Dólar observado",
        digits=(16, 6),
        compute="_compute_operational_rate",
        store=True,
        readonly=False,
        help="Unidades de moneda principal por una unidad de moneda operacional.",
    )
    operational_debit = fields.Monetary(
        string="Débito operacional",
        currency_field="operational_currency_id",
        compute="_compute_operational_totals",
        store=True,
    )
    operational_credit = fields.Monetary(
        string="Crédito operacional",
        currency_field="operational_currency_id",
        compute="_compute_operational_totals",
        store=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("operational_currency_id"):
                company = self.env["res.company"].browse(
                    vals.get("company_id") or self.env.company.id
                )
                vals["operational_currency_id"] = company.operational_currency_id.id
        return super().create(vals_list)

    @api.depends("date", "invoice_date", "company_id", "operational_currency_id")
    def _compute_operational_rate(self):
        today = fields.Date.context_today(self)
        for move in self:
            dates = [value for value in (move.date, move.invoice_date) if value]
            rate_date = min(dates) if dates else today
            move.operational_rate_date = rate_date
            if not move.operational_currency_id:
                move.observed_exchange_rate = 0.0
                continue
            move.observed_exchange_rate = self.env["res.currency"]._get_conversion_rate(
                move.operational_currency_id,
                move.company_currency_id,
                move.company_id,
                rate_date,
            )

    @api.depends(
        "line_ids.operational_debit",
        "line_ids.operational_credit",
        "operational_currency_id",
    )
    def _compute_operational_totals(self):
        for move in self:
            lines = move.line_ids.filtered(
                lambda line: line.display_type not in ("line_section", "line_note")
            )
            move.operational_debit = sum(lines.mapped("operational_debit"))
            move.operational_credit = sum(lines.mapped("operational_credit"))

    def _operational_adjustment_account(self, signed_amount):
        self.ensure_one()
        # signed_amount > 0 creates an operational debit (loss); a negative
        # amount creates a credit (gain).
        return (
            self.company_id.expense_currency_exchange_account_id
            if signed_amount > 0
            else self.company_id.income_currency_exchange_account_id
        )

    def _sync_operational_adjustment(self):
        """Balancea el libro operacional sin alterar el asiento principal."""
        self.ensure_one()
        adjustments = self.line_ids.filtered("is_operational_exchange_adjustment")
        if not self.operational_currency_id:
            adjustments.unlink()
            return
        if self.observed_exchange_rate <= 0:
            raise UserError(_("Configure un tipo de cambio operacional mayor que cero."))

        ordinary = self.line_ids - adjustments
        difference = sum(ordinary.mapped("operational_balance"))
        currency = self.operational_currency_id
        needed = currency.round(-difference)
        if currency.is_zero(needed):
            adjustments.unlink()
            return

        account = self._operational_adjustment_account(needed)
        if not account:
            raise UserError(_(
                "Configure las cuentas de ganancia y pérdida por diferencia "
                "de cambio antes de contabilizar."
            ))
        values = {
            "name": _("Ajuste bimoneda operacional"),
            "account_id": account.id,
            "currency_id": currency.id,
            "amount_currency": needed,
            "balance": 0.0,
            "operational_exchange_rate": self.observed_exchange_rate,
            "is_operational_exchange_adjustment": True,
        }
        if adjustments:
            (adjustments[:1]).write(values)
            (adjustments - adjustments[:1]).unlink()
        else:
            self.env["account.move.line"].with_context(
                check_move_validity=False
            ).create({**values, "move_id": self.id})

    def action_post(self):
        for move in self.filtered(lambda item: item.state == "draft"):
            move._sync_operational_adjustment()
        return super().action_post()


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    operational_currency_id = fields.Many2one(
        related="move_id.operational_currency_id",
        string="Moneda operacional",
        store=True,
    )
    operational_exchange_rate = fields.Float(
        string="T Cambio",
        digits=(16, 6),
        compute="_compute_operational_exchange_rate",
        store=True,
        readonly=False,
    )
    operational_debit = fields.Monetary(
        string="Débito operacional",
        currency_field="operational_currency_id",
        compute="_compute_operational_amounts",
        store=True,
    )
    operational_credit = fields.Monetary(
        string="Crédito operacional",
        currency_field="operational_currency_id",
        compute="_compute_operational_amounts",
        store=True,
    )
    operational_balance = fields.Monetary(
        string="Saldo operacional",
        currency_field="operational_currency_id",
        compute="_compute_operational_amounts",
        store=True,
    )
    is_operational_exchange_adjustment = fields.Boolean(
        string="Ajuste bimoneda",
        copy=False,
        index=True,
    )

    @api.depends(
        "balance", "amount_currency", "currency_id",
        "move_id.observed_exchange_rate", "move_id.operational_currency_id",
    )
    def _compute_operational_exchange_rate(self):
        for line in self:
            operational = line.move_id.operational_currency_id
            if not operational:
                line.operational_exchange_rate = 0.0
                continue
            rate = line.move_id.observed_exchange_rate
            if line.currency_id == operational and line.amount_currency and line.balance:
                rate = abs(line.balance / line.amount_currency)
            line.operational_exchange_rate = rate

    @api.depends(
        "balance", "amount_currency", "currency_id",
        "operational_exchange_rate", "move_id.operational_currency_id",
        "is_operational_exchange_adjustment",
    )
    def _compute_operational_amounts(self):
        for line in self:
            operational = line.move_id.operational_currency_id
            if not operational:
                line.operational_debit = 0.0
                line.operational_credit = 0.0
                line.operational_balance = 0.0
                continue
            rate = line.operational_exchange_rate
            if line.currency_id == operational and line.amount_currency:
                balance = line.amount_currency
            elif rate:
                balance = line.balance / rate
            else:
                balance = 0.0
            line.operational_balance = balance
            line.operational_debit = max(balance, 0.0)
            line.operational_credit = max(-balance, 0.0)

    @api.constrains("operational_exchange_rate")
    def _check_operational_exchange_rate(self):
        for line in self.filtered("operational_currency_id"):
            if line.operational_exchange_rate < 0:
                raise ValidationError(_("El tipo de cambio no puede ser negativo."))
