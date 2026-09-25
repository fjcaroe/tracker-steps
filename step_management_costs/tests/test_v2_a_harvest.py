"""Corte V2 A — cosecha por centro/semana, recursos configurables y envases
reutilizables (`PROMPT_CLAUDE_SONNET5_RESPUESTAS_V2_2026-09-06.md`).

No duplica lo que ya cubre `test_fase4_planning.py` (reconciliación de un
solo centro, inmutabilidad básica, estimación no validada, UdM de otra
empresa): se enfoca en lo nuevo — detalle por centro, W53, recursos
encadenados, redondeo, envases separados, revisión y la OP con cosecha como
fuente.
"""

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_management_costs import ManagementCostsCommon, extra_product_vals


@tagged("post_install", "-at_install")
class TestV2AHarvest(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env["step.management.estimation.unit"].create({
            "name": "Bin", "code": "BINV2A", "kg_factor": 400.0,
            "company_id": cls.company_a.id,
        })
        cls.version = cls.env["step.management.estimation.version"].create({
            "code": "V2A", "name": "Estimación V2 A", "season": "2026/2027",
            "company_id": cls.company_a.id,
        })
        cat = cls.env["step.management.fruit.category"].create({
            "name": "Exportación", "code": "EXPV2A", "company_id": cls.company_a.id,
        })
        fc = cls.env["step.management.fruit.class"].create({
            "name": "Export", "code": "EV2A", "category_id": cat.id,
            "company_id": cls.company_a.id,
        })
        cg = cls.env["step.management.caliber.group"].create({
            "name": "Jumbo", "code": "JV2A", "company_id": cls.company_a.id,
        })
        # Curva con W53 (cruce de año) — 3 semanas, residuo a la última.
        cls.week_curve = cls.env["step.management.estimation.curve"].create({
            "name": "Curva V2A", "code": "WV2A", "curve_type": "week",
            "company_id": cls.company_a.id,
            "line_ids": [
                (0, 0, {"week_number": 45, "percentage": 33.33}),
                (0, 0, {"week_number": 46, "percentage": 33.33}),
                (0, 0, {"week_number": 53, "percentage": 33.34}),
            ],
        })
        cls.week_curve.action_validate()
        cls.cal_curve = cls.env["step.management.estimation.curve"].create({
            "name": "Calibre V2A", "code": "CV2A", "curve_type": "caliber",
            "company_id": cls.company_a.id,
            "line_ids": [(0, 0, {"caliber_group_id": cg.id, "percentage": 100.0})],
        })
        cls.cal_curve.action_validate()
        cls.cls_curve = cls.env["step.management.estimation.curve"].create({
            "name": "Clase V2A", "code": "LV2A", "curve_type": "class",
            "company_id": cls.company_a.id,
            "line_ids": [(0, 0, {"fruit_class_id": fc.id, "percentage": 100.0})],
        })
        cls.cls_curve.action_validate()

        cls.center_a.write({"plants": 1000.0})  # total_kg = 1000*1*400 = 400000
        cls.center_a2.write({"plants": 500.0})  # total_kg = 500*1*400 = 200000

        est = cls.env["step.management.estimation"].create({
            "version_id": cls.version.id, "season": "2026/2027",
            "company_id": cls.company_a.id, "unit_id": cls.unit.id,
            "method": "plants", "default_yield_ue": 1.0,
            "week_curve_id": cls.week_curve.id,
            "caliber_curve_id": cls.cal_curve.id, "class_curve_id": cls.cls_curve.id,
            "center_ids": [(6, 0, [cls.center_a.id, cls.center_a2.id])],
        })
        est.action_compute_lines()
        est.action_validate()
        cls.estimation = est

    def _harvest(self, **kw):
        vals = {"company_id": self.company_a.id, "estimation_id": self.estimation.id}
        vals.update(kw)
        return self.env["step.management.harvest.plan"].create(vals)

    def _generated_plan(self):
        hp = self._harvest()
        hp.action_generate()
        return hp

    # ------------------------------------------------------------------
    # Detalle por centro y semana; W53; residuo por centro y total
    # ------------------------------------------------------------------
    def test_two_centers_multiple_weeks_reconcile(self):
        hp = self._generated_plan()
        self.assertEqual(len(hp.line_ids), 6)  # 2 centros x 3 semanas
        self.assertEqual(hp.center_count, 2)
        self.assertAlmostEqual(hp.total_kg, self.estimation.total_kg, places=2)

        lines_a = hp.line_ids.filtered(lambda l: l.center_id == self.center_a)
        lines_a2 = hp.line_ids.filtered(lambda l: l.center_id == self.center_a2)
        self.assertAlmostEqual(sum(lines_a.mapped("kg")), 400000.0, places=2)
        self.assertAlmostEqual(sum(lines_a2.mapped("kg")), 200000.0, places=2)

    def test_week_53_present_and_gets_residual_per_center(self):
        hp = self._generated_plan()
        w53_a = hp.line_ids.filtered(
            lambda l: l.center_id == self.center_a and l.week_number == 53
        )
        w53_a2 = hp.line_ids.filtered(
            lambda l: l.center_id == self.center_a2 and l.week_number == 53
        )
        self.assertTrue(w53_a and w53_a2)
        w45_a = hp.line_ids.filtered(
            lambda l: l.center_id == self.center_a and l.week_number == 45
        )
        w46_a = hp.line_ids.filtered(
            lambda l: l.center_id == self.center_a and l.week_number == 46
        )
        # residuo del centro A a su propia última semana (53), no al total general
        expected_w53_a = 400000.0 - w45_a.kg - w46_a.kg
        self.assertAlmostEqual(w53_a.kg, expected_w53_a, places=2)

    def test_legacy_lines_without_center_are_not_backfilled(self):
        # Simula un plan generado antes de V2 A: línea sin centro, confirmada.
        hp = self._harvest()
        hp.action_generate()
        hp.action_confirm()
        legacy_line = hp.line_ids[0]
        self.assertTrue(legacy_line.center_id)  # generado en este corte, sí lo trae
        # El campo es opcional a nivel de modelo (compatibilidad): no falla
        # si se crea una línea histórica sin centro en otro plan.
        other = self._harvest()
        other.line_ids.create({
            "harvest_plan_id": other.id, "week_number": 1,
            "week_label": "W01", "kg": 10.0, "containers": 1.0,
        })
        self.assertFalse(other.line_ids.center_id)

    # ------------------------------------------------------------------
    # Recursos configurables encadenados
    # ------------------------------------------------------------------
    def _add_resource(self, hp, **vals):
        base = {
            "harvest_plan_id": hp.id, "resource_key": "other",
            "label": "Recurso", "source_type": "harvest_kg", "factor": 1.0,
        }
        base.update(vals)
        return self.env["step.management.harvest.resource"].create(base)

    def test_chained_factors_boxes_then_pallets(self):
        hp = self._generated_plan()
        boxes = self._add_resource(
            hp, resource_key="boxes", label="Cajas", factor=4.0,
            rounding_policy="none",
        )
        pallets = self._add_resource(
            hp, resource_key="pallet_unit", label="Pallet",
            source_type="resource", source_resource_id=boxes.id, factor=60.0,
            rounding_policy="none",
        )
        (boxes + pallets)._compute_weeks()
        kg_w45 = sum(hp.line_ids.filtered(lambda l: l.week_number == 45).mapped("kg"))
        boxes_w45 = boxes.week_ids.filtered(lambda w: w.week_number == 45)
        pallets_w45 = pallets.week_ids.filtered(lambda w: w.week_number == 45)
        self.assertAlmostEqual(boxes_w45.value, kg_w45 / 4.0, places=4)
        self.assertAlmostEqual(pallets_w45.value, (kg_w45 / 4.0) / 60.0, places=4)

    def test_zero_factor_blocked(self):
        hp = self._generated_plan()
        with self.assertRaises(ValidationError):
            self._add_resource(hp, factor=0.0)

    def test_rounding_policies(self):
        hp = self._generated_plan()
        kg_w45 = sum(hp.line_ids.filtered(lambda l: l.week_number == 45).mapped("kg"))
        ceil_r = self._add_resource(
            hp, resource_key="harvest_workers", label="Ceil", factor=7.0,
            rounding_policy="ceil",
        )
        none_r = self._add_resource(
            hp, resource_key="harvest_workers", label="Sin redondeo", factor=7.0,
            rounding_policy="none",
        )
        (ceil_r + none_r)._compute_weeks()
        exact = kg_w45 / 7.0
        ceil_value = ceil_r.week_ids.filtered(lambda w: w.week_number == 45).value
        none_value = none_r.week_ids.filtered(lambda w: w.week_number == 45).value
        self.assertAlmostEqual(none_value, exact, places=4)
        self.assertGreaterEqual(ceil_value, exact)
        self.assertLess(ceil_value - exact, 1.0)

    def test_resource_week_is_not_manually_editable(self):
        hp = self._generated_plan()
        r = self._add_resource(hp, factor=2.0)
        r._compute_weeks()
        with self.assertRaises(UserError):
            r.week_ids[0].write({"value": 999.0})

    def test_factor_changed_after_confirm_does_not_alter_snapshot(self):
        hp = self._generated_plan()
        r = self._add_resource(hp, resource_key="boxes", label="Cajas", factor=4.0)
        r._compute_weeks()
        frozen_value = r.week_ids.filtered(lambda w: w.week_number == 45).value
        hp.action_confirm()
        snapshot_before = hp.confirmation_snapshot
        r.factor = 999.0  # editable después de confirmar (no altera lo congelado)
        self.assertEqual(hp.confirmation_snapshot, snapshot_before)
        self.assertAlmostEqual(
            r.week_ids.filtered(lambda w: w.week_number == 45).value, frozen_value,
        )

    # ------------------------------------------------------------------
    # Envases reutilizables (C4) — listado aparte, sin mezclar con stock
    # ------------------------------------------------------------------
    def test_reusable_container_target_and_gap(self):
        hp = self._generated_plan()
        product = self.env["product.product"].create(dict({
            "name": "Bin reutilizable", "type": "consu", "is_storable": True,
        }, **extra_product_vals(self.env)))
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_a.id)], limit=1,
        )
        self.env["stock.quant"].sudo()._update_available_quantity(
            product, warehouse.lot_stock_id, 50.0,
        )
        boxes = self._add_resource(
            hp, resource_key="boxes", label="Bins", factor=4.0,
            rounding_policy="none", is_reusable_container=True,
            product_id=product.id, coverage_multiplier=3.0,
        )
        boxes._compute_weeks()
        boxes.invalidate_recordset()
        weekly_values = boxes.week_ids.mapped("value")
        self.assertAlmostEqual(boxes.weekly_max_value, max(weekly_values), places=2)
        self.assertAlmostEqual(
            boxes.target_inventory, boxes.weekly_max_value * 3.0, places=2,
        )
        self.assertAlmostEqual(boxes.on_hand_quantity, 50.0, places=2)
        expected_gap = max(0.0, boxes.target_inventory - 50.0)
        self.assertAlmostEqual(boxes.inventory_gap, expected_gap, places=2)

    def test_reusable_container_not_mixed_with_stock_requirement(self):
        hp = self._generated_plan()
        boxes = self._add_resource(
            hp, resource_key="boxes", label="Bins", factor=4.0,
            is_reusable_container=True,
        )
        boxes._compute_weeks()
        req = self.env["step.management.stock.requirement"].create({
            "company_id": self.company_a.id, "season": "2026/2027",
            "granularity": "season",
        })
        req.action_compute()
        # los envases nunca aparecen en las necesidades de stock consumible
        self.assertFalse(req.line_ids)

    # ------------------------------------------------------------------
    # Multiempresa
    # ------------------------------------------------------------------
    def test_resource_source_cross_company_rejected(self):
        unit_b = self.env["step.management.estimation.unit"].create({
            "name": "BinB", "code": "BINV2AB", "kg_factor": 1.0,
            "company_id": self.company_b.id,
        })
        version_b = self.env["step.management.estimation.version"].create({
            "code": "V2AB", "name": "Estimación B", "season": "2026/2027",
            "company_id": self.company_b.id,
        })
        curve_b = self.env["step.management.estimation.curve"].create({
            "name": "Curva B", "code": "WBV2A", "curve_type": "week",
            "company_id": self.company_b.id,
            "line_ids": [(0, 0, {"week_number": 45, "percentage": 100.0})],
        })
        curve_b.action_validate()
        est_b = self.env["step.management.estimation"].create({
            "version_id": version_b.id, "season": "2026/2027",
            "company_id": self.company_b.id, "unit_id": unit_b.id,
            "method": "kilos", "week_curve_id": curve_b.id,
            "caliber_curve_id": curve_b.id, "class_curve_id": curve_b.id,
            "center_ids": [(6, 0, [self.center_b.id])],
        })
        est_b.action_compute_lines()
        est_b.line_ids.total_kg_input = 1000.0
        hp_b = self.env["step.management.harvest.plan"].create({
            "company_id": self.company_b.id, "estimation_id": est_b.id,
        })
        hp_a = self._generated_plan()
        resource_a = self._add_resource(hp_a, factor=2.0)
        with self.assertRaises(Exception):
            self.env["step.management.harvest.resource"].create({
                "harvest_plan_id": hp_b.id, "resource_key": "other",
                "label": "Cruzado", "source_type": "resource",
                "source_resource_id": resource_a.id, "factor": 1.0,
            })

    # ------------------------------------------------------------------
    # Revisión / inmutabilidad
    # ------------------------------------------------------------------
    def test_revision_after_confirm(self):
        hp = self._generated_plan()
        hp.action_confirm()
        with self.assertRaises(UserError):
            hp._do_reopen("")
        revision = hp._do_reopen("Corrección de kilos")
        self.assertEqual(revision.state, "draft")
        self.assertFalse(revision.line_ids)  # derivado: se regenera, no se copia
        revision.action_generate()
        revision.action_confirm()
        hp.invalidate_recordset()
        self.assertEqual(hp.state, "superseded")
        self.assertEqual(hp.superseded_by_id, revision)

    # ------------------------------------------------------------------
    # OP: cosecha como fuente trazable, sin duplicar
    # ------------------------------------------------------------------
    def test_op_includes_harvest_line_source(self):
        hp = self._generated_plan()
        hp.action_confirm()
        one_line = hp.line_ids.filtered(lambda l: l.center_id == self.center_a)[:1]
        period = self.env["step.management.period.service"]
        located = period.week_of_season(hp.season, one_line.week_number)
        order = self.env["step.management.production.order"].create({
            "company_id": self.company_a.id, "season": hp.season,
            "iso_year": located["iso_year"], "iso_week": one_line.week_number,
            "center_id": self.center_a.id,
        })
        commands, _monday, _sunday, _fp = order._build_op_commands()
        harvest_cmds = [
            v for (_o, _z, v) in commands if v["source_type"] == "harvest_line"
        ]
        self.assertEqual(len(harvest_cmds), 1)
        self.assertAlmostEqual(harvest_cmds[0]["quantity"], one_line.kg, places=2)

        order.action_generate_preview()
        wizard = self.env["step.management.production.order.preview.wizard"].with_context(
            default_order_id=order.id
        ).create({})
        wizard.action_confirm()
        harvest_lines = order.line_ids.filtered(lambda l: l.source_type == "harvest_line")
        self.assertEqual(len(harvest_lines), 1)
        # no se duplica: una fuente idéntica no puede repetirse en la misma OP
        # (constraint SQL, igual patrón que las otras dos fuentes del Corte 2)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["step.management.production.order.line"].create({
                    "order_id": order.id, "source_type": "harvest_line",
                    "harvest_plan_line_id": harvest_lines.harvest_plan_line_id.id,
                    "quantity": 1.0,
                })

    def test_old_authorized_op_not_changed_by_new_harvest_revision(self):
        hp = self._generated_plan()
        hp.action_confirm()
        one_line = hp.line_ids.filtered(lambda l: l.center_id == self.center_a)[:1]
        period = self.env["step.management.period.service"]
        located = period.week_of_season(hp.season, one_line.week_number)
        order = self.env["step.management.production.order"].create({
            "company_id": self.company_a.id, "season": hp.season,
            "iso_year": located["iso_year"], "iso_week": one_line.week_number,
            "center_id": self.center_a.id,
        })
        order.action_generate_preview()
        self.env["step.management.production.order.preview.wizard"].with_context(
            default_order_id=order.id
        ).create({}).action_confirm()
        order.with_user(self.user_approver).action_authorize()
        old_hash = order.approval_hash

        revision = hp._do_reopen("Ajuste posterior")
        revision.action_generate()
        revision.action_confirm()

        order.invalidate_recordset()
        self.assertEqual(order.approval_hash, old_hash)
        self.assertEqual(order.state, "authorized")
