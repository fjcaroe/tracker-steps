"""Fase 2, corte 4 — integrity and auditability regressions."""

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_management_costs import ManagementCostsCommon


@tagged("post_install", "-at_install")
class TestFase2Hardening(ManagementCostsCommon):

    def _general_direct_budget(self):
        center = self.env["step.management.cost.center"].create({
            "code": "GD01", "name": "General directo",
            "company_id": self.company_a.id, "cost_type": "administrative",
            "analytic_account_id": self.env["account.analytic.account"].create(dict({
                "name": "AA General directo", "plan_id": self.plan.id,
                "company_id": self.company_a.id,
            }, **self._extra_analytic_account_vals(self.company_a))).id,
        })
        return self.env["step.management.operational.budget"].create({
            "description": "General monto directo", "season": "2026/2027",
            "budget_type": "general", "company_id": self.company_a.id,
            "allocation_ids": [(0, 0, {"center_id": center.id, "hectares": 0.0})],
            "line_ids": [(0, 0, {
                "center_id": center.id, "group_id": self.group_a.id,
                "category": "service", "indicator": "Honorarios",
                "calculation_mode": "direct", "direct_amount": 120000.0,
                "month_ids": [
                    (0, 0, {"month": "may", "direct_amount": 50000.0}),
                    (0, 0, {"month": "jun", "direct_amount": 70000.0}),
                ],
            })],
        })

    def test_general_direct_amount_can_be_validated_and_approved(self):
        budget = self._general_direct_budget()
        self.assertAlmostEqual(budget.total_amount, 120000.0)
        self.assertAlmostEqual(budget.line_ids.monthly_amount, 120000.0)
        self.assertTrue(budget.line_ids.distribution_complete)
        budget.action_prepare_general()
        budget.with_user(self.user_approver).action_approve()
        self.assertEqual(budget.state, "approved")

    def test_monthly_amount_must_reconcile_even_when_quantity_does(self):
        budget = self._general_direct_budget()
        with self.assertRaises(ValidationError):
            budget.line_ids.month_ids[0].write({"direct_amount": 40000.0})

    def test_direct_amount_is_for_general_budget_only(self):
        budget = self._new_budget()
        with self.assertRaises(ValidationError):
            self.env["step.management.budget.line"].create({
                "budget_id": budget.id, "center_id": self.center_a.id,
                "group_id": self.group_a.id, "category": "labor",
                "indicator": "Directo inválido", "hectares": 10.0,
                "calculation_mode": "direct", "direct_amount": 100.0,
            })

    def test_forgeable_context_cannot_bypass_frozen_budget(self):
        budget = self._new_budget()
        budget.action_generate_lines()
        budget.with_user(self.user_approver).action_approve()
        with self.assertRaises(UserError):
            budget.with_context(mc_reopen=True).write({"description": "alterado"})
        with self.assertRaises(UserError):
            budget.line_ids.with_context(mc_reopen=True).write({"quantity": 1.0})
        with self.assertRaises(UserError):
            budget.line_ids.month_ids.with_context(mc_reopen=True).write({"quantity": 1.0})

    def test_general_revision_copies_detail_without_mutating_approved(self):
        budget = self._general_direct_budget()
        budget.action_prepare_general()
        budget.with_user(self.user_approver).action_approve()
        revision = budget.with_user(self.user_approver)._do_reopen("Corregir monto")
        self.assertEqual(budget.state, "approved")
        self.assertEqual(revision.state, "draft")
        self.assertEqual(revision.budget_type, "general")
        self.assertEqual(len(revision.line_ids), 1)
        self.assertAlmostEqual(revision.line_ids.direct_amount, 120000.0)
        self.assertEqual(len(revision.line_ids.month_ids), 2)

    def test_second_active_successor_is_blocked(self):
        budget = self._general_direct_budget()
        budget.action_prepare_general()
        budget.with_user(self.user_approver).action_approve()
        budget.with_user(self.user_approver).action_new_revision()
        with self.assertRaises(UserError):
            budget.with_user(self.user_approver).action_new_revision()

    def test_shared_analytic_account_blocks_approval(self):
        budget = self._new_budget(centers=[self.center_a, self.center_a2])
        budget.action_generate_lines()
        with self.assertRaises(UserError):
            budget.with_user(self.user_approver).action_approve()

    def test_line_center_must_be_in_allocations(self):
        budget = self._general_direct_budget()
        budget.line_ids.center_id = self.center_a
        with self.assertRaises(UserError):
            budget.action_prepare_general()

    def test_month_has_database_uniqueness(self):
        budget = self._general_direct_budget()
        line = budget.line_ids
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["step.management.budget.month"].create({
                    "budget_line_id": line.id,
                    "month": "may",
                    "direct_amount": 1.0,
                })
