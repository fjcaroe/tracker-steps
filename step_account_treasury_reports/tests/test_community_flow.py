"""Real accounting, five original menus and a normal Treasury/accounting actor."""
import base64
from datetime import date

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import Form, tagged
from odoo.tools.safe_eval import safe_eval
from odoo.addons.account.tests.common import AccountTestInvoicingCommon

from odoo.addons.step_account_treasury.report_ownership import CORE, BRIDGE
from odoo.addons.step_treasury_community_reports.hooks import MODULE, LAUNCHERS


@tagged('post_install', '-at_install', 'treasury_community_bridge')
class TreasuryCommunityBridgeFlowCase(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.actor = cls._new_actor('treasury_bridge_accountant', 'account.group_account_manager')
        cls.other_actor = cls._new_actor('treasury_bridge_other', 'account.group_account_manager')
        cls.treasury_only = cls._new_actor('treasury_bridge_reader', None)
        cls.native = cls.env['account.move'].create({
            'name': 'PRIVATE/TREASURY/1', 'move_type': 'out_invoice',
            'partner_id': cls.partner_a.id, 'invoice_date': date(2026, 9, 3),
            'date': date(2026, 9, 3), 'invoice_date_due': date(2026, 9, 10),
            'invoice_payment_term_id': False,
            'invoice_line_ids': [Command.create({'name': 'Treasury bridge fixture',
                'quantity': 1, 'price_unit': 125, 'tax_ids': []})],
        })
        cls.native.action_post()

    @classmethod
    def _new_actor(cls, login, accounting_group):
        groups = [cls.env.ref('base.group_user').id,
                  cls.env.ref(CORE + '.group_treasury_reader').id]
        if accounting_group:
            groups.append(cls.env.ref(accounting_group).id)
        return cls.env['res.users'].with_context(no_reset_password=True).create({
            'name': login, 'login': login, 'company_id': cls.company.id,
            'company_ids': [Command.set(cls.company.ids)], 'groups_id': [Command.set(groups)],
        })

    def _open(self, kind, actor=None):
        actor = actor or self.actor
        # The web client loads actions through this authorized framework API;
        # ordinary accountants do not have Settings access to read action rows.
        action = self.env['ir.actions.actions'].with_user(actor)._for_xml_id(MODULE + '.action_' + kind)
        context = dict(safe_eval(action['context']), allowed_company_ids=self.company.ids)
        with Form(self.env['step.treasury.report'].with_user(actor).with_context(**context),
                  view=MODULE + '.view_report_form') as form:
            form.company_id = self.company
            if kind not in ('receivable', 'payable'):
                form.date_from = date(2026, 9, 1)
            form.date_to = date(2026, 9, 15)
            form.partner_ids.add(self.partner_a)
        return form.record

    def test_five_original_menus_open_real_form_query_csv_and_pdf(self):
        columns = ['id', 'state', 'name', 'amount_total', 'amount_residual', 'write_date']
        before = self.native.read(columns)
        for name, kind, *_ in LAUNCHERS:
            menu = self.env.ref(BRIDGE + '.' + name).with_user(self.actor)
            self.assertEqual(menu, self.env.ref(CORE + '.' + name).with_user(self.actor))
            self.assertIn(menu.id, self.env['ir.ui.menu'].with_user(self.actor)._visible_menu_ids())
            self.assertEqual(menu.action, self.env.ref(MODULE + '.action_' + kind).with_user(self.actor))
            report = self._open(kind)
            report.action_calculate()
            report.action_export()
            self.assertIn(b'Final', base64.b64decode(report.export_file))
            if kind in ('receivable', 'ledger'):
                self.assertAlmostEqual(report.report_data()['closing'], 125)
            if kind == 'receivable':
                self.assertEqual(report.action_print()['report_type'], 'qweb-pdf')
                pdf, report_type = self.env['ir.actions.report'].with_user(self.actor).with_context(
                    force_report_rendering=True)._render_qweb_pdf(MODULE + '.report_print', report.ids)
                self.assertEqual(report_type, 'pdf')
                self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertEqual(self.native.read(columns), before)

    def test_role_owner_company_and_direct_sudo_render_cannot_bypass_access(self):
        report = self._open('receivable')
        report.action_calculate()
        report.action_export()
        # Warm the result and binary before crossing to another real actor.
        self.assertTrue(report.result_html and report.export_file)
        for operation in ('report_data', 'action_calculate', 'action_export', 'action_print'):
            with self.assertRaises(AccessError):
                getattr(report.with_user(self.other_actor).sudo(), operation)()
        with self.assertRaises(AccessError):
            report.with_user(self.other_actor).sudo().read(['result_html', 'export_file'])
        payload = self.env['report.' + MODULE + '.print_document'].with_user(self.other_actor).sudo()
        with self.assertRaises(AccessError):
            payload._get_report_values(report.ids)
        with self.assertRaises(AccessError):
            self.env['step.treasury.report'].with_user(self.treasury_only).create({'kind': 'receivable'})
        other_company = self.env['res.company'].create({'name': 'Private Treasury other company'})
        with self.assertRaises(AccessError):
            report.with_context(allowed_company_ids=other_company.ids).sudo().report_data()
        # Existing restrictive menu groups remain authoritative, even in a
        # report dispatch environment that arrived with sudo enabled.
        menu = self.env.ref(CORE + '.menu_treasury_aged_receivable')
        menu.groups_id = self.env.ref('base.group_system')
        with self.assertRaises(AccessError):
            report.sudo().report_data()
