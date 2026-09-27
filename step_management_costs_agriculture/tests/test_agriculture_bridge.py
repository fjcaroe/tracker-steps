"""Corte V2 D — puente con los maestros agrícolas reales de `step_hr`.

Sólo se instala (y sólo estas pruebas corren) cuando `step_hr` está
presente — `auto_install` exige ambas dependencias. Verifica la precedencia
de rendimiento estándar (centro → variedad → grupo de variedad), la fuente
de plantas, el snapshot/procedencia congelados al validar, y que el método
"Kilos" del núcleo sigue sin aplicar rendimiento (D05, sin cambios).
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.step_management_costs.tests.test_management_costs import (
    ManagementCostsCommon,
    extra_product_vals,
)


@tagged("post_install", "-at_install")
class TestAgricultureBridge(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        uom = cls.env.ref("uom.product_uom_unit")
        cls.labor = cls.env["product.template"].create(dict({
            "name": "Cosecha V2D", "type": "service",
        }, **extra_product_vals(cls.env)))
        cls.fundo = cls.env["step.fundo"].create({
            "name": "Fundo V2D", "company_id": cls.company_a.id,
        })
        cls.especie = cls.env["step.especie"].create({
            "name": "Cereza V2D", "type_especie": "frutal", "group_especie": "fruta_h",
            "company_id": cls.company_a.id,
        })
        cls.grupo = cls.env["step.grupo.variedad"].create({
            "name": "Grupo V2D", "especie_id": cls.especie.id, "company_id": cls.company_a.id,
        })
        cls.variedad = cls.env["step.variedad"].create({
            "name": "Bing V2D", "cod_variedad": "BNGV2D", "especie_id": cls.especie.id,
            "grupo_variedad_id": cls.grupo.id, "company_id": cls.company_a.id,
        })

        def _account(name, variedad=False, grupo=False):
            return cls.env["account.analytic.account"].create({
                "name": name, "plan_id": cls.plan.id, "company_id": cls.company_a.id,
                "type_costo": "fruta", "etapa_costo": "ope", "tipo_fruta": "conven",
                "fundo_id": cls.fundo.id, "especie_id": cls.especie.id,
                "variedad_id": variedad and variedad.id, "grupo_variedad_id": grupo and grupo.id,
                "plant_cost": 500, "has_cost": 10,
            })

        # Centro 1: tiene línea propia de rendimiento -> debe ganar sobre
        # variedad y grupo aunque ambas también tengan línea.
        cls.account_center = _account("AA centro V2D", variedad=cls.variedad, grupo=cls.grupo)
        # Centro 2: sin línea propia, sólo variedad (y grupo, que no debe usarse).
        cls.account_variety = _account("AA variedad V2D", variedad=cls.variedad, grupo=cls.grupo)
        # Centro 3: sin variedad asignada, sólo grupo.
        cls.account_group = _account("AA grupo V2D", variedad=False, grupo=cls.grupo)

        cls.center_center = cls.env["step.management.cost.center"].create({
            "code": "V2DCTR", "name": "Centro V2D (centro)", "company_id": cls.company_a.id,
            "hectares": 10.0, "analytic_account_id": cls.account_center.id,
        })
        cls.center_variety = cls.env["step.management.cost.center"].create({
            "code": "V2DVAR", "name": "Centro V2D (variedad)", "company_id": cls.company_a.id,
            "hectares": 10.0, "analytic_account_id": cls.account_variety.id,
        })
        cls.center_group = cls.env["step.management.cost.center"].create({
            "code": "V2DGRP", "name": "Centro V2D (grupo)", "company_id": cls.company_a.id,
            "hectares": 10.0, "analytic_account_id": cls.account_group.id,
        })

        cls.env["step.rendimiento.line"].create({
            "name": "Rend. centro", "centro_id": cls.account_center.id,
            "labor_id": cls.labor.id, "uom_id": uom.id, "uom_trato": uom.id,
            "redim_std": 12.5,
        })
        cls.env["step.variedad.line"].create({
            "name": "Rend. variedad", "variedad_id": cls.variedad.id,
            "labor_id": cls.labor.id, "uom_id": uom.id, "uom_trato": uom.id,
            "hec_rendimiento": 8,
        })
        cls.env["step.grupo.variedad.line"].create({
            "name": "Rend. grupo", "grupo_variedad_id": cls.grupo.id,
            "labor_id": cls.labor.id, "uom_id": uom.id, "uom_trato": uom.id,
            "hec_rendimiento": 5,
        })

        cls.unit = cls.env["step.management.estimation.unit"].create({
            "name": "Bin", "code": "BINV2D", "kg_factor": 400.0,
            "company_id": cls.company_a.id,
        })
        cls.version = cls.env["step.management.estimation.version"].create({
            "code": "V2D", "name": "Estimación V2D", "season": "2026/2027",
            "company_id": cls.company_a.id,
        })
        cls.week_curve = cls.env["step.management.estimation.curve"].create({
            "name": "Semana V2D", "code": "WV2D", "curve_type": "week",
            "company_id": cls.company_a.id,
            "line_ids": [(0, 0, {"week_number": 45, "percentage": 100.0})],
        })
        cls.week_curve.action_validate()
        cat = cls.env["step.management.fruit.category"].create({
            "name": "Exp V2D", "code": "EXPV2D", "company_id": cls.company_a.id,
        })
        fc = cls.env["step.management.fruit.class"].create({
            "name": "Exp V2D", "code": "EV2D", "category_id": cat.id, "company_id": cls.company_a.id,
        })
        cls.class_curve = cls.env["step.management.estimation.curve"].create({
            "name": "Clase V2D", "code": "LV2D", "curve_type": "class",
            "company_id": cls.company_a.id,
            "line_ids": [(0, 0, {"fruit_class_id": fc.id, "percentage": 100.0})],
        })
        cls.class_curve.action_validate()
        cg = cls.env["step.management.caliber.group"].create({
            "name": "J V2D", "code": "JV2D", "company_id": cls.company_a.id,
        })
        cls.caliber_curve = cls.env["step.management.estimation.curve"].create({
            "name": "Calibre V2D", "code": "CV2D", "curve_type": "caliber",
            "company_id": cls.company_a.id,
            "line_ids": [(0, 0, {"caliber_group_id": cg.id, "percentage": 100.0})],
        })
        cls.caliber_curve.action_validate()

    def _estimation(self, centers, harvest_labor=None, method="plants", default_yield=1.0):
        vals = {
            "version_id": self.version.id, "season": "2026/2027",
            "company_id": self.company_a.id, "unit_id": self.unit.id,
            "method": method, "default_yield_ue": default_yield,
            "week_curve_id": self.week_curve.id,
            "caliber_curve_id": self.caliber_curve.id, "class_curve_id": self.class_curve.id,
            "center_ids": [(6, 0, [c.id for c in centers])],
        }
        if harvest_labor is not None:
            vals["harvest_labor_id"] = harvest_labor.id
        est = self.env["step.management.estimation"].create(vals)
        est.action_compute_lines()
        return est

    def _line_for(self, est, center):
        return est.line_ids.filtered(lambda l: l.center_id == center)

    # ------------------------------------------------------------------
    # Precedencia completa de rendimiento
    # ------------------------------------------------------------------
    def test_precedence_center_wins_over_variety_and_group(self):
        est = self._estimation([self.center_center], harvest_labor=self.labor)
        line = self._line_for(est, self.center_center)
        self.assertAlmostEqual(line.yield_ue, 12.5)
        self.assertIn("centro", line.yield_source.lower())

    def test_precedence_falls_back_to_variety(self):
        est = self._estimation([self.center_variety], harvest_labor=self.labor)
        line = self._line_for(est, self.center_variety)
        self.assertAlmostEqual(line.yield_ue, 8.0)
        self.assertIn("variedad", line.yield_source.lower())

    def test_precedence_falls_back_to_group(self):
        est = self._estimation([self.center_group], harvest_labor=self.labor)
        line = self._line_for(est, self.center_group)
        self.assertAlmostEqual(line.yield_ue, 5.0)
        self.assertIn("grupo", line.yield_source.lower())

    def test_absent_at_every_level_documented_and_falls_back(self):
        other_labor = self.env["product.template"].create(dict({
            "name": "Labor sin datos", "type": "service",
        }, **extra_product_vals(self.env)))
        est = self._estimation(
            [self.center_center], harvest_labor=other_labor, default_yield=3.0,
        )
        line = self._line_for(est, self.center_center)
        self.assertAlmostEqual(line.yield_ue, 3.0)  # default_yield_ue del núcleo, sin tocar
        self.assertIn("manual", line.yield_source.lower())

    def test_no_harvest_labor_keeps_core_behavior(self):
        est = self._estimation([self.center_center], harvest_labor=None, default_yield=2.0)
        line = self._line_for(est, self.center_center)
        self.assertAlmostEqual(line.yield_ue, 2.0)
        self.assertIn("manual", line.yield_source.lower())

    # ------------------------------------------------------------------
    # Plantas por cuartel y fallback documentado
    # ------------------------------------------------------------------
    def test_plants_from_center_master(self):
        est = self._estimation([self.center_center], harvest_labor=self.labor)
        line = self._line_for(est, self.center_center)
        self.assertAlmostEqual(line.plants, 500.0)
        self.assertIn("maestro", line.plants_source.lower())

    def test_plants_fallback_when_no_analytic_link(self):
        core_only = self.env["step.management.cost.center"].create({
            "code": "V2DCOREONLY", "name": "Sin maestro", "company_id": self.company_a.id,
            "hectares": 10.0, "plants": 250.0,
        })
        est = self._estimation([core_only], harvest_labor=self.labor)
        line = self._line_for(est, core_only)
        self.assertAlmostEqual(line.plants, 250.0)
        self.assertIn("núcleo", line.plants_source.lower())

    # ------------------------------------------------------------------
    # Dos compañías; método Kilos sin doble rendimiento; snapshot inmutable
    # ------------------------------------------------------------------
    def test_two_companies_do_not_cross_link(self):
        fundo_b = self.env["step.fundo"].create({
            "name": "Fundo B V2D", "company_id": self.company_b.id,
        })
        account_b = self.env["account.analytic.account"].create({
            "name": "AA B V2D", "plan_id": self.plan.id, "company_id": self.company_b.id,
            "type_costo": "fruta", "etapa_costo": "ope", "tipo_fruta": "conven",
            "fundo_id": fundo_b.id, "plant_cost": 999,
        })
        # `check_company=True` (ya existente en el núcleo) rechaza enlazar un
        # centro de la empresa A con una cuenta analítica de la empresa B.
        with self.assertRaises(Exception):
            self.center_a.write({"analytic_account_id": account_b.id})

    def test_kilos_method_never_applies_yield_twice(self):
        est = self._estimation(
            [self.center_center], harvest_labor=self.labor, method="kilos",
        )
        line = self._line_for(est, self.center_center)
        line.total_kg_input = 12345.0
        self.assertAlmostEqual(line.total_kg, 12345.0)
        # aunque haya rendimiento estándar real disponible, "Kilos" lo ignora
        self.assertAlmostEqual(line.total_kg, 12345.0)

    def test_snapshot_freezes_source_fields(self):
        est = self._estimation([self.center_center], harvest_labor=self.labor)
        est.action_validate()
        line = self._line_for(est, self.center_center)
        with self.assertRaises(UserError):
            line.write({"yield_source": "manipulado"})
        with self.assertRaises(UserError):
            line.write({"plants_source": "manipulado"})
