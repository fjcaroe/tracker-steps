from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


def dashboard_sample(env):
    """A mixed, native budget: operation, investment and growth, two species."""
    env = env(context=dict(env.context, tracking_disable=True, mail_create_nosubscribe=True, no_reset_password=True))
    company = env.company
    season = env["step.temporada"].create({
        "name": "QA T228 Temporada", "company_id": company.id,
        "start_date": "2026-09-01", "end_date": "2027-08-31",
    })
    other_season = env["step.temporada"].create({"name": "QA T228 Otra temporada", "company_id": company.id})
    species = env["step.especie"].create([
        {"name": "QA T228 A", "company_id": company.id, "type_especie": "frutal", "group_especie": "baya"},
        {"name": "QA T228 B", "company_id": company.id, "type_especie": "frutal", "group_especie": "baya"},
    ])
    plan = env["account.analytic.plan"].create({"name": "QA T228 Centros"})
    centers = env["account.analytic.account"].create([
        {"name": "QA T228 " + name, "company_id": company.id, "plan_id": plan.id,
         "type_costo": "fruta", "etapa_costo": stage, "especie_id": spec.id, "hectares": ha}
        for name, stage, spec, ha in (
            ("Operación A", "ope", species[0], 2), ("Inversión A", "inver", species[0], 1),
            ("Crecimiento B", "cre", species[1], 3), ("Operación B", "ope", species[1], 4),
        )
    ])
    activity_plan = env["account.analytic.plan"].search([("name", "=", "Actividad")], limit=1)
    activity_plan = activity_plan or env["account.analytic.plan"].create({"name": "Actividad"})
    activities = env["account.analytic.account"].create([
        {"name": name, "company_id": company.id, "plan_id": activity_plan.id}
        for name in ("Cosechar", "Mantener")
    ])
    groups = env["step.management.budget.group"].create([
        {"name": "QA T228 " + name, "code": "QA228-%s-%s" % (season.id, flow), "flow_type": flow,
         "company_id": company.id, "origin_id": env.ref("step_budget_design.origin_income" if flow == "income" else "step_budget_design.origin_labor").id}
        for name, flow in (("Costos", "cost"), ("Ingresos", "income"))
    ])
    lines = []
    for index, harvest, maintenance, income in ((0, 300, 200, 1000), (1, 50, 150, 400), (2, 0, 100, 0), (3, 100, 50, 500)):
        for amount, activity, group in ((harvest, activities[0], groups[0]), (maintenance, activities[1], groups[0]), (income, activities[1], groups[1])):
            if amount:
                lines.append(Command.create({"center_id": centers[index].id, "group_id": group.id,
                    "activity_id": activity.id, "category": group.origin_id.category, "indicator": "QA T228 línea",
                    "calculation_mode": "direct", "direct_amount": amount}))
    budget = env["step.management.operational.budget"].create({
        "description": "QA T228 presupuesto mixto", "company_id": company.id,
        "budget_type": "general", "season_id": season.id, "date": "2026-11-01",
        "currency_id": env.ref("base.CLP").id,
        "allocation_ids": [Command.create({"center_id": center.id, "hectares": center.hectares}) for center in centers],
        "line_ids": lines,
    })
    version = env["step.management.estimation.version"].create({
        "name": "QA T228 versión", "code": "QA228-%s" % season.id, "season_id": season.id,
    })
    unit = env["step.management.estimation.unit"].create({"name": "QA T228 kg", "code": "QA228-%s" % season.id, "kg_factor": 1})
    estimate = env["step.management.estimation"].create({
        "company_id": company.id, "version_id": version.id, "season_id": season.id,
        "unit_id": unit.id, "method": "kilos", "center_ids": [Command.set(centers.ids)],
        "line_ids": [Command.create({"center_id": center.id, "total_kg_input": kg})
                     for center, kg in zip(centers, (1000, 200, 300, 500))],
    })
    category = env["step.management.fruit.category"].create({"name": "QA T228 fruta", "code": "QA228-%s" % season.id})
    fruit_class = env["step.management.fruit.class"].create({"name": "QA T228 clase", "code": "QA228-%s" % season.id, "category_id": category.id})
    caliber = env["step.management.caliber.group"].create({"name": "QA T228 calibre", "code": "QA228-%s" % season.id})
    for axis, dimension in {"week": {"week_number": 10}, "caliber": {"caliber_group_id": caliber.id}, "class": {"fruit_class_id": fruit_class.id}}.items():
        curve = env["step.management.estimation.curve"].create({
            "name": "QA T228 " + axis, "code": "QA228-%s-%s" % (season.id, axis),
            "curve_type": axis, "line_ids": [Command.create(dict(dimension, percentage=100))],
        })
        curve.action_validate()
        estimate[axis + "_curve_id"] = curve
    return {"budget": budget, "estimate": estimate, "season": season, "other_season": other_season,
            "species": species, "centers": centers, "groups": groups, "activities": activities}


@tagged("post_install", "-at_install")
class DashboardCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        company = cls.env["res.company"].create({"name": "QA T228 empresa", "currency_id": cls.env.ref("base.CLP").id})
        cls.env = cls.env["res.company"].with_company(company).with_context(allowed_company_ids=company.ids).env
        cls.sample = dashboard_sample(cls.env)
        cls.budget = cls.sample["budget"]
        cls.estimate = cls.sample["estimate"]
        cls.user = new_test_user(cls.env, login="qa-t228-planner", company_id=company.id,
            company_ids=[Command.set(company.ids)], groups="step_management_costs.group_management_manager")

    def panel(self, **filters):
        return self.budget.with_user(self.user).get_management_dashboard(
            season_id=self.sample["season"].id, **filters)

    def test_investment_growth_nature_and_harvest_columns(self):
        data = self.panel()
        self.assertEqual(data["budgets"]["amount"], 650)
        self.assertEqual(data["budgets"]["investment"], 300)
        self.assertEqual([(row["income"], row["cost"], row["result"]) for row in data["projected"]], [(1000, 500, 500), (500, 150, 350)])
        row = data["recent"][0]
        self.assertEqual((row["harvest"], row["maintenance"], row["amount"], row["hectares"], row["cost_per_ha"]), (450, 500, 950, 10, 95))
        self.assertIsNone(row["estimated_kg"])
        self.assertIsNone(row["cost_per_kg"])

    def test_species_and_season_filters_use_native_masters(self):
        data = self.panel(species_id=self.sample["species"][0].id)
        self.assertEqual(data["budgets"]["amount"], 500)
        self.assertEqual(data["budgets"]["investment"], 200)
        row = data["recent"][0]
        self.assertEqual((row["harvest"], row["maintenance"], row["amount"], row["hectares"]), (350, 350, 700, 3))
        self.assertEqual(len(data["projected"]), 1)
        empty = self.budget.with_user(self.user).get_management_dashboard(season_id=self.sample["other_season"].id)
        self.assertEqual(empty["budgets"]["total"], 0)
        self.assertFalse(empty["recent"])
        self.assertFalse(empty["projected"])

    def test_current_validated_estimation_and_no_duplicate_revisions(self):
        estimate = self.estimate.with_user(self.user)
        estimate.action_validate()
        row = self.panel()["recent"][0]
        self.assertEqual(row["estimated_kg"], estimate.total_kg)
        self.assertEqual(row["estimated_kg"], 2000)
        self.assertAlmostEqual(row["cost_per_kg"], .475)
        revision = estimate.browse(estimate.action_new_revision()["res_id"])
        revision.line_ids[0].total_kg_input += 1000
        self.assertEqual(self.panel()["recent"][0]["estimated_kg"], 2000)
        revision.action_validate()
        row = self.panel()["recent"][0]
        self.assertEqual(row["estimated_kg"], 3000)
        self.assertEqual(estimate.state, "superseded")
        filtered = self.panel(species_id=self.sample["species"][0].id)["recent"][0]
        self.assertEqual(filtered["estimated_kg"], 2200)
        self.assertAlmostEqual(filtered["cost_per_kg"], 700 / 2200)

    def test_currency_conversion_and_missing_rates_are_visible(self):
        usd = self.env.ref("base.USD")
        data = self.panel(currency_id=usd.id)
        self.assertIsNone(data["budgets"]["amount"])
        self.assertEqual(data["budgets"]["missing_rates"], 1)
        self.assertIsNone(data["recent"][0]["amount"])
        self.env["step.management.exchange.rate"].create({"currency_id": usd.id, "year": 2026, "month": "11", "company_value_per_unit": 1000})
        data = self.panel(currency_id=usd.id)
        self.assertEqual(data["currencies"]["selected"], "USD")
        self.assertAlmostEqual(data["budgets"]["amount"], .65)
        self.assertAlmostEqual(data["budgets"]["investment"], .3)
        row = data["recent"][0]
        self.assertAlmostEqual(row["harvest"] + row["maintenance"], row["amount"])
        self.assertAlmostEqual(row["amount"], .95)
        self.assertAlmostEqual(row["cost_per_ha"], .095)

    def test_zero_hectares_and_partial_estimation_do_not_invent_ratios(self):
        self.budget.allocation_ids.hectares = 0
        self.assertIsNone(self.panel()["recent"][0]["cost_per_ha"])
        estimate = self.estimate.with_user(self.user)
        estimate.line_ids[-1].unlink()
        estimate.action_validate()
        row = self.panel()["recent"][0]
        self.assertIsNone(row["estimated_kg"])
        self.assertIsNone(row["cost_per_kg"])
        self.assertEqual(row["estimated_centers"], 3)

    def test_company_isolation_even_with_both_companies_selected(self):
        other = self.env["res.company"].create({"name": "QA T228 otra empresa", "currency_id": self.env.ref("base.CLP").id})
        foreign_season = self.env["step.temporada"].with_company(other).create({"name": "QA T228 privada", "company_id": other.id})
        self.env["step.management.operational.budget"].with_company(other).create({
            "description": "QA T228 privado", "company_id": other.id, "season_id": foreign_season.id, "budget_type": "general"})
        model = self.budget.with_context(allowed_company_ids=[self.env.company.id, other.id])
        data = model.get_management_dashboard()
        self.assertEqual(data["budgets"]["total"], 1)
        self.assertNotIn(foreign_season.id, [row["id"] for row in data["filters"]["seasons"]])
        with self.assertRaises(ValidationError):
            model.get_management_dashboard(season_id=foreign_season.id)
