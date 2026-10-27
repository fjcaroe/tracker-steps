import base64
import csv
import io
from datetime import date
from pathlib import Path

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged, Form
from odoo.tools import config
from odoo.addons.step_account_treasury.tests.test_treasury import TestTreasuryCommon
from ..hooks import MODULE, LAUNCHERS, post_init_reports


@tagged('post_install', '-at_install')
class TestCommunityReports(TestTreasuryCommon):
    def _report(self, kind='ledger', **values):
        return self.env['step.treasury.report'].create(dict(
            kind=kind, company_id=self.company.id, date_from='2026-09-01', date_to='2026-09-15',
            partner_ids=[Command.set(self.partner_a.ids)], **values))

    def _settle(self, invoice, amount, day):
        receivable = invoice.line_ids.filtered(lambda line: line.account_id.account_type == 'asset_receivable')
        move = self.env['account.move'].create({
            'journal_id': self.bank_journal.id, 'date': day,
            'line_ids': [Command.create({'account_id': self.bank_journal.default_account_id.id, 'debit': amount}),
                         Command.create({'account_id': receivable.account_id.id, 'partner_id': self.partner_a.id, 'credit': amount})],
        })
        move.action_post()
        (receivable + move.line_ids.filtered(lambda line: line.account_id == receivable.account_id)).reconcile()
        return move

    def test_historical_aging_reopens_a_later_paid_invoice(self):
        invoice = self._invoice('out_invoice', date(2026, 9, 3), 100)
        self._settle(invoice, 100, '2026-09-20')
        self.assertTrue(invoice.currency_id.is_zero(invoice.amount_residual))
        report = self._report('receivable')
        result = report.report_data()
        self.assertAlmostEqual(result['closing'], 100)
        self.assertEqual(result['rows'][0]['bucket'], '1–30')
        report.date_to = '2026-09-30'
        self.assertAlmostEqual(report.report_data()['closing'], 0)

    def test_partial_reconciliation_respects_both_dates(self):
        invoice = self._invoice('out_invoice', date(2026, 9, 3), 100)
        self._settle(invoice, 40, '2026-09-10')
        self._settle(invoice, 60, '2026-09-20')
        result = self._report('receivable').report_data()
        self.assertAlmostEqual(result['closing'], 60)
        self.assertAlmostEqual(sum(result['buckets'].values()), 60)

    def test_payable_keeps_signed_balances(self):
        self._invoice('in_invoice', date(2026, 9, 30), 125)
        result = self._report('payable').report_data()
        self.assertAlmostEqual(result['closing'], -125)
        self.assertEqual(result['rows'][0]['bucket'], 'No vencido')

    def test_credit_note_offsets_receivable(self):
        self._invoice('out_invoice', date(2026, 9, 3), 100)
        self._invoice('out_refund', date(2026, 9, 3), 25)
        self.assertAlmostEqual(self._report('receivable').report_data()['closing'], 75)

    def test_ledger_opening_and_movement_equal_closing(self):
        invoice = self._invoice('out_invoice', date(2026, 9, 3), 100)
        self._settle(invoice, 40, '2026-09-10')
        result = self._report().report_data()
        self.assertAlmostEqual(result['opening'], 100)
        self.assertAlmostEqual(result['movement'], -40)
        self.assertAlmostEqual(result['closing'], 60)

    def test_cash_uses_actual_liquidity_entries(self):
        invoice = self._invoice('out_invoice', date(2026, 9, 3), 100)
        self._settle(invoice, 40, '2026-09-10')
        report = self._report('cash')
        report.partner_ids = False
        result = report.report_data()
        lines = report._lines(report._scope() + [('account_id.account_type', '=', 'asset_cash')])
        self.assertAlmostEqual(result['closing'], sum(lines.mapped('balance')))
        self.assertAlmostEqual(result['opening'] + result['movement'], result['closing'])

    def test_bank_reports_native_statement_evidence(self):
        entry = self.env['account.bank.statement.line'].create({
            'journal_id': self.bank_journal.id, 'date': '2026-09-10',
            'payment_ref': 'Report statement fixture', 'amount': 80, 'partner_id': self.partner_a.id})
        report = self._report('bank')
        result = report.report_data()
        self.assertIn(entry.id, [row['id'] for row in result['statements']])
        row = next(row for row in result['statements'] if row['id'] == entry.id)
        self.assertEqual(row['reconciled_now'], entry.is_reconciled)
        self.assertEqual(row['amount'], 80)

    def test_bank_checkpoint_reconciles_statement_and_book(self):
        entry = self.env['account.bank.statement.line'].create({
            'journal_id': self.bank_journal.id, 'date': '2026-09-10',
            'payment_ref': 'Closing statement fixture', 'amount': 80})
        self.env['account.bank.statement'].create({
            'name': 'Closing fixture', 'line_ids': [Command.link(entry.id)],
            'balance_start': 0, 'balance_end_real': 80})
        report = self._report('bank')
        report.partner_ids = False
        anchor = next(row for row in report.report_data()['anchors'] if row['label'] == self.bank_journal.display_name)
        self.assertEqual(anchor['statement'], 80)
        self.assertAlmostEqual(anchor['difference'], 0)

    def test_no_accounting_access_is_not_granted_by_treasury(self):
        user = self.env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Report reader fixture', 'login': 'report_reader_fixture',
            'company_id': self.company.id, 'company_ids': [Command.set(self.company.ids)],
            'groups_id': [Command.set([self.env.ref('base.group_user').id,
                                      self.env.ref('step_account_treasury.group_treasury_reader').id])]})
        with self.assertRaises(AccessError):
            self._report().with_user(user).report_data()

    def test_other_company_cannot_be_requested(self):
        company = self.env['res.company'].create({'name': 'Other report fixture'})
        report = self._report()
        report.company_id = company
        with self.assertRaises(AccessError):
            report.with_context(allowed_company_ids=self.company.ids).report_data()

    def test_invalid_period_is_rejected(self):
        report = self._report()
        report.date_from = '2026-10-01'
        with self.assertRaises(ValidationError):
            report.report_data()

    def test_hidden_menu_cannot_be_bypassed_by_changing_report_kind(self):
        report = self._report()
        self.env.ref('step_account_treasury.menu_treasury_partner_ledger').active = False
        with self.assertRaises(AccessError):
            report.report_data()

    def test_exports_and_screen_use_same_dataset(self):
        self._invoice('out_invoice', date(2026, 9, 3), 100)
        report = self._report('receivable')
        report.action_calculate()
        self.assertIn('100.00', report.result_html)
        report.action_export()
        text = base64.b64decode(report.export_file).decode('utf-8-sig')
        rows = list(csv.reader(io.StringIO(text)))
        self.assertEqual(float(rows[2][-1]), report.report_data()['closing'])
        self.assertIn('Antigüedad', report.result_html)
        self.assertEqual(report.action_print()['report_type'], 'qweb-pdf')
        html, unused = self.env['ir.actions.report']._render_qweb_html(MODULE + '.report_print', report.ids)
        self.assertIn(b'100.00', html)
        pdf, report_type = self.env['ir.actions.report'].with_context(force_report_rendering=True)._render_qweb_pdf(MODULE + '.report_print', report.ids)
        self.assertEqual(report_type, 'pdf')
        self.assertTrue(pdf.startswith(b'%PDF-'))
        if self.env.cr.dbname.startswith(('COMMUNITY_TREASURY_', 'MANAGEMENT_QA_')):
            (Path(config['data_dir']) / 'treasury-report-fixture.pdf').write_bytes(pdf)

    def test_launchers_keep_ids_and_restrictive_groups(self):
        before = {}
        for name, kind, *_ in LAUNCHERS:
            menu = self.env.ref('step_account_treasury.' + name)
            self.assertEqual(menu, self.env.ref(MODULE + '.' + name))
            self.assertEqual(menu.action, self.env.ref(MODULE + '.action_' + kind))
            before[name] = menu.read(['id', 'groups_id', 'parent_id', 'sequence', 'active', 'write_date'])
        post_init_reports(self.env)
        for name, *_ in LAUNCHERS:
            self.assertEqual(before[name], self.env.ref(MODULE + '.' + name).read(['id', 'groups_id', 'parent_id', 'sequence', 'active', 'write_date']))
        Form(self.env['step.treasury.report'], view=MODULE + '.view_report_form')

    def test_operational_amounts_are_stored_historical_values(self):
        self.company.operational_currency_id = self.aux_currency
        self.env['res.currency.rate'].create({'name': '2026-08-01', 'currency_id': self.aux_currency.id,
                                             'company_id': self.company.id, 'rate': 2})
        invoice = self._invoice('out_invoice', date(2026, 9, 3), 100)
        self._settle(invoice, 40, '2026-09-10')
        invoice.line_ids.invalidate_recordset()
        report = self._report('receivable')
        values = report.report_data()
        self.assertEqual(values['rows'][0]['operational_currency'], self.aux_currency.name)
        self.assertAlmostEqual(values['rows'][0]['operational'], 120)
        self.env['res.currency.rate'].create({'name': '2026-09-14', 'currency_id': self.aux_currency.id,
                                             'company_id': self.company.id, 'rate': 19})
        self.assertEqual(values, report.report_data())
