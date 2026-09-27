"""Fase 2, corte 3 — Presupuesto general (centros no agrícolas, formulario libre).

Verifica que el nuevo ``budget_type`` separa el flujo agrícola (plantilla por
hectárea) del general (líneas y montos a mano, sin hectáreas), sin regresión en
el flujo agrícola existente.
"""

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_management_costs import ManagementCostsCommon

_MONTHS = ["may", "jun", "jul", "aug", "sep", "oct", "nov", "dec",
           "jan", "feb", "mar", "apr"]


@tagged("post_install", "-at_install")
class TestFase2General(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.center_ops = cls.env["step.management.cost.center"].create({
            "code": "OPS01", "name": "Administración central",
            "company_id": cls.company_a.id, "cost_type": "administrative",
            "hectares": 0.0, "analytic_account_id": cls.aa_a.id,
        })

    def _general_budget(self, with_lines=True):
        vals = {
            "description": "Gastos generales 2026/27",
            "season": "2026/2027",
            "budget_type": "general",
            "company_id": self.company_a.id,
            "allocation_ids": [(0, 0, {
                "center_id": self.center_ops.id, "hectares": 0.0,
            })],
        }
        if with_lines:
            vals["line_ids"] = [(0, 0, {
                "center_id": self.center_ops.id, "group_id": self.group_a.id,
                "category": "service", "indicator": "Servicios contables",
                "quantity": 12.0, "unit_price": 500.0,
                "month_ids": [
                    (0, 0, {"month": m, "quantity": 1.0, "unit_price": 500.0})
                    for m in _MONTHS
                ],
            })]
        return self.env["step.management.operational.budget"].create(vals)

    # ------------------------------------------------------------------
    # General: se admite sin hectáreas
    # ------------------------------------------------------------------
    def test_general_budget_zero_hectares_and_totals(self):
        budget = self._general_budget()
        self.assertEqual(budget.origin_type, "manual")
        self.assertEqual(budget.total_hectares, 0.0)
        self.assertAlmostEqual(budget.total_amount, 6000.0)
        self.assertEqual(budget.cost_per_ha, 0.0)

    def test_general_line_without_hectares_is_valid(self):
        budget = self._general_budget()
        line = budget.line_ids
        self.assertFalse(line.hectares)
        self.assertTrue(line.distribution_complete)

    def test_general_budget_approval_and_freeze(self):
        budget = self._general_budget()
        budget.action_prepare_general()
        budget.with_user(self.user_approver).action_approve()
        self.assertEqual(budget.state, "approved")
        self.assertTrue(budget.approval_hash)
        with self.assertRaises(UserError):
            budget.write({"budget_type": "agricultural"})

    # ------------------------------------------------------------------
    # No hay atajos: sin plantilla / carga, y sin "calcular"
    # ------------------------------------------------------------------
    def test_generate_lines_blocked_on_general(self):
        budget = self._general_budget(with_lines=False)
        with self.assertRaises(UserError):
            budget.action_generate_lines()

    def test_general_cannot_carry_template(self):
        budget = self._general_budget()
        with self.assertRaises(ValidationError):
            budget.write({"template_id": self.template.id})

    # ------------------------------------------------------------------
    # No regresión del flujo agrícola
    # ------------------------------------------------------------------
    def test_agricultural_allocation_still_rejects_zero_hectares(self):
        budget = self._new_budget()
        with self.assertRaises(ValidationError):
            self.env["step.management.budget.center"].create({
                "budget_id": budget.id, "center_id": self.center_a2.id,
                "hectares": 0.0,
            })

    def test_agricultural_line_requires_hectares(self):
        budget = self._new_budget()
        with self.assertRaises(ValidationError):
            self.env["step.management.budget.line"].create({
                "budget_id": budget.id, "center_id": self.center_a.id,
                "group_id": self.group_a.id, "category": "labor",
                "indicator": "Sin hectáreas", "quantity": 1.0, "unit_price": 1.0,
            })

    def test_agricultural_flow_unchanged(self):
        budget = self._new_budget()
        budget.action_generate_lines()
        budget.with_user(self.user_approver).action_approve()
        self.assertEqual(budget.state, "approved")
        self.assertEqual(budget.budget_type, "agricultural")

    # ------------------------------------------------------------------
    # La comparación con el real funciona sobre un presupuesto general
    # ------------------------------------------------------------------
    def test_variance_wizard_runs_on_general_budget(self):
        budget = self._general_budget()
        budget.state = "calculated"
        budget.with_user(self.user_approver).action_approve()
        wizard = self.env["step.management.budget.variance.wizard"].create({
            "budget_id": budget.id,
            "date_from": "2026-05-01", "date_to": "2027-04-30",
        })
        wizard.action_compute()
        self.assertTrue(wizard.computed)
        self.assertAlmostEqual(wizard.total_budget_cost, 6000.0)
