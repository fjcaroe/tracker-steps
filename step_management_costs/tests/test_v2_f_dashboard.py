"""Corte V2 F — comparativos, tablero y clasificación fuera de OP.

Cubre: comparativo de temporada (temporada anterior inexistente, pesos/USD,
presupuesto cero, valores negativos/reversas, totales vs. porcentajes,
todas las dimensiones, dos compañías, permisos de consulta), clasificación
dentro/fuera de OP (sin doble conteo entre fuentes), y los dos bloques
nuevos del tablero (hectáreas por fundo/especie y por variedad).
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .test_management_costs import ManagementCostsCommon, extra_product_vals
from ..wizard.season_comparison import shift_season


@tagged("post_install", "-at_install")
class TestSeasonComparison(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.center_a.write({"farm": "Fundo Uno", "species": "Cerezo", "variety": "Bing"})

    def _cost(self, season, actual=0.0, budget=0.0, **kw):
        vals = {
            "name": "hecho", "company_id": self.company_a.id, "date": "2026-06-15",
            "center_id": self.center_a.id, "season": season,
            "actual_amount": actual, "budget_amount": budget,
            "farm": "Fundo Uno", "species": "Cerezo", "variety": "Bing",
            "center_label": "Centro A", "origin_label": "Externo",
            "budget_group_label": "Mano de obra", "activity_label": "Poda",
            "product_label": "Poda manual",
        }
        vals.update(kw)
        return self.env["step.management.historical.cost"].create(vals)

    def _wizard(self, **kw):
        vals = {
            "company_id": self.company_a.id, "season": "2026/2027",
            "previous_season": "2025/2026", "dimension": "center", "metric": "actual",
        }
        vals.update(kw)
        return self.env["step.management.season.comparison.wizard"].create(vals)

    def test_shift_season_helper(self):
        self.assertEqual(shift_season("2026/2027"), "2025/2026")
        self.assertEqual(shift_season("2026/2027", delta=1), "2027/2028")
        self.assertIsNone(shift_season("no es una temporada"))

    def test_previous_season_missing_shows_zero_no_baseline(self):
        self._cost("2026/2027", actual=1000.0)
        wiz = self._wizard()
        wiz.action_compute()
        line = wiz.line_ids
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.current_amount, 1000.0)
        self.assertAlmostEqual(line.previous_amount, 0.0)
        self.assertFalse(line.variance_percent_available)
        self.assertAlmostEqual(line.variance_percent, 0.0)  # nunca NaN/inf

    def test_pesos_and_usd(self):
        self._cost(
            "2026/2027", actual=100000.0, dataset_kind="actual",
            source_amount_usd=110.5,
        )
        wiz = self._wizard()
        wiz.action_compute()
        self.assertAlmostEqual(wiz.line_ids.current_amount, 100000.0)
        self.assertAlmostEqual(wiz.line_ids.current_amount_usd, 110.5)

    def test_budget_metric_zero(self):
        self._cost("2026/2027", actual=5000.0, budget=0.0)
        self._cost("2025/2026", actual=4000.0, budget=2000.0)
        wiz = self._wizard(metric="budget")
        wiz.action_compute()
        line = wiz.line_ids
        self.assertAlmostEqual(line.current_amount, 0.0)
        self.assertAlmostEqual(line.previous_amount, 2000.0)
        self.assertAlmostEqual(line.variance_percent, -100.0)

    def test_negative_reversal_values(self):
        self._cost("2026/2027", actual=1000.0)
        self._cost("2026/2027", actual=-400.0, name="reversa")
        wiz = self._wizard()
        wiz.action_compute()
        self.assertAlmostEqual(wiz.line_ids.current_amount, 600.0)

    def test_totals_from_totals_not_from_percent_sum(self):
        # Dos centros con temporada anterior distinta de cero: si se
        # promediaran los % de fila (100% y -50%), el total daría 25%; el
        # correcto (desde los totales: 1500 vs 1500) es 0%.
        center_b_center = self.env["step.management.cost.center"].create({
            "code": "SF01", "name": "Centro sin fundo", "company_id": self.company_a.id,
            "hectares": 3.0, "analytic_account_id": self.aa_a.id,
        })
        self._cost("2026/2027", actual=1000.0, center_id=self.center_a.id, center_label="Centro A")
        self._cost("2025/2026", actual=500.0, center_id=self.center_a.id, center_label="Centro A")
        self._cost("2026/2027", actual=500.0, center_id=center_b_center.id, center_label="Centro B")
        self._cost("2025/2026", actual=1000.0, center_id=center_b_center.id, center_label="Centro B")
        wiz = self._wizard()
        wiz.action_compute()
        self.assertEqual(len(wiz.line_ids), 2)
        self.assertAlmostEqual(wiz.total_current_amount, 1500.0)
        self.assertAlmostEqual(wiz.total_previous_amount, 1500.0)
        self.assertAlmostEqual(wiz.total_variance_percent, 0.0)

    def test_all_dimensions_selection(self):
        keys = [key for key, _label in self.env[
            "step.management.season.comparison.wizard"
        ]._fields["dimension"].selection]
        self.assertEqual(
            set(keys),
            {"farm", "species", "variety", "center", "origin", "budget_group", "activity", "product"},
        )
        self._cost("2026/2027", actual=100.0)
        for dimension in keys:
            wiz = self._wizard(dimension=dimension)
            wiz.action_compute()
            self.assertTrue(wiz.line_ids, "sin filas para la dimensión %s" % dimension)

    def test_unreviewed_origin_excluded(self):
        self._cost("2026/2027", actual=100.0, origin="unreviewed")
        wiz = self._wizard()
        wiz.action_compute()
        self.assertFalse(wiz.line_ids)

    def test_two_companies_isolated(self):
        self._cost("2026/2027", actual=1000.0)
        cost_b = self.env["step.management.historical.cost"].create({
            "name": "hecho B", "company_id": self.company_b.id, "date": "2026-06-15",
            "center_id": self.center_b.id, "season": "2026/2027", "actual_amount": 9999.0,
        })
        wiz = self._wizard(company_id=self.company_a.id)
        wiz.action_compute()
        self.assertAlmostEqual(wiz.total_current_amount, 1000.0)
        wiz_b = self._wizard(company_id=self.company_b.id)
        wiz_b.action_compute()
        self.assertAlmostEqual(wiz_b.total_current_amount, 9999.0)

    def test_readonly_group_can_compute(self):
        self._cost("2026/2027", actual=1000.0)
        wiz = self._wizard().with_user(self.user_readonly)
        wiz.action_compute()
        self.assertTrue(wiz.line_ids)

    def test_same_season_rejected(self):
        from odoo.exceptions import ValidationError
        wiz = self._wizard(previous_season="2026/2027")
        with self.assertRaises(ValidationError):
            wiz.action_compute()


@tagged("post_install", "-at_install")
class TestOutOfOp(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(dict({
            "name": "Servicio fuera de OP", "type": "service",
        }, **extra_product_vals(cls.env)))
        cls.product.categ_id.management_budget_group_id = cls.group_a.id
        cls.vendor = cls.env["res.partner"].create({"name": "Proveedor V2F"})
        # `center_a2` comparte la cuenta analítica de `center_a` (fixture
        # compartida del núcleo, a propósito para otros tests de esa
        # ambigüedad). El clasificador ahora la detecta y la rechaza
        # (`cost_center.py::account_to_center_map`, mismo criterio que
        # `_duplicate_analytic_centers` del núcleo) — correcto para
        # cualquier lectura real de gasto, pero rompería estos tests si
        # `center_a2` quedara activa sin que a ellos les importe. Se
        # desactiva sólo en esta clase (no toca el fixture compartido).
        cls.center_a2.active = False
        aa_other = cls.env["account.analytic.account"].create(dict({
            "name": "AA Centro sin OP", "plan_id": cls.plan.id, "company_id": cls.company_a.id,
        }, **cls._extra_analytic_account_vals(cls.company_a)))
        cls.center_no_op = cls.env["step.management.cost.center"].create({
            "code": "NOP01", "name": "Centro sin OP", "company_id": cls.company_a.id,
            "hectares": 2.0, "analytic_account_id": aa_other.id,
        })

    def _bill(self, amount, center=None, date="2026-06-15", post=True):
        center = center or self.center_a
        move = self.env["account.move"].create({
            "move_type": "in_invoice", "partner_id": self.vendor.id,
            "invoice_date": date, "date": date, "company_id": center.company_id.id,
            "invoice_line_ids": [(0, 0, {
                "product_id": self.product.id, "quantity": 1, "price_unit": amount,
                "analytic_distribution": {str(center.analytic_account_id.id): 100.0},
            })],
        })
        if post:
            move.action_post()
        return move

    def _wizard(self, **kw):
        vals = {
            "company_id": self.company_a.id,
            "date_from": "2026-05-01", "date_to": "2027-04-30",
        }
        vals.update(kw)
        return self.env["step.management.out.of.op.wizard"].create(vals)

    def _authorized_order(self, center=None):
        """OP real y autorizada (presupuesto → plan → tareas semanales →
        vista previa → confirmar → autorizar), con `budget_group_id =
        self.group_a` heredado de `self.template` — mismo patrón que
        `test_fase7_corte2_production_order.py`."""
        center = center or self.center_a
        budget = self._new_budget(template=self.template, centers=[center])
        budget.action_generate_lines()
        budget.with_user(self.user_approver).action_approve()
        plan = self.env["step.management.plan"].create({
            "description": "Plan V2F", "company_id": self.company_a.id,
            "date_start": "2026-05-01", "date_end": "2027-04-30", "budget_id": budget.id,
        })
        plan.action_generate_weekly_tasks()
        self.env["step.management.plan.weekly.preview.wizard"].with_context(
            default_plan_id=plan.id
        ).create({}).action_confirm()
        line = plan.line_ids.filtered(lambda l: l.generated and l.center_id == center)[:1]
        self.assertTrue(line, "el plan no generó tareas semanales para el centro")
        order = self.env["step.management.production.order"].create({
            "company_id": self.company_a.id, "season": "2026/2027",
            "iso_year": line.iso_year, "iso_week": line.iso_week,
            "center_id": center.id,
        })
        order.action_generate_preview()
        self.env["step.management.production.order.preview.wizard"].with_context(
            default_order_id=order.id
        ).create({}).action_confirm()
        order.with_user(self.user_approver).action_authorize()
        self.assertIn(self.group_a, order.line_ids.mapped("budget_group_id"))
        return order

    def test_expense_without_op_is_out_of_op(self):
        self._bill(10000.0)
        wiz = self._wizard()
        wiz.action_compute()
        self.assertEqual(len(wiz.line_ids), 1)
        line = wiz.line_ids
        self.assertFalse(line.backed_by_op)
        self.assertAlmostEqual(wiz.total_out_of_op, 10000.0)
        self.assertAlmostEqual(wiz.total_in_op, 0.0)
        self.assertIn("derivado", line.source_label)
        self.assertIn("W", line.source_label)

    def test_expense_backed_by_op_is_classified_in_op(self):
        order = self._authorized_order()
        self._bill(5000.0)
        wiz = self._wizard()
        wiz.action_compute()
        line = wiz.line_ids
        self.assertTrue(line.backed_by_op)
        self.assertIn(order.name, line.op_names)
        self.assertAlmostEqual(wiz.total_in_op, 5000.0)
        self.assertAlmostEqual(wiz.total_out_of_op, 0.0)

    def test_only_out_of_op_filter(self):
        self._authorized_order()
        self._bill(5000.0)  # amparado
        self._bill(3000.0, center=self.center_no_op)  # no amparado
        wiz = self._wizard(only_out_of_op=True)
        wiz.action_compute()
        self.assertEqual(len(wiz.line_ids), 1)
        self.assertFalse(wiz.line_ids.backed_by_op)

    def test_shared_analytic_account_raises(self):
        self.center_a2.active = True  # reactivada sólo para este test
        self._bill(1000.0)
        wiz = self._wizard()
        with self.assertRaises(UserError):
            wiz.action_compute()

    def test_draft_bill_not_counted(self):
        self._bill(1000.0, post=False)
        wiz = self._wizard()
        wiz.action_compute()
        self.assertFalse(wiz.line_ids)

    def test_no_double_counting_single_source(self):
        # El clasificador lee únicamente `account.move.line` publicado; un
        # hecho histórico normalizado (V2 B) de la misma temporada no
        # aparece aquí — evita sumar la misma plata dos veces por dos
        # caminos distintos.
        self.env["step.management.historical.cost"].create({
            "name": "hecho histórico", "company_id": self.company_a.id,
            "date": "2026-06-15", "center_id": self.center_a.id,
            "season": "2026/2027", "actual_amount": 777777.0,
        })
        self._bill(1000.0)
        wiz = self._wizard()
        wiz.action_compute()
        self.assertAlmostEqual(sum(wiz.line_ids.mapped("amount")), 1000.0)


@tagged("post_install", "-at_install")
class TestDashboardExtension(ManagementCostsCommon):
    def test_hectares_by_farm_species_and_variety(self):
        self.center_a.write({"farm": "Fundo Uno", "species": "Cerezo", "variety": "Bing"})
        self.center_a2.write({"farm": "Fundo Uno", "species": "Cerezo", "variety": "Lapins"})
        data = self.env["step.management.operational.budget"].with_company(
            self.company_a
        ).get_management_dashboard()
        farm_species = {(row["farm"], row["species"]): row["hectares"] for row in data["hectares_by_farm_species"]}
        self.assertAlmostEqual(farm_species[("Fundo Uno", "Cerezo")], 15.0)  # 10 + 5
        variety = {row["variety"]: row["hectares"] for row in data["hectares_by_variety"]}
        self.assertAlmostEqual(variety["Bing"], 10.0)
        self.assertAlmostEqual(variety["Lapins"], 5.0)
        self.assertIn("stock", data)
        self.assertEqual(data["stock"]["line_count"], 0)
        self.assertAlmostEqual(data["stock"]["needs"], 0.0)

    def test_costs_block_variance_percent_zero_safe(self):
        # Prueba unitaria directa sobre el helper (no sobre
        # `get_management_dashboard()` completo): ese método busca en toda
        # la compañía sin acotar a datos de esta prueba, así que en un
        # entorno con historia real (upgrade de `LAB_TAREAS`) ya habría
        # presupuesto/real distinto de cero para «la compañía principal» —
        # el helper zero-safe es lo que realmente hay que verificar aquí.
        Model = self.env["step.management.operational.budget"]
        empty = Model._dashboard_costs_block([], [])
        self.assertAlmostEqual(empty["variance_percent"], 0.0)
        self.assertFalse(empty["budget_available"])
        with_budget = Model._dashboard_costs_block(
            [{"amount": 1200.0, "available": True}], [{"amount": 1000.0, "available": True}],
        )
        self.assertAlmostEqual(with_budget["variance_percent"], 20.0)
        self.assertTrue(with_budget["budget_available"])
