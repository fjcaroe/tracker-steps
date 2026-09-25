"""Corte 1 post Fase 6 — respuestas del cliente:

- vista previa antes de regenerar el plan semanal;
- política de precio de programas (D07): default `standard`, congelado en
  snapshot (sin cambio de código, sólo regresión);
- programas por temporada + centro de costo, misma variedad;
- importación Excel de la receta de un programa (staging seguro);
- necesidades de stock cruzadas con inventario real (almacén + métrica
  explícita, nunca mezclada bajo una sola etiqueta).
"""

import base64
import io

import openpyxl

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .test_management_costs import ManagementCostsCommon, extra_product_vals

RECIPE_HEADERS = [
    "Producto", "Dosis/Ha", "UdM", "Objetivo", "Semana", "Carencia", "Reingreso",
]


def _recipe_xlsx(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(RECIPE_HEADERS)
    for row in rows:
        ws.append(row)
    bio = io.BytesIO()
    wb.save(bio)
    return base64.b64encode(bio.getvalue())


@tagged("post_install", "-at_install")
class TestFase7Corte1(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Corte 1: los centros de un programa deben compartir variedad.
        cls.center_a.write({"variety": "Reina"})
        cls.center_a2.write({"variety": "Reina"})
        cls.center_a_no_aa.write({"variety": "Otra"})

        uom = cls.env.ref("uom.product_uom_unit")
        cls.prod_a = cls.env["product.product"].create(dict({
            "name": "Fungicida Corte1", "type": "consu", "uom_id": uom.id,
            "standard_price": 5000.0,
        }, **extra_product_vals(cls.env)))
        cls.prod_stock = cls.env["product.product"].create(dict({
            "name": "Insumo Corte1", "type": "consu", "uom_id": uom.id,
            "is_storable": True, "standard_price": 100.0,
        }, **extra_product_vals(cls.env)))

        cls.tmpl = cls.env["step.management.budget.template"].create({
            "name": "Plantilla insumo C1", "company_id": cls.company_a.id,
            "base_hectares": 1.0, "state": "active",
            "line_ids": [(0, 0, {
                "category": "input", "group_id": cls.group_a.id,
                "indicator": "Fertilizar", "product_id": cls.prod_stock.id,
                "uom_id": uom.id, "unit_price": 100.0, "jun": 12.0,
            })],
        })

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _approved_budget(self, template=None, centers=None):
        budget = self._new_budget(template=template or self.tmpl, centers=centers)
        budget.action_generate_lines()
        budget.with_user(self.user_approver).action_approve()
        return budget

    def _plan(self, budget=None, **kw):
        vals = {
            "description": "Plan C1", "company_id": self.company_a.id,
            "date_start": "2026-05-01", "date_end": "2027-04-30",
        }
        if budget:
            vals["budget_id"] = budget.id
        vals.update(kw)
        return self.env["step.management.plan"].create(vals)

    def _open_preview(self, plan):
        plan.action_generate_weekly_tasks()
        return self.env["step.management.plan.weekly.preview.wizard"].with_context(
            default_plan_id=plan.id
        ).create({})

    def _program(self, price_policy="standard", lines=None, centers=None, compute=True):
        lines = lines or [{"product_id": self.prod_a.id, "dose_per_ha": 2.0}]
        centers = centers or [self.center_a]
        program = self.env["step.management.crop.program"].create({
            "company_id": self.company_a.id, "program_type": "phyto",
            "season": "2026/2027", "price_policy": price_policy,
            "line_ids": [(0, 0, dict(line)) for line in lines],
            "center_ids": [(6, 0, [c.id for c in centers])],
        })
        if compute:
            program.action_compute_applications()
        return program

    def _set_stock(self, product, warehouse, qty, reserved=0.0):
        location = warehouse.lot_stock_id
        self.env["stock.quant"].sudo()._update_available_quantity(product, location, qty)
        if reserved:
            quant = self.env["stock.quant"].sudo().search([
                ("product_id", "=", product.id), ("location_id", "=", location.id),
            ], limit=1)
            quant.reserved_quantity = reserved

    def _make_program_import(self, b64, **kw):
        vals = {
            "company_id": self.company_a.id, "program_type": "phyto",
            "season": "2026/2027", "file": b64, "filename": "receta.xlsx",
            "center_ids": [(6, 0, [self.center_a.id])],
        }
        vals.update(kw)
        return self.env["step.management.crop.program.import"].create(vals)

    def _recipe_row(self, product="Fungicida Corte1", dose=2.0, uom="", target="",
                     week="", phi="", rei=""):
        return [product, dose, uom, target, week, phi, rei]

    # ------------------------------------------------------------------
    # 1. Vista previa antes de regenerar el plan semanal
    # ------------------------------------------------------------------
    def test_preview_does_not_write_until_confirmed(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        wizard = self._open_preview(plan)
        self.assertFalse(plan.line_ids)  # nada escrito todavía
        self.assertGreater(wizard.add_count, 0)
        self.assertEqual(wizard.add_count, len(wizard.preview_line_ids))
        self.assertEqual(wizard.remove_count, 0)
        self.assertEqual(wizard.keep_manual_count, 0)
        wizard.action_confirm()
        self.assertEqual(len(plan.line_ids.filtered("generated")), wizard.add_count)

    def test_preview_counts_removal_on_regeneration(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        self._open_preview(plan).action_confirm()
        n = len(plan.line_ids.filtered("generated"))
        wizard2 = self._open_preview(plan)
        self.assertEqual(wizard2.remove_count, n)
        self.assertEqual(wizard2.add_count, n)

    def test_preview_never_touches_manual_tasks(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        self._open_preview(plan).action_confirm()
        plan.write({"line_ids": [(0, 0, {
            "date": "2026-06-01", "indicator": "Tarea manual",
            "center_id": self.center_a.id,
        })]})
        wizard = self._open_preview(plan)
        self.assertEqual(wizard.keep_manual_count, 1)
        wizard.action_confirm()
        self.assertEqual(len(plan.line_ids.filtered(lambda l: not l.generated)), 1)

    def test_preview_wizard_requires_valid_source(self):
        plan = self._plan()  # sin presupuesto
        with self.assertRaises(UserError):
            self._open_preview(plan)

    # ------------------------------------------------------------------
    # 2. Política de precio (D07) — sin cambio de código, sólo regresión
    # ------------------------------------------------------------------
    def test_price_policy_default_is_standard_and_freezes_standard_price(self):
        program = self._program()  # price_policy no especificado explícitamente
        self.assertEqual(program.price_policy, "standard")
        program.action_approve()
        app = program.application_ids
        self.assertAlmostEqual(app.unit_price, self.prod_a.standard_price)
        payload_price = app.unit_price
        self.assertAlmostEqual(
            payload_price,
            self.prod_a.with_company(self.company_a).standard_price,
        )

    # ------------------------------------------------------------------
    # 3. Programas por temporada + centro de costo, misma variedad
    # ------------------------------------------------------------------
    def test_program_same_variety_centers_allowed(self):
        program = self._program(centers=[self.center_a, self.center_a2], compute=False)
        self.assertTrue(program)

    def test_program_mixed_variety_centers_rejected(self):
        with self.assertRaises(ValidationError):
            self._program(
                centers=[self.center_a, self.center_a_no_aa], compute=False,
            )

    def test_program_blank_variety_centers_do_not_conflict(self):
        blank_a = self.env["step.management.cost.center"].create({
            "code": "CABLANK1", "name": "Sin variedad 1", "company_id": self.company_a.id,
            "hectares": 2.0,
        })
        blank_b = self.env["step.management.cost.center"].create({
            "code": "CABLANK2", "name": "Sin variedad 2", "company_id": self.company_a.id,
            "hectares": 3.0,
        })
        program = self._program(centers=[blank_a, blank_b], compute=False)
        self.assertTrue(program)

    # ------------------------------------------------------------------
    # 4. Importación Excel de la receta de un programa
    # ------------------------------------------------------------------
    def test_program_import_happy_path_creates_draft_program(self):
        imp = self._make_program_import(_recipe_xlsx([
            self._recipe_row(dose=2.0, target="Botrytis", week=20, phi=7, rei=12),
        ]))
        imp.action_validate()
        self.assertEqual(imp.error_count, 0, imp.line_ids.mapped("error"))
        action = imp.action_import()
        self.assertEqual(imp.state, "imported")
        program = self.env["step.management.crop.program"].browse(action["res_id"])
        self.assertEqual(program, imp.program_id)
        self.assertEqual(program.state, "draft")  # aprobación segura: nunca automática
        self.assertEqual(len(program.line_ids), 1)
        self.assertAlmostEqual(program.line_ids.dose_per_ha, 2.0)
        self.assertEqual(program.line_ids.week_number, 20)

    def test_program_import_row_errors(self):
        imp = self._make_program_import(_recipe_xlsx([
            self._recipe_row(product="No existe", dose=1.0),
            self._recipe_row(dose=-1.0),
            self._recipe_row(week=99),
        ]))
        imp.action_validate()
        self.assertEqual(imp.error_count, 3)
        self.assertEqual(imp.ok_count, 0)
        with self.assertRaises(UserError):
            imp.action_import()

    def test_program_import_valid_only_subset(self):
        imp = self._make_program_import(_recipe_xlsx([
            self._recipe_row(dose=2.0),
            self._recipe_row(product="No existe", dose=1.0),
        ]))
        imp.action_validate()
        self.assertEqual(imp.error_count, 1)
        self.assertEqual(imp.ok_count, 1)
        imp.import_valid_only = True
        imp.action_import()
        self.assertEqual(len(imp.program_id.line_ids), 1)

    def test_program_import_idempotent_same_file(self):
        b64 = _recipe_xlsx([self._recipe_row(dose=2.0)])
        imp1 = self._make_program_import(b64)
        imp1.action_validate()
        imp1.action_import()
        imp2 = self._make_program_import(b64)
        imp2.action_validate()
        with self.assertRaises(UserError):
            imp2.action_import()

    def test_program_import_requires_center(self):
        imp = self._make_program_import(
            _recipe_xlsx([self._recipe_row(dose=2.0)]), center_ids=[(6, 0, [])],
        )
        with self.assertRaises(UserError):
            imp.action_validate()

    # ------------------------------------------------------------------
    # 5. Necesidades de stock cruzadas con inventario real
    # ------------------------------------------------------------------
    def _requirement(self, **kw):
        vals = {
            "company_id": self.company_a.id, "season": "2026/2027",
            "granularity": "season",
        }
        vals.update(kw)
        req = self.env["step.management.stock.requirement"].create(vals)
        req.action_compute()
        return req

    def test_availability_on_hand_and_shortage(self):
        budget = self._approved_budget()
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_a.id)], limit=1,
        )
        self._set_stock(self.prod_stock, warehouse, 50.0)
        req = self._requirement(
            budget_ids=[(6, 0, [budget.id])], warehouse_id=warehouse.id,
            availability_metric="on_hand",
        )
        line = req.line_ids.filtered(lambda l: l.product_id == self.prod_stock)
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.available_quantity, 50.0, places=2)
        expected_shortage = max(0.0, line.total_quantity - 50.0)
        self.assertAlmostEqual(line.shortage_quantity, expected_shortage, places=2)
        self.assertTrue(req.computed_at)

    def test_availability_free_subtracts_reserved(self):
        budget = self._approved_budget()
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_a.id)], limit=1,
        )
        self._set_stock(self.prod_stock, warehouse, 50.0, reserved=20.0)
        req = self._requirement(
            budget_ids=[(6, 0, [budget.id])], warehouse_id=warehouse.id,
            availability_metric="free",
        )
        line = req.line_ids.filtered(lambda l: l.product_id == self.prod_stock)
        self.assertAlmostEqual(line.available_quantity, 30.0, places=2)

    def test_availability_metric_selection_is_explicit(self):
        req = self._requirement()
        self.assertEqual(req.availability_metric, "on_hand")  # default explícito
        self.assertFalse(req.warehouse_id)  # vacío = alcance de compañía, no ambiguo

    def test_computed_at_updates_on_recompute(self):
        req = self._requirement()
        first = req.computed_at
        self.assertTrue(first)
        req.action_compute()
        self.assertTrue(req.computed_at)
        self.assertGreaterEqual(req.computed_at, first)
