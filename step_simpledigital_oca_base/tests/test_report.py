from contextlib import ExitStack
from unittest.mock import patch

from lxml import html as etree
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from .report_fixture import StoredReportFixture


@tagged('post_install', '-at_install', 'stored_payslip_report')
class StoredPayslipReportCase(StoredReportFixture, TransactionCase):
    def test_closed_archived_html_uses_only_stored_values(self):
        slip = self.closed_slip()
        self.structure.active = False
        self.contract.wage = 9000000
        self.env.flush_all()
        before = self.stored_snapshot(slip)
        with ExitStack() as stack:
            for method in ('compute_sheet', 'get_lines_dict', '_get_paid_amount', '_get_contract_wage', '_compute_provider_totals'):
                stack.enter_context(patch.object(type(slip), method, side_effect=AssertionError('Report cannot compute payroll')))
            stack.enter_context(patch.object(type(slip.line_ids), '_compute_total', side_effect=AssertionError('Report cannot compute totals')))
            html = self.rendered_html(slip)
        page = etree.fromstring(html)
        text = page.text_content()
        self.assertIn('<literal> Stored remuneration', text)
        self.assertNotIn(b'<literal>', html)
        self.assertIn('Original stored payslip name', text)
        self.assertIn('PRIVATE/PDF/1', text)
        self.assertIn('Stored BASIC', text)
        self.assertIn('Stored OTHER', text)
        self.assertIn('Stored attendance', text)
        self.assertNotIn('9000000', text)
        self.assertEqual(self.stored_snapshot(slip), before)
        values = self.scope['report.step_simpledigital_oca_base.report_payslip']._get_report_values(slip.ids)
        self.assertEqual(values['step_report_net'](slip), 75)
        totals = {line.code: values['step_report_total'](line) for line in values['step_report_lines'](slip)}
        self.assertIsNone(totals['NULL_VALUE'])
        self.assertEqual((totals['ZERO'], totals['NEGATIVE']), (0, -25))

    def test_hide_basic_is_presentation_only(self):
        slip = self.closed_slip()
        before = self.stored_snapshot(slip)
        self.structure.hide_basic_on_pdf = True
        html = self.rendered_html(slip)
        self.assertNotIn(b'Stored BASIC', html)
        self.assertIn(b'Stored GROSS', html)
        values = self.scope['report.step_simpledigital_oca_base.report_payslip']._get_report_values(slip.ids)
        self.assertEqual(values['step_report_net'](slip), 75)
        self.assertEqual(values['step_report_category_total'](slip, ['GROSS']), 100)
        self.assertEqual(self.stored_snapshot(slip), before)

    def test_repeated_net_same_original_rule_is_additive(self):
        slip = self.closed_slip(split_net=True)
        values = self.scope['report.step_simpledigital_oca_base.report_payslip']._get_report_values(slip.ids)
        self.assertEqual(values['step_report_net'](slip), 100)

    def test_net_different_original_rule_is_not_arbitrarily_selected(self):
        slip = self.closed_slip(ambiguous_net=True)
        before = self.stored_snapshot(slip)
        with self.assertRaises(UserError):
            self.rendered_html(slip)
        self.assertEqual(self.stored_snapshot(slip), before)

    def test_employee_own_print_does_not_grant_configuration_or_other_salary_access(self):
        slip = self.closed_slip()
        owner = self.employee_actor()
        self.employee.user_id = owner
        self.structure.active = False
        before = self.stored_snapshot(slip)
        self.assertIn(b'Stored BASIC', self.rendered_html(slip, owner))
        renderer = self.scope['report.step_simpledigital_oca_base.report_payslip'].with_user(owner).sudo().with_context(uid=1)
        values = renderer._get_report_values(slip.ids, data={'uid': 1, 'report_sudo': True})
        self.assertFalse(values['docs'].env.su)
        self.assertEqual(values['docs'].env.uid, owner.id)
        with self.assertRaises(AccessError):
            self.structure.with_user(owner).read(['payslip_name'])
        with self.assertRaises(AccessError):
            self.rules['NET'].with_user(owner).read(['amount_python_compute'])
        other = self.employee_actor('private-stored-pdf-other')
        with self.assertRaises(AccessError):
            self.rendered_html(slip, other)
        with self.assertRaises(AccessError):
            renderer.with_user(other).sudo()._get_report_values(slip.ids, data={'uid': owner.id})
        self.assertEqual(self.stored_snapshot(slip), before)

    def test_hidden_salary_or_day_refuses_entire_report(self):
        slip = self.closed_slip()
        owner = self.employee_actor()
        self.employee.user_id = owner
        for model, record in (('hr.payslip.line', slip.line_ids[:1]),
                              ('hr.payslip.worked_days', slip.worked_days_line_ids[:1])):
            rule = self.env['ir.rule'].create({'name': 'Private hidden PDF child',
                'model_id': self.env['ir.model']._get_id(model),
                'domain_force': repr([('id', '!=', record.id)])})
            with self.assertRaises(AccessError):
                self.rendered_html(slip, owner)
            with self.assertRaises(AccessError):
                self.scope['report.step_simpledigital_oca_base.report_payslip'].with_user(owner).sudo()._get_report_values(slip.ids)
            rule.unlink()

    def test_field_acl_cannot_be_bypassed_by_stored_sql_payload(self):
        slip = self.closed_slip()
        owner = self.employee_actor()
        self.employee.user_id = owner
        field = self.env['hr.payslip.line']._fields['total']
        with patch.object(field, 'groups', 'payroll.group_payroll_manager'):
            with self.assertRaises(AccessError):
                self.rendered_html(slip, owner)

    def test_action_identity_selection_and_untrusted_report_data(self):
        slip = self.closed_slip()
        report = self.scope.ref('payroll.action_report_payslip')
        action_id = report.id
        action = report.report_action(slip, config=False)
        self.assertEqual(action['report_name'], 'step_simpledigital_oca_base.report_payslip')
        self.assertEqual(action['report_type'], 'qweb-pdf')
        self.assertEqual(report.binding_model_id.model, 'hr.payslip')
        self.assertFalse(report.attachment_use)
        self.assertEqual(self.scope.ref('payroll.action_report_payslip').id, action_id)
        self.assertFalse(self.scope.ref('hr_payroll.action_report_payslip', raise_if_not_found=False))
        renderer = self.scope['report.step_simpledigital_oca_base.report_payslip']
        for ids in ([], slip.ids + slip.ids, [True], ['1']):
            with self.assertRaises(UserError):
                renderer._get_report_values(ids)
        values = renderer._get_report_values(slip.ids, data={'docs': None, 'step_report_net': 'fake'})
        self.assertEqual(values['docs'], slip)
        self.assertEqual(values['step_report_net'](slip), 75)
