"""Corte V2 E — presupuesto de maquinaria sobre el detalle general existente.

Sólo corre cuando `step_machinery` está instalado (dependencia dura de este
puente `auto_install`). Verifica: cero horas con y sin gastos (nunca
división por cero), horas positivas, desglose por componente, tarifa por
labor, varios centros, snapshot/inmutabilidad, revisión, moneda por
empresa, dos compañías, y que el núcleo (`step_management_costs` solo, sin
este puente) sigue sin cambios de comportamiento.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.step_management_costs.tests.test_management_costs import (
    ManagementCostsCommon,
)

from ..models.budget_group import MACHINERY_GROUP_CODE


@tagged("post_install", "-at_install")
class TestMachineryBudget(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brand = cls.env["fleet.vehicle.model.brand"].create({"name": "MC Brand"})
        cls.model = cls.env["fleet.vehicle.model"].create({
            "name": "MC Model", "brand_id": cls.brand.id,
        })
        cls.vehicle_a = cls.env["fleet.vehicle"].create({
            "model_id": cls.model.id, "company_id": cls.company_a.id,
            "es_maquina": True, "step_total_hrs_mes": 200.0,
        })
        cls.actividad = cls.env["step.actividad"].create({"name": "MC Actividad"})
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.labor = cls.env["step.labor"].create({
            "name": "Rastra", "uom_id": cls.uom_unit.id, "uom_trato": cls.uom_unit.id,
            "actividad_id": cls.actividad.id, "grupo_labor": "manten",
            "met_costeo": "udm", "es_maquina": True, "company_id": cls.company_a.id,
        })
        # `step_machinery` siembra su catálogo canónico (códigos "01".."08")
        # en su propio `post_init_hook`: se reutiliza ese registro real en
        # vez de crear uno duplicado (violaría `unique(cod, company_id)` y,
        # sobre todo, va contra "provenientes de los tipos de servicio
        # reales cuando existan").
        cls.service_fuel = cls._get_or_create_service("01", "Combustible")
        cls.service_rental = cls._get_or_create_service("06", "Arriendo")
        cls.group_machinery_a = cls.env["step.management.budget.group"].get_machinery_group(
            cls.company_a
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @classmethod
    def _get_or_create_service(cls, cod, label, company=None):
        company = company or cls.company_a
        service = cls.env["type.service.machinery"].search([
            ("cod", "=", cod), ("company_id", "in", (company.id, False)),
        ], limit=1)
        return service or cls.env["type.service.machinery"].create({
            "name": label, "cod": cod, "company_id": company.id,
        })

    def _add_consumption(self, vehicle, service, amount, hourly=0.0):
        return self.env["monthly.consumption.line"].create({
            "name": service.name, "vehicle_id": vehicle.id,
            "service_machinery_id": service.id,
            "concept_amount": amount, "cost_hr_amount": hourly,
        })

    def _add_radio(self, vehicle, service, amount, hourly=0.0):
        return self.env["monthly.radio.line"].create({
            "name": service.name, "vehicle_id": vehicle.id,
            "service_machinery_id": service.id,
            "concept_amount": amount, "cost_hr_amount": hourly,
        })

    def _machinery_budget(self, company, center, vehicle, labor=None, hours=10.0,
                           unit_price=0.0):
        group = self.env["step.management.budget.group"].get_machinery_group(company)
        budget = self.env["step.management.operational.budget"].create({
            "description": "Ppto maquinaria", "season": "2026/2027",
            "budget_type": "general", "company_id": company.id,
            "allocation_ids": [(0, 0, {"center_id": center.id, "hectares": 0.0})],
            "line_ids": [(0, 0, {
                "center_id": center.id, "group_id": group.id, "category": "machinery",
                "indicator": vehicle.display_name, "calculation_mode": "quantity",
                "quantity": hours, "unit_price": unit_price,
                "uom_id": self.uom_unit.id,
                "machinery_vehicle_id": vehicle.id,
                "machinery_labor_id": labor.id if labor else False,
                "month_ids": [(0, 0, {
                    "month": "jun", "quantity": hours, "unit_price": unit_price,
                })],
            })],
        })
        return budget, budget.line_ids

    # ------------------------------------------------------------------
    # Tarifa estándar
    # ------------------------------------------------------------------
    def test_zero_hours_without_expenses(self):
        self.vehicle_a.step_total_hrs_mes = 0.0
        self.assertAlmostEqual(self.vehicle_a.mc_standard_hourly_rate(), 0.0)
        self.assertEqual(self.vehicle_a.mc_standard_hourly_components(), {})

    def test_zero_hours_with_expenses_never_divides_by_zero(self):
        self.vehicle_a.step_total_hrs_mes = 0.0
        self._add_consumption(self.vehicle_a, self.service_fuel, 500000.0)
        self._add_radio(self.vehicle_a, self.service_rental, 300000.0)
        # No debe lanzar ZeroDivisionError y el indicador por hora es cero.
        self.assertAlmostEqual(self.vehicle_a.mc_standard_hourly_rate(), 0.0)
        components = self.vehicle_a.mc_standard_hourly_components()
        self.assertAlmostEqual(components["01"], 0.0)
        self.assertAlmostEqual(components["06"], 0.0)

    def test_positive_hours_compute_rate_from_components(self):
        self._add_consumption(self.vehicle_a, self.service_fuel, 200000.0)  # /200h = 1000
        self._add_radio(self.vehicle_a, self.service_rental, 0.0, hourly=500.0)
        components = self.vehicle_a.mc_standard_hourly_components()
        self.assertAlmostEqual(components["01"], 1000.0)
        self.assertAlmostEqual(components["06"], 500.0)
        self.assertAlmostEqual(self.vehicle_a.mc_standard_hourly_rate(), 1500.0)

    def test_components_breakdown_frozen_on_pull(self):
        self._add_consumption(self.vehicle_a, self.service_fuel, 200000.0)
        budget, lines = self._machinery_budget(
            self.company_a, self.center_a, self.vehicle_a, hours=10.0,
        )
        lines.action_pull_machinery_rate()
        self.assertAlmostEqual(lines.unit_price, 1000.0)
        self.assertIn('"01": 1000.0', lines.machinery_component_json)
        self.assertAlmostEqual(lines.amount, 10000.0)

    def test_labor_rate_overrides_standard(self):
        self._add_consumption(self.vehicle_a, self.service_fuel, 200000.0)  # standard = 1000/h
        self.env["step.management.machinery.labor.rate"].create({
            "company_id": self.company_a.id, "vehicle_id": self.vehicle_a.id,
            "labor_id": self.labor.id, "hourly_rate": 4200.0,
        })
        budget, lines = self._machinery_budget(
            self.company_a, self.center_a, self.vehicle_a, labor=self.labor, hours=5.0,
        )
        lines.action_pull_machinery_rate()
        self.assertAlmostEqual(lines.unit_price, 4200.0)
        # Sin labor, la misma máquina sigue usando la tarifa estándar.
        budget2, lines2 = self._machinery_budget(
            self.company_a, self.center_a, self.vehicle_a, hours=5.0,
        )
        lines2.action_pull_machinery_rate()
        self.assertAlmostEqual(lines2.unit_price, 1000.0)

    def test_multiple_centers_independent_lines(self):
        self._add_consumption(self.vehicle_a, self.service_fuel, 200000.0)
        budget = self.env["step.management.operational.budget"].create({
            "description": "Ppto maquinaria varios centros", "season": "2026/2027",
            "budget_type": "general", "company_id": self.company_a.id,
            "allocation_ids": [
                (0, 0, {"center_id": self.center_a.id, "hectares": 0.0}),
                (0, 0, {"center_id": self.center_a2.id, "hectares": 0.0}),
            ],
            "line_ids": [
                (0, 0, {
                    "center_id": self.center_a.id, "group_id": self.group_machinery_a.id,
                    "category": "machinery", "indicator": "Rastra C1",
                    "calculation_mode": "quantity", "quantity": 8.0, "unit_price": 0.0,
                    "uom_id": self.uom_unit.id, "machinery_vehicle_id": self.vehicle_a.id,
                    "month_ids": [(0, 0, {"month": "jun", "quantity": 8.0, "unit_price": 0.0})],
                }),
                (0, 0, {
                    "center_id": self.center_a2.id, "group_id": self.group_machinery_a.id,
                    "category": "machinery", "indicator": "Rastra C2",
                    "calculation_mode": "quantity", "quantity": 3.0, "unit_price": 0.0,
                    "uom_id": self.uom_unit.id, "machinery_vehicle_id": self.vehicle_a.id,
                    "month_ids": [(0, 0, {"month": "jun", "quantity": 3.0, "unit_price": 0.0})],
                }),
            ],
        })
        budget.line_ids.action_pull_machinery_rate()
        self.assertEqual(len(budget.line_ids), 2)
        self.assertAlmostEqual(sum(budget.line_ids.mapped("amount")), (8.0 + 3.0) * 1000.0)

    # ------------------------------------------------------------------
    # Snapshot / revisión / inmutabilidad
    # ------------------------------------------------------------------
    def test_frozen_after_approval(self):
        self._add_consumption(self.vehicle_a, self.service_fuel, 200000.0)
        budget, lines = self._machinery_budget(
            self.company_a, self.center_a, self.vehicle_a, hours=10.0,
        )
        lines.action_pull_machinery_rate()
        budget.action_prepare_general()
        budget.with_user(self.user_approver).action_approve()
        with self.assertRaises(UserError):
            lines.write({"machinery_vehicle_id": self.vehicle_a.id})
        with self.assertRaises(UserError):
            lines.action_pull_machinery_rate()

    def test_revision_preserves_machinery_fields(self):
        self._add_consumption(self.vehicle_a, self.service_fuel, 200000.0)
        budget, lines = self._machinery_budget(
            self.company_a, self.center_a, self.vehicle_a, labor=self.labor, hours=10.0,
        )
        lines.action_pull_machinery_rate()
        budget.action_prepare_general()
        budget.with_user(self.user_approver).action_approve()
        revision = budget.with_user(self.user_approver)._do_reopen("Ajustar horas")
        rev_line = revision.line_ids.filtered(lambda l: l.category == "machinery")
        self.assertEqual(rev_line.machinery_vehicle_id, self.vehicle_a)
        self.assertEqual(rev_line.machinery_labor_id, self.labor)
        self.assertTrue(rev_line.machinery_component_json)

    # ------------------------------------------------------------------
    # Multiempresa / moneda
    # ------------------------------------------------------------------
    def test_two_companies_isolated(self):
        vehicle_b = self.env["fleet.vehicle"].create({
            "model_id": self.model.id, "company_id": self.company_b.id,
            "step_total_hrs_mes": 100.0,
        })
        service_fuel_b = self._get_or_create_service("01", "Combustible", company=self.company_b)
        self._add_consumption(vehicle_b, service_fuel_b, 100000.0)
        budget_b, lines_b = self._machinery_budget(
            self.company_b, self.center_b, vehicle_b, hours=4.0,
        )
        lines_b.action_pull_machinery_rate()
        self.assertAlmostEqual(lines_b.unit_price, 1000.0)
        self.assertEqual(lines_b.currency_id, self.company_b.currency_id)
        # Una máquina de la empresa B no puede usarse en un presupuesto de A
        # (`check_company=True` en `machinery_vehicle_id`; el núcleo de Odoo
        # lo hace cumplir con `UserError`, no `ValidationError`).
        with self.assertRaises(UserError):
            self._machinery_budget(self.company_a, self.center_a, vehicle_b, hours=1.0)

    def test_currency_follows_company(self):
        self._add_consumption(self.vehicle_a, self.service_fuel, 200000.0)
        budget, lines = self._machinery_budget(
            self.company_a, self.center_a, self.vehicle_a, hours=10.0,
        )
        self.assertEqual(lines.currency_id, self.company_a.currency_id)
        self.assertEqual(budget.currency_id, self.company_a.currency_id)

    # ------------------------------------------------------------------
    # Grupo controlado
    # ------------------------------------------------------------------
    def test_machinery_group_is_idempotent_and_reserved(self):
        group1 = self.env["step.management.budget.group"].get_machinery_group(self.company_a)
        group2 = self.env["step.management.budget.group"].get_machinery_group(self.company_a)
        self.assertEqual(group1, group2)
        self.assertEqual(group1.code, MACHINERY_GROUP_CODE)

    # ------------------------------------------------------------------
    # Real efectivo por centro/maquinaria (relación demostrable)
    # ------------------------------------------------------------------
    def test_actual_hours_only_with_demonstrable_relation(self):
        self._add_consumption(self.vehicle_a, self.service_fuel, 200000.0)
        budget, lines = self._machinery_budget(
            self.company_a, self.center_a, self.vehicle_a, hours=10.0,
        )
        registry = self.env["step.hrs.machinery"].create({
            "date": "2026-06-15", "company_id": self.company_a.id,
        })
        self.env["step.hrs.machinery.line"].create({
            "machinery_id": registry.id, "machinery_ids": self.vehicle_a.id,
            "cost_id": self.center_a.analytic_account_id.id,
            "labor_id": self.labor.id, "hrs_maquina": 7.0,
        })
        registry.action_progress()
        registry.action_listo()
        self.assertAlmostEqual(lines.machinery_actual_hours, 7.0)
        # Sin `cost_id` (sin relación demostrable) no se imputa a ningún centro.
        other_registry = self.env["step.hrs.machinery"].create({
            "date": "2026-06-16", "company_id": self.company_a.id,
        })
        self.env["step.hrs.machinery.line"].create({
            "machinery_id": other_registry.id, "machinery_ids": self.vehicle_a.id,
            "hrs_maquina": 3.0,
        })
        other_registry.action_progress()
        other_registry.action_listo()
        lines.invalidate_recordset(["machinery_actual_hours"])
        self.assertAlmostEqual(lines.machinery_actual_hours, 7.0)
