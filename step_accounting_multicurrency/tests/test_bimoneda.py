from odoo import Command, fields
from odoo.tests.common import TransactionCase, tagged
from odoo.tools import SQL


@tagged("post_install", "-at_install")
class TestAccountingBimoneda(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.clp = cls.env.ref("base.CLP")
        cls.usd = cls.env.ref("base.USD")
        cls.clp.active = True
        cls.usd.active = True
        cls.company.currency_id = cls.clp
        cls.company.operational_currency_id = cls.usd
        cls.env["res.currency.rate"].create({
            "currency_id": cls.usd.id,
            "company_id": cls.company.id,
            "name": "2026-08-01",
            "rate": 1 / 950,
        })
        cls.debit_account = cls._account("111101", "Caja prueba", "asset_cash")
        cls.credit_account = cls._account(
            "411101", "Ingreso prueba", "income_other"
        )
        cls.gain_account = cls._account(
            "471101", "Ganancia cambio", "income_other"
        )
        cls.loss_account = cls._account(
            "671101", "Pérdida cambio", "expense"
        )
        cls.company.income_currency_exchange_account_id = cls.gain_account
        cls.company.expense_currency_exchange_account_id = cls.loss_account
        cls.journal = cls.env["account.journal"].create({
            "name": "Diario bimoneda",
            "code": "BIM",
            "type": "general",
            "company_id": cls.company.id,
        })

    @classmethod
    def _account(cls, code, name, account_type):
        return cls.env["account.account"].create({
            "code": code,
            "name": name,
            "account_type": account_type,
            "company_ids": [Command.set(cls.company.ids)],
        })

    def _move(self, date="2026-08-10", invoice_date=False):
        return self.env["account.move"].create({
            "date": date,
            "invoice_date": invoice_date,
            "journal_id": self.journal.id,
            "line_ids": [
                Command.create({
                    "name": "Debe",
                    "account_id": self.debit_account.id,
                    "debit": 9500,
                }),
                Command.create({
                    "name": "Haber",
                    "account_id": self.credit_account.id,
                    "credit": 9500,
                }),
            ],
        })

    def test_rate_uses_earliest_document_or_accounting_date(self):
        move = self._move(date="2026-08-10", invoice_date="2026-08-05")
        self.assertEqual(move.operational_rate_date, fields.Date.to_date("2026-08-05"))
        self.assertAlmostEqual(move.observed_exchange_rate, 950, places=2)

    def test_operational_amounts_are_stored_per_line(self):
        move = self._move()
        debit = move.line_ids.filtered(lambda line: line.debit)
        credit = move.line_ids.filtered(lambda line: line.credit)
        self.assertAlmostEqual(debit.operational_debit, 10, places=2)
        self.assertAlmostEqual(credit.operational_credit, 10, places=2)

    def test_different_line_rates_create_balancing_adjustment(self):
        move = self._move()
        debit = move.line_ids.filtered(lambda line: line.debit)
        credit = move.line_ids.filtered(lambda line: line.credit)
        debit.operational_exchange_rate = 950
        credit.operational_exchange_rate = 1000
        move.action_post()

        adjustment = move.line_ids.filtered("is_operational_exchange_adjustment")
        self.assertEqual(len(adjustment), 1)
        self.assertEqual(adjustment.account_id, self.gain_account)
        self.assertAlmostEqual(sum(move.line_ids.mapped("operational_balance")), 0, places=2)
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0, places=2)

    def test_payment_conversion_in_both_directions(self):
        clp_payment = self.env["account.payment"].new({
            "company_id": self.company.id,
            "currency_id": self.clp.id,
            "amount": 9500,
            "date": "2026-08-10",
        })
        usd_payment = self.env["account.payment"].new({
            "company_id": self.company.id,
            "currency_id": self.usd.id,
            "amount": 10,
            "date": "2026-08-10",
        })
        self.assertAlmostEqual(clp_payment.conversion_amount, 10, places=2)
        self.assertEqual(clp_payment.conversion_currency_id, self.usd)
        self.assertAlmostEqual(usd_payment.conversion_amount, 9500, places=2)
        self.assertEqual(usd_payment.conversion_currency_id, self.clp)

    def test_report_engine_reads_stored_operational_balance(self):
        report = self.env["account.report"].with_context(
            step_operational_report=True
        )
        expression = report._currency_table_apply_rate(
            SQL("account_move_line.balance")
        )
        self.assertIn("operational_balance", str(expression))
