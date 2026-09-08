import hashlib
import json

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_management_costs import ManagementCostsCommon


@tagged("post_install", "-at_install")
class TestFase3Estimation(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env["step.management.estimation.unit"].create({
            "name": "Bin", "code": "BIN", "kg_factor": 400.0,
            "company_id": cls.company_a.id,
        })
        cls.category = cls.env["step.management.fruit.category"].create({
            "name": "Exportación", "code": "EXP", "company_id": cls.company_a.id,
        })
        cls.fc1 = cls.env["step.management.fruit.class"].create({
            "name": "Exportación", "code": "E", "category_id": cls.category.id,
            "company_id": cls.company_a.id,
        })
        cls.fc2 = cls.env["step.management.fruit.class"].create({
            "name": "Nacional", "code": "N", "category_id": cls.category.id,
            "company_id": cls.company_a.id,
        })
        cls.cg1 = cls.env["step.management.caliber.group"].create({
            "name": "Jumbo", "code": "J", "company_id": cls.company_a.id,
        })
        cls.cg2 = cls.env["step.management.caliber.group"].create({
            "name": "Large", "code": "L", "company_id": cls.company_a.id,
        })

        cls.week_curve = cls._mk_curve("week", "WK", [
            {"week_number": 45, "percentage": 33.33},
            {"week_number": 46, "percentage": 33.33},
            {"week_number": 53, "percentage": 33.34},
        ])
        cls.caliber_curve = cls._mk_curve("caliber", "CB", [
            {"caliber_group_id": cls.cg1.id, "percentage": 60.0},
            {"caliber_group_id": cls.cg2.id, "percentage": 40.0},
        ])
        cls.class_curve = cls._mk_curve("class", "CL", [
            {"fruit_class_id": cls.fc1.id, "percentage": 70.0},
            {"fruit_class_id": cls.fc2.id, "percentage": 30.0},
        ])

        cls.center_a.write({
            "plants": 1000.0, "farm": "Fundo A", "plot": "Cuartel 1",
            "species": "Cerezo", "variety": "Santina",
        })
        cls.center_a2.write({"plants": 500.0})

        cls.version = cls.env["step.management.estimation.version"].create({
            "code": "V1", "name": "Estimación 2026/2027", "season": "2026/2027",
            "company_id": cls.company_a.id,
        })

    @classmethod
    def _mk_curve(cls, curve_type, code, lines):
        curve = cls.env["step.management.estimation.curve"].create({
            "name": "Curva %s" % code, "code": code, "curve_type": curve_type,
            "company_id": cls.company_a.id,
            "line_ids": [(0, 0, vals) for vals in lines],
        })
        curve.action_validate()
        return curve

    def _base_vals(self, **overrides):
        vals = {
            "version_id": self.version.id,
            "season": "2026/2027",
            "company_id": self.company_a.id,
            "unit_id": self.unit.id,
            "method": "plants",
            "default_yield_ue": 1.0,
            "species": "Cerezo",
            "variety": "Santina",
            "week_curve_id": self.week_curve.id,
            "caliber_curve_id": self.caliber_curve.id,
            "class_curve_id": self.class_curve.id,
            "center_ids": [(6, 0, [self.center_a.id])],
        }
        vals.update(overrides)
        return vals

    def _mk_estimation(self, method="plants", centers=None, compute=True, **overrides):
        if centers is not None:
            overrides["center_ids"] = [(6, 0, [c.id for c in centers])]
        est = self.env["step.management.estimation"].create(
            self._base_vals(method=method, **overrides)
        )
        if compute:
            est.action_compute_lines()
        return est

    # ------------------------------------------------------------------
    # Fórmula D05
    # ------------------------------------------------------------------
    def test_method_plants(self):
        est = self._mk_estimation("plants")
        line = est.line_ids
        self.assertEqual(line.plants, 1000.0)
        self.assertEqual(line.kg_factor, 400.0)
        self.assertAlmostEqual(line.total_ue, 1000.0)
        self.assertAlmostEqual(line.total_kg, 400000.0)  # 1000 * 1 * 400, factor una vez
        self.assertAlmostEqual(est.total_kg, 400000.0)

    def test_method_hectares(self):
        est = self._mk_estimation("hectares")
        line = est.line_ids
        self.assertAlmostEqual(line.total_ue, 10.0)  # 10 ha * 1
        self.assertAlmostEqual(line.total_kg, 4000.0)  # 10 * 400

    def test_method_kilos_direct_no_double_multiply(self):
        est = self._mk_estimation("kilos")
        est.line_ids.total_kg_input = 12345.0
        self.assertAlmostEqual(est.line_ids.total_kg, 12345.0)
        # cambiar rendimiento/plantas no vuelve a multiplicar en método kilos
        est.line_ids.yield_ue = 999.0
        est.line_ids.plants = 42.0
        self.assertAlmostEqual(est.line_ids.total_kg, 12345.0)
        self.assertAlmostEqual(est.total_kg, 12345.0)

    def test_kg_ratios_never_divide_by_zero(self):
        c0 = self.env["step.management.cost.center"].create({
            "code": "CZERO", "name": "Sin datos", "company_id": self.company_a.id,
            "hectares": 0.0, "plants": 0.0,
        })
        est = self._mk_estimation("kilos", centers=[c0])
        est.line_ids.total_kg_input = 500.0
        self.assertEqual(est.line_ids.kg_per_ha, 0.0)
        self.assertEqual(est.line_ids.kg_per_plant, 0.0)
        self.assertEqual(est.kg_per_ha, 0.0)
        self.assertEqual(est.kg_per_plant, 0.0)
        est.action_validate()
        self.assertEqual(est.state, "validated")

    # ------------------------------------------------------------------
    # Conciliación, redondeo y residuo
    # ------------------------------------------------------------------
    def test_three_axes_reconcile_with_total_kg(self):
        est = self._mk_estimation("hectares")  # total_kg = 4000
        est.action_validate()
        total = est.total_kg
        for axis in ("week", "caliber", "class"):
            axis_lines = est.distribution_ids.filtered(lambda d: d.axis == axis)
            self.assertTrue(axis_lines)
            self.assertAlmostEqual(sum(axis_lines.mapped("kg")), total, places=2)

    def test_rounding_residual_goes_to_last_ordered_line(self):
        est = self._mk_estimation("kilos")
        est.line_ids.total_kg_input = 1000.01
        est.action_validate()
        week = est.distribution_ids.filtered(lambda d: d.axis == "week").sorted(
            key=lambda d: (d.sequence, d.id)
        )
        # 1000.01 * 33.33% = 333.303 -> 333.30 (x2) ; residuo en la última:
        # 1000.01 - 666.60 = 333.41  (no el 333.40 "ingenuo" de 33.34%)
        self.assertAlmostEqual(week[0].kg, 333.30, places=2)
        self.assertAlmostEqual(week[1].kg, 333.30, places=2)
        self.assertAlmostEqual(week[2].kg, 333.41, places=2)
        self.assertAlmostEqual(sum(week.mapped("kg")), 1000.01, places=2)

    def test_week_53_is_supported(self):
        est = self._mk_estimation("hectares")
        est.action_validate()
        w53 = est.distribution_ids.filtered(
            lambda d: d.axis == "week" and d.week_number == 53
        )
        self.assertEqual(len(w53), 1)
        self.assertEqual(w53.dimension_name, "W53")

    # ------------------------------------------------------------------
    # Idempotencia / transaccionalidad
    # ------------------------------------------------------------------
    def test_compute_lines_is_idempotent(self):
        est = self._mk_estimation("hectares", centers=[self.center_a, self.center_a2])
        count = len(est.line_ids)
        totals = sorted(est.line_ids.mapped("total_kg"))
        est.action_compute_lines()
        self.assertEqual(len(est.line_ids), count)
        self.assertEqual(sorted(est.line_ids.mapped("total_kg")), totals)

    def test_validation_generates_deterministic_distribution(self):
        est_a = self._mk_estimation("hectares")
        est_b = self._mk_estimation("hectares")
        est_a.action_validate()
        est_b.action_validate()
        key = lambda d: (d.axis, d.sequence, d.id)
        self.assertEqual(
            est_a.distribution_ids.sorted(key=key).mapped("kg"),
            est_b.distribution_ids.sorted(key=key).mapped("kg"),
        )

    # ------------------------------------------------------------------
    # Inmutabilidad y revisiones
    # ------------------------------------------------------------------
    def test_validated_estimation_is_immutable(self):
        est = self._mk_estimation("hectares")
        est.action_validate()
        with self.assertRaises(UserError):
            est.write({"species": "Otra"})
        with self.assertRaises(UserError):
            est.line_ids.write({"hectares": 1.0})
        with self.assertRaises(UserError):
            est.line_ids.unlink()
        with self.assertRaises(UserError):
            est.distribution_ids[0].write({"kg": 0.0})
        with self.assertRaises(UserError):
            est.distribution_ids[0].unlink()
        with self.assertRaises(UserError):
            est.unlink()

    def test_revision_flow_and_supersede(self):
        est = self._mk_estimation("hectares")
        est.action_validate()
        with self.assertRaises(UserError):
            est._do_reopen("")
        revision = est._do_reopen("Ajuste de rendimiento")
        self.assertEqual(est.state, "validated")
        self.assertEqual(revision.state, "draft")
        self.assertEqual(revision.revision, 2)
        self.assertEqual(revision.revision_of_id, est)
        self.assertEqual(revision.reopen_reason, "Ajuste de rendimiento")
        self.assertEqual(len(revision.line_ids), len(est.line_ids))
        self.assertFalse(revision.distribution_ids)
        # sólo una sucesora activa
        with self.assertRaises(UserError):
            est.action_new_revision()
        revision.line_ids.write({"yield_ue": 2.0})
        revision.action_validate()
        est.invalidate_recordset()
        self.assertEqual(est.state, "superseded")
        self.assertEqual(est.superseded_by_id, revision)
        self.assertAlmostEqual(revision.total_kg, 8000.0)

    def test_validation_snapshot_and_hash(self):
        est = self._mk_estimation("hectares")
        est.action_validate()
        self.assertTrue(est.validation_snapshot)
        self.assertEqual(
            est.validation_hash,
            hashlib.sha256(est.validation_snapshot.encode("utf-8")).hexdigest(),
        )
        payload = json.loads(est.validation_snapshot)
        self.assertEqual(payload["revision"], 1)
        self.assertAlmostEqual(payload["total_kg"], est.total_kg, places=2)
        self.assertEqual(len(payload["distributions"]["week"]), 3)

    # ------------------------------------------------------------------
    # Roles y llamadas RPC
    # ------------------------------------------------------------------
    def test_roles_operator_creates_approver_validates(self):
        est = self.env["step.management.estimation"].with_user(
            self.user_operator
        ).create(self._base_vals())
        est.with_user(self.user_operator).action_compute_lines()
        self.assertTrue(est.line_ids)
        # operador no valida ni llamando el método directo (equivalente RPC)
        with self.assertRaises(UserError):
            est.with_user(self.user_operator).action_validate()
        # consulta no crea
        with self.assertRaises(AccessError):
            self.env["step.management.estimation"].with_user(
                self.user_readonly
            ).create(self._base_vals())
        # aprobador sí valida
        est.with_user(self.user_approver).action_validate()
        self.assertEqual(est.state, "validated")

    def test_context_flag_cannot_bypass_immutability(self):
        est = self._mk_estimation("hectares")
        est.action_validate()
        forged = est.with_context(
            mc_force=True, bypass_immutability=True, force_edit=True
        )
        with self.assertRaises(UserError):
            forged.write({"species": "hack"})
        with self.assertRaises(UserError):
            forged.line_ids.with_context(mc_force=True).write({"plants": 1.0})

    # ------------------------------------------------------------------
    # Curvas incorrectas o incompletas
    # ------------------------------------------------------------------
    def test_validation_requires_three_valid_curves(self):
        draft_curve = self.env["step.management.estimation.curve"].create({
            "name": "Sin validar", "code": "DRAFT", "curve_type": "week",
            "company_id": self.company_a.id,
            "line_ids": [(0, 0, {"week_number": 1, "percentage": 100.0})],
        })
        est = self._mk_estimation("hectares", week_curve_id=draft_curve.id)
        with self.assertRaises(UserError):
            est.action_validate()  # curva no validada

        est_missing = self._mk_estimation("hectares")
        est_missing.write({"class_curve_id": False})
        with self.assertRaises(UserError):
            est_missing.action_validate()  # falta una curva

        est_wrong = self._mk_estimation(
            "hectares", class_curve_id=self.week_curve.id
        )
        with self.assertRaises(UserError):
            est_wrong.action_validate()  # tipo de curva incorrecto

    def test_zero_total_kg_cannot_validate(self):
        est = self._mk_estimation("kilos")  # total_kg_input queda en 0
        with self.assertRaises(UserError):
            est.action_validate()

    # ------------------------------------------------------------------
    # Multicompañía y constraints SQL
    # ------------------------------------------------------------------
    def test_cross_company_relations_rejected(self):
        unit_b = self.env["step.management.estimation.unit"].create({
            "name": "Bin B", "code": "BINB", "kg_factor": 100.0,
            "company_id": self.company_b.id,
        })
        with self.assertRaises(UserError):
            self.env["step.management.estimation"].create(
                self._base_vals(unit_id=unit_b.id)
            )
        with self.assertRaises(ValidationError):
            self.env["step.management.estimation"].create(
                self._base_vals(center_ids=[(6, 0, [self.center_b.id])])
            )

    def test_operator_only_sees_own_company_estimations(self):
        version_b = self.env["step.management.estimation.version"].create({
            "code": "VB", "name": "Versión B", "season": "2026/2027",
            "company_id": self.company_b.id,
        })
        est_b = self.env["step.management.estimation"].create({
            "version_id": version_b.id, "season": "2026/2027",
            "company_id": self.company_b.id,
            "unit_id": self.env["step.management.estimation.unit"].create({
                "name": "UB", "code": "UB", "kg_factor": 1.0,
                "company_id": self.company_b.id,
            }).id,
            "method": "kilos",
        })
        visible = self.env["step.management.estimation"].with_user(
            self.user_operator
        ).search([])
        self.assertNotIn(est_b, visible)

    def test_version_code_unique_per_company(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["step.management.estimation.version"].create({
                    "code": "V1", "name": "Duplicada", "season": "x",
                    "company_id": self.company_a.id,
                })

    def test_line_center_unique_per_estimation(self):
        est = self._mk_estimation("hectares")
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["step.management.estimation.line"].create({
                    "estimation_id": est.id, "center_id": self.center_a.id,
                })

    # ------------------------------------------------------------------
    # Upgrade / campo no destructivo
    # ------------------------------------------------------------------
    def test_cost_center_plants_field_defaults_zero(self):
        self.assertEqual(self.center_a_no_aa.plants, 0.0)
        self.center_a_no_aa.plants = 25.0
        self.assertEqual(self.center_a_no_aa.plants, 25.0)
        with self.assertRaises(ValidationError):
            self.center_a_no_aa.plants = -1.0
