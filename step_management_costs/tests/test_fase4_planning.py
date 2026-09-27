from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .test_management_costs import ManagementCostsCommon


@tagged("post_install", "-at_install")
class TestFase4Planning(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env["step.management.estimation.unit"].create({
            "name": "Bin", "code": "BIN4", "kg_factor": 400.0,
            "company_id": cls.company_a.id,
        })
        cls.version = cls.env["step.management.estimation.version"].create({
            "code": "V4", "name": "Estimación 2026/2027", "season": "2026/2027",
            "company_id": cls.company_a.id,
        })
        cat = cls.env["step.management.fruit.category"].create({
            "name": "Exportación", "code": "EXP4", "company_id": cls.company_a.id,
        })
        fc = cls.env["step.management.fruit.class"].create({
            "name": "Export", "code": "E4", "category_id": cat.id,
            "company_id": cls.company_a.id,
        })
        cg = cls.env["step.management.caliber.group"].create({
            "name": "Jumbo", "code": "J4", "company_id": cls.company_a.id,
        })
        cls.week_curve = cls._mk_curve("week", "W4", [
            {"week_number": 48, "percentage": 40.0},
            {"week_number": 52, "percentage": 60.0},  # > W50 → C3
        ])
        cls.cal_curve = cls._mk_curve("caliber", "C4", [
            {"caliber_group_id": cg.id, "percentage": 100.0},
        ])
        cls.cls_curve = cls._mk_curve("class", "L4", [
            {"fruit_class_id": fc.id, "percentage": 100.0},
        ])
        cls.center_a.write({"plants": 1000.0})
        est = cls.env["step.management.estimation"].create({
            "version_id": cls.version.id, "season": "2026/2027",
            "company_id": cls.company_a.id, "unit_id": cls.unit.id,
            "method": "plants", "default_yield_ue": 1.0,
            "week_curve_id": cls.week_curve.id,
            "caliber_curve_id": cls.cal_curve.id,
            "class_curve_id": cls.cls_curve.id,
            "center_ids": [(6, 0, [cls.center_a.id])],
        })
        est.action_compute_lines()
        est.action_validate()
        cls.estimation = est  # total_kg = 1000 * 1 * 400 = 400000

    @classmethod
    def _mk_curve(cls, curve_type, code, lines):
        curve = cls.env["step.management.estimation.curve"].create({
            "name": "Curva %s" % code, "code": code, "curve_type": curve_type,
            "company_id": cls.company_a.id,
            "line_ids": [(0, 0, v) for v in lines],
        })
        curve.action_validate()
        return curve

    def _period(self):
        return self.env["step.management.period.service"]

    def _approved_budget(self):
        budget = self._new_budget()
        budget.action_generate_lines()
        budget.with_user(self.user_approver).action_approve()
        return budget

    def _generate_weekly_tasks(self, plan, user=None):
        """Simula el flujo completo (Corte 1 post Fase 6): abrir la vista
        previa y confirmarla — `action_generate_weekly_tasks` ya no escribe
        directamente."""
        target = plan.with_user(user) if user else plan
        target.action_generate_weekly_tasks()
        wizard_model = self.env["step.management.plan.weekly.preview.wizard"]
        if user:
            wizard_model = wizard_model.with_user(user)
        wizard = wizard_model.with_context(default_plan_id=plan.id).create({})
        wizard.action_confirm()
        return wizard

    def _plan(self, budget=None, user=None, **kw):
        model = self.env["step.management.plan"]
        if user:
            model = model.with_user(user)
        vals = {
            "description": "Plan semanal", "company_id": self.company_a.id,
            "date_start": "2026-05-01", "date_end": "2027-04-30",
        }
        if budget:
            vals["budget_id"] = budget.id
        vals.update(kw)
        return model.create(vals)

    # ------------------------------------------------------------------
    # period_service
    # ------------------------------------------------------------------
    def test_season_bounds_may_to_april(self):
        start, end = self._period().season_bounds("2026/2027")
        self.assertEqual(str(start), "2026-05-01")
        self.assertEqual(str(end), "2027-04-30")

    def test_iso_weeks_support_w53(self):
        weeks = self._period().iso_weeks("2026-12-01", "2027-01-15")
        self.assertIn("W53", [w["label"] for w in weeks])
        self.assertTrue(all(1 <= w["days_in_range"] <= 7 for w in weeks))

    def test_distribute_single_month_reconciles_all_weeks(self):
        weeks = self._period().distribute_monthly_to_weeks(
            "2026/2027", {"jun": 120.0}, rounding=0.01,
        )
        self.assertAlmostEqual(sum(w["quantity"] for w in weeks), 120.0, places=2)
        self.assertGreater(len(weeks), 50)  # C3: todas las semanas de la temporada
        with_qty = [w for w in weeks if w["quantity"]]
        # la última semana (cruce jun/jul) recibe menos que una semana completa
        self.assertLess(with_qty[-1]["quantity"], with_qty[0]["quantity"])

    def test_distribute_cross_year_months(self):
        weeks = self._period().distribute_monthly_to_weeks(
            "2026/2027", {"dec": 100.0, "jan": 50.0}, rounding=0.01,
        )
        self.assertAlmostEqual(sum(w["quantity"] for w in weeks), 150.0, places=2)

    # ------------------------------------------------------------------
    # Tareas semanales desde el presupuesto aprobado
    # ------------------------------------------------------------------
    def test_weekly_tasks_reconcile_with_budget(self):
        budget = self._approved_budget()
        expected = sum(budget.line_ids.month_ids.mapped("quantity"))
        plan = self._plan(budget=budget)
        self._generate_weekly_tasks(plan)
        gen = plan.line_ids.filtered("generated")
        self.assertTrue(gen)
        self.assertEqual(plan.source_type, "budget")
        self.assertAlmostEqual(sum(gen.mapped("quantity")), expected, places=2)
        self.assertTrue(all(gen.mapped("week_label")))

    def test_weekly_tasks_idempotent(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        self._generate_weekly_tasks(plan)
        n = len(plan.line_ids.filtered("generated"))
        total = sum(plan.line_ids.filtered("generated").mapped("quantity"))
        self._generate_weekly_tasks(plan)
        gen = plan.line_ids.filtered("generated")
        self.assertEqual(len(gen), n)
        self.assertAlmostEqual(sum(gen.mapped("quantity")), total, places=2)

    def test_weekly_tasks_preserve_manual_lines(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        self._generate_weekly_tasks(plan)
        plan.write({"line_ids": [(0, 0, {
            "date": "2026-06-01", "indicator": "Tarea manual",
            "center_id": self.center_a.id,
        })]})
        self.assertEqual(len(plan.line_ids.filtered(lambda l: not l.generated)), 1)
        self._generate_weekly_tasks(plan)
        self.assertEqual(len(plan.line_ids.filtered(lambda l: not l.generated)), 1)

    def test_weekly_tasks_require_approved_budget(self):
        budget = self._new_budget()
        budget.action_generate_lines()  # calculated, no aprobado
        plan = self._plan(budget=budget)
        with self.assertRaises(UserError):
            self._generate_weekly_tasks(plan)

    def test_weekly_tasks_without_budget_raises(self):
        plan = self._plan()
        with self.assertRaises(UserError):
            self._generate_weekly_tasks(plan)

    def test_weekly_tasks_roles(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget, user=self.user_operator)
        self._generate_weekly_tasks(plan, user=self.user_operator)
        self.assertTrue(plan.line_ids.filtered("generated"))
        with self.assertRaises(AccessError):
            self._plan(budget=budget, user=self.user_readonly)

    def test_weekly_tasks_cross_company_budget_rejected(self):
        template_b = self.env["step.management.budget.template"].create({
            "name": "PB", "company_id": self.company_b.id,
            "base_hectares": 1.0, "state": "active",
        })
        budget_b = self.env["step.management.operational.budget"].create({
            "description": "B", "season": "2026/2027",
            "company_id": self.company_b.id, "template_id": template_b.id,
        })
        with self.assertRaises(UserError):
            self._plan(budget=budget_b)

    # ------------------------------------------------------------------
    # Plan de cosecha desde la estimación validada
    # ------------------------------------------------------------------
    def _harvest(self, **kw):
        vals = {"company_id": self.company_a.id, "estimation_id": self.estimation.id}
        vals.update(kw)
        return self.env["step.management.harvest.plan"].create(vals)

    def test_harvest_plan_reconciles_and_keeps_late_weeks(self):
        hp = self._harvest()
        hp.action_generate()
        self.assertAlmostEqual(hp.total_kg, self.estimation.total_kg, places=2)
        by_week = {l.week_number: l.kg for l in hp.line_ids}
        self.assertIn(52, by_week)  # C3: semana > W50 no se pierde
        self.assertAlmostEqual(by_week[48], 160000.0, places=2)
        self.assertAlmostEqual(by_week[52], 240000.0, places=2)
        l48 = hp.line_ids.filtered(lambda l: l.week_number == 48)
        self.assertAlmostEqual(l48.containers, 400.0)  # ceil(160000/400)

    def test_harvest_containers_exact_when_round_up_off(self):
        hp = self._harvest(round_up_containers=False)
        hp.action_generate()
        for line in hp.line_ids:
            self.assertAlmostEqual(line.containers, line.kg / 400.0, places=4)

    def test_harvest_requires_validated_estimation(self):
        est_draft = self.env["step.management.estimation"].create({
            "version_id": self.version.id, "season": "2026/2027",
            "company_id": self.company_a.id, "unit_id": self.unit.id,
            "method": "kilos",
        })
        hp = self._harvest(estimation_id=est_draft.id)
        with self.assertRaises(UserError):
            hp.action_generate()

    def test_harvest_immutable_after_confirm(self):
        hp = self._harvest()
        hp.action_generate()
        hp.action_confirm()
        self.assertEqual(hp.state, "confirmed")
        with self.assertRaises(UserError):
            hp.write({"round_up_containers": False})
        with self.assertRaises(UserError):
            hp.line_ids[0].write({"kg": 1.0})
        with self.assertRaises(UserError):
            hp.line_ids[0].unlink()
        with self.assertRaises(UserError):
            hp.unlink()
        hp.action_reset_to_draft()
        self.assertEqual(hp.state, "draft")

    def test_harvest_cross_company_unit_rejected(self):
        unit_b = self.env["step.management.estimation.unit"].create({
            "name": "UB", "code": "UB4", "kg_factor": 1.0,
            "company_id": self.company_b.id,
        })
        with self.assertRaises(UserError):
            self._harvest(container_unit_id=unit_b.id)
