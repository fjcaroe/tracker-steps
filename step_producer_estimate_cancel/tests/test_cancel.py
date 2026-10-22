from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests.common import TransactionCase, new_test_user
from odoo.addons.step_producer_estimate_report.tests import test_report as fixtures


class CancellationCase(TransactionCase):
    def sample(self):
        return fixtures.EstimateReportCase.sample(self)[0]

    def test_cancel_current_preserves_history_and_report(self):
        estimate = self.sample()
        estimate.action_validate_estimate()
        estimate.action_activate_estimate()
        lines = estimate.estimate_line_ids
        weeks = lines.week_line_ids
        quantities = weeks.mapped('export_kg')
        estimate.action_cancel_estimate()
        self.env.flush_all()
        self.assertEqual(estimate.state, 'cancelled')
        self.assertEqual(estimate.estimate_cancelled_by_id, self.env.user)
        self.assertTrue(estimate.estimate_cancelled_at)
        self.assertEqual(estimate.estimate_line_ids, lines)
        self.assertEqual(lines.week_line_ids, weeks)
        self.assertEqual(weeks.mapped('export_kg'), quantities)
        rows = self.env['step.producer.estimate.report'].search([('estimate_id', '=', estimate.id)])
        self.assertEqual(len(rows), 2)
        self.assertEqual(set(rows.mapped('state')), {'cancelled'})
        self.assertFalse(rows.filtered(lambda row: row.state == 'current'))
        audit = (estimate.estimate_cancelled_at, estimate.estimate_cancelled_by_id)
        estimate.action_cancel_estimate()
        self.assertEqual((estimate.estimate_cancelled_at, estimate.estimate_cancelled_by_id), audit)

    def test_cancel_draft_and_validated_and_duplicate(self):
        for validate in (False, True):
            estimate = self.sample()
            if validate:
                estimate.action_validate_estimate()
            estimate.action_cancel_estimate()
            duplicate = estimate.copy()
            self.assertEqual(duplicate.state, 'created')
            self.assertFalse(duplicate.estimate_cancelled_at)
            self.assertFalse(duplicate.estimate_cancelled_by_id)
            self.assertNotEqual(duplicate.series_code, estimate.series_code)
            self.assertEqual(duplicate.estimate_line_ids.export_kg, estimate.estimate_line_ids.export_kg)
            self.assertEqual(duplicate.estimate_line_ids.week_line_ids.mapped('export_kg'),
                             estimate.estimate_line_ids.week_line_ids.mapped('export_kg'))

    def test_cannot_reactivate_or_mutate_cancelled_history(self):
        estimate = self.sample()
        estimate.action_cancel_estimate()
        line = estimate.estimate_line_ids
        week = line.week_line_ids[0]
        for action in [lambda: estimate.write({'name': 'changed'}),
                       lambda: estimate.write({'state': 'current'}), estimate.unlink,
                       estimate.action_validate_estimate, estimate.action_activate_estimate,
                       estimate.action_new_estimate_version,
                       lambda: line.write({'step_delivery_closed': True}),
                       lambda: line.write({'export_kg': 12}), line.unlink,
                       lambda: week.write({'export_kg': 12}), week.unlink,
                       lambda: line.copy({'estimate_id': estimate.id}),
                       lambda: week.copy({'line_id': line.id})]:
            with self.assertRaises(UserError), self.cr.savepoint():
                action()

    def test_replaced_version_is_not_revived_and_rpc_cannot_forge_audit(self):
        estimate = self.sample()
        estimate.action_validate_estimate()
        estimate.action_activate_estimate()
        current = self.env['step.export.estimate'].browse(estimate.action_new_estimate_version()['res_id'])
        current.action_validate_estimate()
        current.action_activate_estimate()
        current.action_cancel_estimate()
        self.assertEqual(estimate.state, 'replaced')
        with self.assertRaises(UserError):
            estimate.action_cancel_estimate()
        with self.assertRaises(UserError):
            estimate.with_context(_estimate_cancellation=True).write({'state': 'cancelled'})
        with self.assertRaises(UserError):
            self.env['step.export.estimate'].create({'name': 'forged', 'state': 'cancelled'})

    def test_cannot_move_lines_or_weeks_into_cancelled_estimate(self):
        cancelled = self.sample()
        draft = self.sample()
        cancelled.action_cancel_estimate()
        with self.assertRaises(UserError):
            draft.estimate_line_ids.write({'estimate_id': cancelled.id})
        with self.assertRaises(UserError):
            draft.estimate_line_ids.week_line_ids[0].write({'line_id': cancelled.estimate_line_ids.id})

    def test_company_access_is_preserved(self):
        estimate = self.sample()
        other = self.env['res.company'].create({'name': 'QA cancellation other'})
        user = new_test_user(self.env(context=dict(self.env.context, no_reset_password=True)), login='qa-cancel-other', groups='base.group_user',
                             company_id=other.id, company_ids=[Command.set(other.ids)])
        with self.assertRaises(AccessError):
            estimate.with_user(user).with_context(allowed_company_ids=other.ids).action_cancel_estimate()
        self.assertEqual(estimate.state, 'created')
