from contextlib import ExitStack
import base64
from unittest.mock import patch

from lxml import html as etree
from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from .common import action_snapshot, prepare_ce_fixture
from ..models.report_route import ORIGINAL_NAME, RENDERER


@tagged('post_install', '-at_install', 'original_report_ce')
class OriginalPayrollReportRouteCase(TransactionCase):
    def setUp(self):
        super().setUp()
        self.fixture, self.action = prepare_ce_fixture(self)

    def render(self, slip, actor=None, **kwargs):
        reports = self.fixture.scope['ir.actions.report']
        if actor:
            reports = reports.with_user(actor)
        return reports._render_qweb_html(self.action.id, slip.ids, **kwargs)[0]

    def test_existing_action_and_structure_fk_stay_exact_while_stored_html_is_real(self):
        f = self.fixture
        slip = f.closed_slip()
        self.assertEqual(f.structure.report_id, self.action)
        identity = action_snapshot(self.action)
        f.structure.active = False
        f.contract.wage = 9000000
        self.env.flush_all()
        before = f.stored_snapshot(slip)
        with ExitStack() as stack:
            for method in ('compute_sheet', 'get_lines_dict', '_get_paid_amount', '_get_contract_wage', '_compute_provider_totals'):
                stack.enter_context(patch.object(type(slip), method, side_effect=AssertionError('Cannot recompute history')))
            stack.enter_context(patch.object(type(slip.line_ids), '_compute_total', side_effect=AssertionError('Cannot compute totals')))
            html = self.render(slip)
        text = etree.fromstring(html).text_content()
        for value in ('Stored BASIC', 'Stored NEGATIVE', 'Stored ZERO', 'Stored NULL_VALUE',
                      'Original stored payslip name', 'PRIVATE/PDF/1', '-25', '75'):
            self.assertIn(value, text)
        self.assertNotIn('9000000', text)
        self.assertEqual(action_snapshot(self.action), identity)
        self.assertEqual(f.structure.report_id, self.action)
        self.assertEqual(f.stored_snapshot(slip), before)

    def test_zero_negative_null_and_basic_visibility_keep_original_stored_values(self):
        f = self.fixture
        slip = f.closed_slip()
        before = f.stored_snapshot(slip)
        f.structure.hide_basic_on_pdf = True
        html = self.render(slip)
        self.assertNotIn(b'Stored BASIC', html)
        self.assertIn(b'Stored ZERO', html)
        values = f.scope['ir.actions.report']._step_original_report_values(
            f.scope['ir.actions.report']._step_original_report_target(self.action.id), slip.ids)
        totals = {line.code: values['step_report_total'](line) for line in values['step_report_lines'](slip)}
        self.assertEqual(totals['ZERO'], 0)
        self.assertEqual(totals['NEGATIVE'], -25)
        self.assertIsNone(totals['NULL_VALUE'])
        self.assertEqual(f.stored_snapshot(slip), before)

    def test_ambiguous_net_never_selects_a_rule_or_renders_a_cached_result(self):
        f = self.fixture
        slip = f.closed_slip(ambiguous_net=True)
        before = f.stored_snapshot(slip)
        with patch.object(type(self.action), 'retrieve_attachment', side_effect=AssertionError('Cannot read attachments')):
            with self.assertRaisesRegex(UserError, 'different rule identities'):
                self.render(slip)
        self.assertEqual(f.stored_snapshot(slip), before)

    def test_normal_employee_owner_groups_and_company_cannot_be_bypassed_by_sudo(self):
        f = self.fixture
        slip = f.closed_slip()
        owner, other = f.employee_actor(), f.employee_actor('original-route-other-employee')
        f.employee.user_id = owner
        self.assertIn(b'Stored NEGATIVE', self.render(slip, owner))
        reports = f.scope['ir.actions.report'].with_user(other).sudo()
        with self.assertRaises(AccessError):
            reports._render_qweb_html(self.action.id, slip.ids)
        self.action.groups_id = self.env.ref('base.group_system')
        with self.assertRaises(AccessError):
            f.scope['ir.actions.report'].with_user(owner).sudo()._render_qweb_html(self.action.id, slip.ids)
        self.action.groups_id = [Command.clear()]
        foreign = self.env['res.company'].create({'name': 'Private original report foreign company'})
        with self.assertRaises(AccessError):
            f.scope['ir.actions.report'].with_user(owner).sudo().with_context(
                allowed_company_ids=foreign.ids)._render_qweb_html(self.action.id, slip.ids)

    def test_complete_hidden_children_and_field_acl_are_checked_before_pdf_preparation(self):
        f = self.fixture
        slip = f.closed_slip()
        owner = f.employee_actor()
        f.employee.user_id = owner
        reports = f.scope['ir.actions.report'].with_user(owner).sudo()
        for model, row in (('hr.payslip.line', slip.line_ids[:1]),
                           ('hr.payslip.worked_days', slip.worked_days_line_ids[:1])):
            rule = self.env['ir.rule'].create({'name': 'Private original report hidden child',
                'model_id': self.env['ir.model']._get_id(model), 'domain_force': repr([('id', '!=', row.id)])})
            with patch.object(type(self.action), 'retrieve_attachment', side_effect=AssertionError('Cannot retrieve cache')):
                with self.assertRaises(AccessError):
                    reports._pre_render_qweb_pdf(self.action.id, slip.ids)
            rule.unlink()
        field = self.env['hr.payslip.line']._fields['total']
        with patch.object(field, 'groups', 'payroll.group_payroll_manager'):
            with self.assertRaises(AccessError):
                reports._pre_render_qweb_pdf(self.action.id, slip.ids)

    def test_invalid_docids_financial_payload_and_forged_actor_context_are_rejected(self):
        f = self.fixture
        slip = f.closed_slip()
        reports = f.scope['ir.actions.report']
        for ids in (None, [], slip.ids + slip.ids, [True], ['1'], [0]):
            with self.assertRaises(UserError):
                reports._render_qweb_html(self.action.id, ids)
        for data in ({'docs': slip}, {'uid': 1}, {'step_report_net': 999}, {'report_type': 'text'}):
            with self.assertRaises(UserError):
                reports._render_qweb_html(self.action.id, slip.ids, data=data)
        for context in ({'uid': 1}, {'user_id': 1}, {'report_sudo': True}, {'employee_id': f.employee.id}):
            with self.assertRaises(AccessError):
                reports.sudo().with_context(**context)._render_qweb_html(self.action.id, slip.ids)
        with self.assertRaises(AccessError):
            reports._render_qweb_html(self.action.id, slip.ids, data={'context': {'uid': 1}})

    def test_attachment_policy_rejects_before_retrieving_any_existing_cache(self):
        f = self.fixture
        slip = f.closed_slip()
        before = f.stored_snapshot(slip)
        cache = self.env['ir.attachment'].create({'name': 'Existing.pdf', 'type': 'binary',
            'datas': base64.b64encode(b'Private opaque cache must never be returned'),
            'res_model': 'hr.payslip', 'res_id': slip.id, 'mimetype': 'application/octet-stream'})
        cached = cache.read(['id', 'datas', 'res_model', 'res_id', 'public', 'access_token'])
        for policy in ({'attachment': "'Existing.pdf'", 'attachment_use': False},
                       {'attachment': False, 'attachment_use': True}):
            self.action.write(policy)
            identity = action_snapshot(self.action)
            with patch.object(type(self.action), 'retrieve_attachment', side_effect=AssertionError('Cache cannot be read')):
                with self.assertRaisesRegex(UserError, 'Attachment'):
                    f.scope['ir.actions.report'].with_context(report_pdf_no_attachment=True)._render_qweb_pdf(self.action.id, slip.ids)
            self.assertEqual(action_snapshot(self.action), identity)
        self.assertEqual(f.stored_snapshot(slip), before)
        self.assertEqual(cache.read(list(cached[0].keys())), cached)


@tagged('post_install', '-at_install', 'original_report_native')
class NativeOriginalPayrollReportRouteCase(TransactionCase):
    def test_native_backend_is_inert_and_original_action_identity_stays_intact(self):
        reports = self.env['ir.actions.report']
        if reports._step_original_report_ce_renderer() is not None:
            self.skipTest('Native-only no-op contract; CE exercises the actual stored route')
        action = self.env.ref('hr_payroll.action_report_payslip', raise_if_not_found=False)
        self.assertTrue(action)
        before = action_snapshot(action)
        self.assertIsNone(reports._step_original_report_target(action.id))
        self.assertEqual(action_snapshot(action), before)
        renderer = self.env.registry.get('report.' + ORIGINAL_NAME)
        if renderer is not None:
            self.assertNotEqual(renderer._original_module, 'step_payroll_original_report')
        self.assertNotIn(RENDERER, self.env.registry)
