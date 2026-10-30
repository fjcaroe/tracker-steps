"""Real tests, wizard, typed observations, approvals, UoM and preserved results."""
import json
from unittest import TestCase
from unittest.mock import patch

from odoo import api, Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import json_default
from odoo.addons.step_quality_contracts.access import original_quality_provider


@tagged('post_install', '-at_install')
class QualityOcaOperationCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({'name': 'Private OCA QA company'})
        actor = cls.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private OCA QA manager',
            'login': 'private-oca-qa-manager', 'company_id': cls.company.id, 'company_ids': [Command.set(cls.company.ids)],
            'groups_id': [Command.set([cls.env.ref(alias).id for alias in ('base.group_user',
                'quality_control_oca.group_quality_control_manager', 'uom.group_uom')])]})
        cls.scope = api.Environment(cls.env.cr, actor.id, dict(cls.env.context, allowed_company_ids=cls.company.ids,
            lang='en_US', tracking_disable=True, mail_create_nosubscribe=True), su=False)
        cls.env['ir.sequence'].create({'name': 'Private OCA inspection numbering', 'code': 'qc.inspection',
            'company_id': cls.company.id, 'implementation': 'no_gap', 'prefix': 'PRIVATE/QC/'})
        cls.product = cls.env['product.product'].create({'name': 'Private actual quality product'})
        cls.kg = cls.scope.ref('uom.product_uom_kgm')
        cls.test = cls.scope['qc.test'].create({'name': 'Private actual quality test', 'company_id': cls.company.id,
            'fill_correct_values': False, 'test_lines': [Command.create({'name': 'Actual weight', 'type': 'quantitative',
                'min_value': .9, 'max_value': 1.1, 'uom_id': cls.kg.id}),
                Command.create({'name': 'Actual appearance', 'type': 'qualitative', 'ql_values': [
                    Command.create({'name': 'Accepted', 'ok': True}), Command.create({'name': 'Rejected', 'ok': False})]})]})
        cls.answer = cls.test.test_lines.filtered(lambda row: row.type == 'qualitative').ql_values.filtered('ok')

    def _inspection(self, measured=1.0, accepted=True):
        inspection = self.scope['qc.inspection'].create({'company_id': self.company.id,
            'object_id': 'product.product,%s' % self.product.id, 'qty': 1})
        wizard = self.scope['qc.inspection.set.test'].with_context(active_model='qc.inspection', active_id=inspection.id).create({'test': self.test.id})
        self.assertTrue(wizard.action_create_test())
        for line in inspection.inspection_lines:
            if line.question_type == 'quantitative' and measured is not None:
                line.quantitative_value = measured
            elif accepted is not None:
                answer = line.possible_ql_values.filtered(lambda row: row.ok == accepted)
                self.assertEqual(len(answer), 1)
                line.qualitative_value = answer
        return inspection

    def _snapshot(self, inspections):
        self.env.flush_all()
        result = []
        for table, inverse in (('qc_inspection', 'id'), ('qc_inspection_line', 'inspection_id')):
            self.env.cr.execute('SELECT to_jsonb(t) FROM ' + table + ' t WHERE ' + inverse + '=ANY(%s) ORDER BY id', (inspections.ids,))
            result.append(self.env.cr.fetchall())
        return result

    def test_actual_wizard_measurements_success_and_real_form(self):
        self.assertNotIn('quality.check', self.scope.registry)
        inspection = self._inspection(measured=None)
        original_ids = inspection.inspection_lines.ids
        measured = inspection.inspection_lines.filtered(lambda row: row.question_type == 'quantitative')
        self.env.flush_all()
        self.env.cr.execute('SELECT quantitative_value FROM qc_inspection_line WHERE id=%s', (measured.id,))
        self.assertIsNone(self.env.cr.fetchone()[0])
        inspection.action_todo()
        unmeasured = self._snapshot(inspection)
        with TestCase.assertRaisesRegex(self, UserError, 'NULL'):
            inspection.action_confirm()
        self.assertEqual(self._snapshot(inspection), unmeasured)
        measured.quantitative_value = 1.0
        inspection.action_confirm()
        self.assertEqual(inspection.state, 'success')
        self.assertTrue(inspection.success)
        self.assertEqual(inspection.inspection_lines.ids, original_ids)
        self.assertTrue(inspection.date_done)
        view = self.scope['qc.inspection'].get_view(view_id=self.scope.ref('quality_control_oca.qc_inspection_form_view').id, view_type='form')
        self.assertIn('action_confirm', view['arch'])
        self.assertIn('inspection_lines', view['arch'])
        data = self.scope['qc.inspection'].get_step_quality_overview()
        self.assertEqual(data['passed'], 1)
        self.assertFalse(data['native_identity_converted'])
        json.dumps(data, default=json_default)
        with TestCase.assertRaises(self, UserError):
            original_quality_provider(self.scope)

    def test_actual_failed_result_requires_manager_and_closes_on_approval(self):
        inspection = self._inspection(measured=1.5)
        inspection.action_todo()
        inspection.action_confirm()
        self.assertEqual(inspection.state, 'waiting')
        user = self.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private QC operator',
            'login': 'private-qc-operator', 'company_id': self.company.id, 'company_ids': [Command.set(self.company.ids)],
            'groups_id': [Command.set([self.env.ref('base.group_user').id, self.env.ref('quality_control_oca.group_quality_control_user').id])]})
        before = self._snapshot(inspection)
        with TestCase.assertRaises(self, UserError):
            inspection.with_user(user).sudo().action_approve()
        self.assertEqual(self._snapshot(inspection), before)
        inspection.action_approve()
        self.assertEqual(inspection.state, 'failed')
        self.assertFalse(inspection.success)

    def test_real_cross_unit_conversion_uses_official_uom_api_without_rewriting_measurement(self):
        inspection = self._inspection(measured=1000)
        line = inspection.inspection_lines.filtered(lambda row: row.question_type == 'quantitative')
        gram = self.scope.ref('uom.product_uom_gram')
        line.uom_id = gram
        self.assertEqual(gram._compute_quantity(1000, self.kg, round=False), 1)
        inspection.action_todo()
        inspection.action_confirm()
        self.assertEqual(inspection.state, 'success')
        self.assertEqual(line.quantitative_value, 1000)
        self.assertEqual(line.uom_id, gram)
        self.assertEqual(line.test_uom_id, self.kg)

    def test_batch_missing_answer_or_physical_measurement_rejects_before_first_state(self):
        first, second = self._inspection(), self._inspection(accepted=None)
        (first | second).action_todo()
        before = self._snapshot(first | second)
        with TestCase.assertRaises(self, UserError):
            (first | second).action_confirm()
        self.assertEqual(self._snapshot(first | second), before)
        second.inspection_lines.filtered(lambda row: row.question_type == 'qualitative').qualitative_value = self.answer
        line = second.inspection_lines.filtered(lambda row: row.question_type == 'quantitative')
        self.env.flush_all()
        self.env.cr.execute('UPDATE qc_inspection_line SET quantitative_value=NULL WHERE id=%s', (line.id,))
        line.invalidate_recordset(['quantitative_value'])
        self.assertEqual(line.quantitative_value, 0)
        before = self._snapshot(first | second)
        with TestCase.assertRaisesRegex(self, UserError, 'NULL'):
            (first | second).action_confirm()
        self.assertEqual(self._snapshot(first | second), before)

    def test_complete_child_and_answer_permissions_reject_warm_sudo_without_closing(self):
        inspection = self._inspection()
        inspection.action_todo()
        before = self._snapshot(inspection)
        inspection.sudo().inspection_lines.read(['success'])
        line = inspection.inspection_lines[:1]
        rule = self.env['ir.rule'].create({'name': 'Private hidden quality line',
            'model_id': self.env['ir.model']._get_id('qc.inspection.line'), 'domain_force': "[('id','!=',%s)]" % line.id})
        with TestCase.assertRaises(self, AccessError):
            inspection.sudo().action_confirm()
        self.assertEqual(self._snapshot(inspection), before)
        rule.unlink()
        rule = self.env['ir.rule'].create({'name': 'Private hidden original answer',
            'model_id': self.env['ir.model']._get_id('qc.test.question.value'), 'domain_force': "[('id','!=',%s)]" % self.answer.id})
        with TestCase.assertRaises(self, AccessError):
            inspection.sudo().action_confirm()
        self.assertEqual(self._snapshot(inspection), before)

    def test_field_acl_and_foreign_company_cannot_be_bypassed_by_sudo(self):
        inspection = self._inspection()
        inspection.action_todo()
        before = self._snapshot(inspection)
        field = self.scope['qc.inspection.line']._fields['quantitative_value']
        with patch.object(field, 'groups', 'base.group_system'):
            with TestCase.assertRaises(self, AccessError):
                inspection.sudo().action_confirm()
        self.assertEqual(self._snapshot(inspection), before)
        company = self.env['res.company'].create({'name': 'Private foreign QC company'})
        actor = self.env['res.users'].with_context(no_reset_password=True).create({'name': 'Private foreign QC manager',
            'login': 'private-foreign-qc-manager', 'company_id': company.id, 'company_ids': [Command.set(company.ids)],
            'groups_id': [Command.set([self.env.ref('base.group_user').id, self.env.ref('quality_control_oca.group_quality_control_manager').id])]})
        with TestCase.assertRaises(self, AccessError):
            inspection.with_user(actor).sudo().action_confirm()
        with TestCase.assertRaises(self, AccessError):
            inspection.with_user(actor).sudo().read(['state'])
        with TestCase.assertRaises(self, AccessError):
            inspection.inspection_lines.with_user(actor).sudo().read(['quantitative_value'])
        with TestCase.assertRaises(self, AccessError):
            inspection.inspection_lines.with_user(actor).sudo().write({'quantitative_value': 1})
        self.assertEqual(self._snapshot(inspection), before)

    def test_finalized_evidence_and_used_answers_keep_original_stored_results(self):
        inspection = self._inspection()
        inspection.action_todo()
        inspection.action_confirm()
        before = self._snapshot(inspection)
        for operation in (lambda: inspection.sudo().action_draft(), lambda: inspection.sudo().action_cancel(),
                lambda: inspection.inspection_lines.sudo().write({'quantitative_value': 2}),
                lambda: inspection.inspection_lines.sudo().unlink(), lambda: self.answer.write({'ok': False})):
            with TestCase.assertRaises(self, UserError):
                operation()
        inspection.invalidate_recordset(['success'])
        inspection.inspection_lines.invalidate_recordset(['success'])
        inspection._compute_success()
        inspection.inspection_lines._compute_quality_test_check()
        self.assertEqual(self._snapshot(inspection), before)

    def test_empty_test_prefilled_answers_and_wrong_question_cannot_be_certified(self):
        empty = self.scope['qc.test'].create({'name': 'Private empty test', 'company_id': self.company.id})
        inspection = self.scope['qc.inspection'].create({'test': empty.id, 'company_id': self.company.id})
        with TestCase.assertRaises(self, UserError):
            inspection.action_todo()
        actual = self._inspection()
        self.test.fill_correct_values = True
        with TestCase.assertRaisesRegex(self, UserError, 'prefilled'):
            actual.action_todo()
        self.test.fill_correct_values = False
        other = self.test.copy({'name': 'Private distinct test'})
        wrong = other.test_lines.filtered(lambda row: row.type == 'qualitative').ql_values.filtered('ok')
        actual.inspection_lines.filtered(lambda row: row.question_type == 'qualitative').qualitative_value = wrong
        with TestCase.assertRaisesRegex(self, UserError, 'exact original quality question'):
            actual.action_todo()

    def test_forged_results_and_nonfinite_limits_do_not_close_or_create_history(self):
        inspection = self._inspection()
        with TestCase.assertRaises(self, UserError):
            inspection.write({'success': True})
        with TestCase.assertRaises(self, UserError):
            inspection.inspection_lines.write({'success': True})
        line = inspection.inspection_lines.filtered(lambda row: row.question_type == 'quantitative')
        before = self._snapshot(inspection)
        with TestCase.assertRaisesRegex(self, UserError, 'finite'):
            line.write({'quantitative_value': float('inf')})
        self.assertEqual(self._snapshot(inspection), before)
