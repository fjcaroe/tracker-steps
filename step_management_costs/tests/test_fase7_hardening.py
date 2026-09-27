"""Revisión de `18.0.13.0.0` antes del Corte 2 (R1-R5,
`REVISION_CORTE1_Y_CONTINUACION_CLAUDE_CORTE2_2026-09-04.md`):

- R1: contrato de huella para la vista previa semanal (no reescribir algo
  distinto de lo mostrado; el gate de estado también corre por RPC directo);
- R2: normalizar UdM antes de consolidar necesidades de stock;
- R3: faltante acumulado cronológico (no repetir la misma foto de
  disponibilidad en cada período);
- R4: coherencia completa de variedad en programas fito/ferti;
- R5: importador Excel de programas más estricto (enteros, dosis cero,
  idempotencia por intención completa).

R6 es sólo documentación (`DECISION_LOG.md`), sin código ni pruebas.
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
class TestFase7Hardening(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.center_a.write({"variety": "Reina"})
        cls.center_a2.write({"variety": "Reina"})
        cls.center_a_no_aa.write({"variety": "Otra"})

        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.uom_g = cls.env.ref("uom.product_uom_gram")
        cls.uom_l = cls.env.ref("uom.product_uom_litre")

        cls.prod_a = cls.env["product.product"].create(dict({
            "name": "Fungicida Hardening", "type": "consu", "uom_id": cls.uom_unit.id,
            "standard_price": 5000.0,
        }, **extra_product_vals(cls.env)))
        cls.prod_stock = cls.env["product.product"].create(dict({
            "name": "Insumo Hardening", "type": "consu", "uom_id": cls.uom_kg.id,
            "is_storable": True, "standard_price": 100.0,
        }, **extra_product_vals(cls.env)))

        # base_hectares = las del centro por defecto (`center_a`), para que
        # `action_generate_lines` no reescale las cantidades (factor 1:1) y
        # los números de los tests de R2/R3 sean los mismos que se piden.
        cls.tmpl = cls.env["step.management.budget.template"].create({
            "name": "Plantilla insumo Hardening", "company_id": cls.company_a.id,
            "base_hectares": cls.center_a.hectares, "state": "active",
            "line_ids": [(0, 0, {
                "category": "input", "group_id": cls.group_a.id,
                "indicator": "Fertilizar", "product_id": cls.prod_stock.id,
                "uom_id": cls.uom_kg.id, "unit_price": 100.0, "jun": 12.0,
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
            "description": "Plan Hardening", "company_id": self.company_a.id,
            "date_start": "2026-05-01", "date_end": "2027-04-30",
        }
        if budget:
            vals["budget_id"] = budget.id
        vals.update(kw)
        return self.env["step.management.plan"].create(vals)

    def _open_preview(self, plan):
        return self.env["step.management.plan.weekly.preview.wizard"].with_context(
            default_plan_id=plan.id
        ).create({})

    def _program(self, price_policy="standard", lines=None, centers=None,
                 variety=None, compute=True):
        lines = lines or [{"product_id": self.prod_a.id, "dose_per_ha": 2.0}]
        centers = centers or [self.center_a]
        vals = {
            "company_id": self.company_a.id, "program_type": "phyto",
            "season": "2026/2027", "price_policy": price_policy,
            "line_ids": [(0, 0, dict(line)) for line in lines],
            "center_ids": [(6, 0, [c.id for c in centers])],
        }
        if variety is not None:
            vals["variety"] = variety
        program = self.env["step.management.crop.program"].create(vals)
        if compute:
            program.action_compute_applications()
        return program

    def _make_program_import(self, b64, **kw):
        vals = {
            "company_id": self.company_a.id, "program_type": "phyto",
            "season": "2026/2027", "file": b64, "filename": "receta.xlsx",
            "center_ids": [(6, 0, [self.center_a.id])],
        }
        vals.update(kw)
        return self.env["step.management.crop.program.import"].create(vals)

    def _recipe_row(self, product="Fungicida Hardening", dose=2.0, uom="", target="",
                     week="", phi="", rei=""):
        return [product, dose, uom, target, week, phi, rei]

    def _set_stock(self, product, warehouse, qty, reserved=0.0):
        location = warehouse.lot_stock_id
        self.env["stock.quant"].sudo()._update_available_quantity(product, location, qty)
        if reserved:
            quant = self.env["stock.quant"].sudo().search([
                ("product_id", "=", product.id), ("location_id", "=", location.id),
            ], limit=1)
            quant.reserved_quantity = reserved

    def _requirement(self, **kw):
        vals = {
            "company_id": self.company_a.id, "season": "2026/2027",
            "granularity": "week",
        }
        vals.update(kw)
        req = self.env["step.management.stock.requirement"].create(vals)
        req.action_compute()
        return req

    # ------------------------------------------------------------------
    # R1 — contrato de huella de la vista previa semanal
    # ------------------------------------------------------------------
    def test_r1_confirm_without_changes_applies_shown_commands(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        wizard = self._open_preview(plan)
        self.assertTrue(wizard.fingerprint)
        wizard.action_confirm()
        self.assertEqual(len(plan.line_ids.filtered("generated")), wizard.add_count)

    def test_r1_budget_changed_after_preview_blocks_confirm(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        wizard = self._open_preview(plan)
        # el presupuesto cambia después de abrir la vista previa: se crea
        # una revisión con más hectáreas asignadas al mismo centro.
        revision = budget._do_reopen("Cambio de hectáreas")
        revision.allocation_ids.write({"hectares": 99.0})
        revision.action_generate_lines()
        revision.with_user(self.user_approver).action_approve()
        plan.budget_id = revision
        with self.assertRaises(UserError):
            wizard.action_confirm()
        self.assertFalse(plan.line_ids)

    def test_r1_plan_state_changed_after_preview_blocks_confirm(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        wizard = self._open_preview(plan)
        plan.action_plan()  # sigue siendo "planned", válido...
        plan.action_start()  # ...pero "in_progress" ya no lo es
        with self.assertRaises(UserError):
            wizard.action_confirm()

    def test_r1_wizard_via_direct_rpc_enforces_state_gate(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        plan.action_plan()
        plan.action_start()  # estado no válido para generar tareas
        with self.assertRaises(UserError):
            self.env["step.management.plan.weekly.preview.wizard"].with_context(
                default_plan_id=plan.id
            ).create({})

    def test_r1_other_company_blocked(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        plan_b = self._plan(company_id=self.company_b.id)
        with self.assertRaises(ValidationError):
            plan_b.budget_id = budget

    def test_r1_manual_tasks_untouched_across_confirm(self):
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

    def test_r1_readonly_user_cannot_confirm(self):
        budget = self._approved_budget()
        plan = self._plan(budget=budget)
        wizard = self._open_preview(plan)
        with self.assertRaises(Exception):
            wizard.with_user(self.user_readonly).action_confirm()

    # ------------------------------------------------------------------
    # R2 — normalizar UdM antes de consolidar necesidades de stock
    # ------------------------------------------------------------------
    def test_r2_budget_kg_and_program_g_consolidate_converted(self):
        budget = self._approved_budget()  # tmpl: jun=12.0 kg de prod_stock
        program = self._program(
            lines=[{
                "product_id": self.prod_stock.id, "dose_per_ha": 2000.0,
                "uom_id": self.uom_g.id,
            }],
            centers=[self.center_a],  # 10 ha → 20000 g = 20 kg
        )
        program.action_approve()
        req = self._requirement(
            granularity="season",
            budget_ids=[(6, 0, [budget.id])], program_ids=[(6, 0, [program.id])],
        )
        line = req.line_ids.filtered(lambda l: l.product_id == self.prod_stock)
        self.assertEqual(len(line), 1)
        self.assertEqual(line.uom_id, self.uom_kg)
        self.assertAlmostEqual(line.budget_quantity, 12.0, places=2)
        self.assertAlmostEqual(line.program_quantity, 20.0, places=2)  # 20000 g → 20 kg

    def test_r2_incompatible_category_raises(self):
        budget = self._approved_budget()
        program = self._program(
            lines=[{
                "product_id": self.prod_stock.id, "dose_per_ha": 1.0,
                "uom_id": self.uom_l.id,  # volumen, incompatible con kg
            }],
            centers=[self.center_a],
        )
        program.action_approve()
        req = self.env["step.management.stock.requirement"].create({
            "company_id": self.company_a.id, "season": "2026/2027",
            "granularity": "season",
            "budget_ids": [(6, 0, [budget.id])],
            "program_ids": [(6, 0, [program.id])],
        })
        with self.assertRaises(UserError):
            req.action_compute()

    def test_r2_import_defaults_uom_to_product_uom(self):
        imp = self._make_program_import(_recipe_xlsx([
            self._recipe_row(dose=2.0),  # sin UdM en el Excel
        ]))
        imp.action_validate()
        self.assertEqual(imp.error_count, 0, imp.line_ids.mapped("error"))
        imp.action_import()
        self.assertEqual(imp.program_id.line_ids.uom_id, self.prod_a.uom_id)

    def test_r2_import_uom_incompatible_with_product_errors(self):
        imp = self._make_program_import(_recipe_xlsx([
            self._recipe_row(dose=2.0, uom=self.uom_l.name),  # prod_a es "Unidades"
        ]))
        imp.action_validate()
        self.assertEqual(imp.error_count, 1)
        self.assertIn("categoría", imp.line_ids.error)

    # ------------------------------------------------------------------
    # R3 — faltante acumulado cronológico
    # ------------------------------------------------------------------
    def _two_month_budget(self, jun=60.0, jul=60.0, product=None):
        product = product or self.prod_stock
        # base_hectares = las del centro por defecto, para que
        # `action_generate_lines` no reescale las cantidades (factor 1:1) y
        # los números del test sean los mismos que se piden aquí.
        tmpl = self.env["step.management.budget.template"].create({
            "name": "Plantilla dos meses %s" % product.name,
            "company_id": self.company_a.id, "base_hectares": self.center_a.hectares,
            "state": "active",
            "line_ids": [(0, 0, {
                "category": "input", "group_id": self.group_a.id,
                "indicator": "Fert", "product_id": product.id,
                "uom_id": product.uom_id.id, "unit_price": 10.0,
                "jun": jun, "jul": jul,
            })],
        })
        return self._approved_budget(template=tmpl)

    def test_r3_cumulative_shortage_across_two_periods(self):
        budget = self._two_month_budget(jun=60.0, jul=60.0)
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_a.id)], limit=1,
        )
        self._set_stock(self.prod_stock, warehouse, 100.0)
        req = self._requirement(
            granularity="month", warehouse_id=warehouse.id,
            budget_ids=[(6, 0, [budget.id])], include_programs=False,
        )
        lines = req.line_ids.sorted(key=lambda l: l.period_index)
        self.assertEqual(len(lines), 2)
        # mayo→abril: junio (índice 2) antes que julio (índice 3)
        self.assertLess(lines[0].period_index, lines[1].period_index)
        self.assertAlmostEqual(lines[0].shortage_quantity, 0.0, places=2)
        self.assertAlmostEqual(lines[1].shortage_quantity, 20.0, places=2)

    def test_r3_multiple_products_do_not_interfere(self):
        prod2 = self.env["product.product"].create(dict({
            "name": "Insumo Hardening 2", "type": "consu", "uom_id": self.uom_kg.id,
            "is_storable": True, "standard_price": 50.0,
        }, **extra_product_vals(self.env)))
        budget1 = self._two_month_budget(jun=60.0, jul=60.0, product=self.prod_stock)
        tmpl2 = self.env["step.management.budget.template"].create({
            "name": "Plantilla prod2", "company_id": self.company_a.id,
            "base_hectares": self.center_a.hectares, "state": "active",
            "line_ids": [(0, 0, {
                "category": "input", "group_id": self.group_a.id,
                "indicator": "Fert 2", "product_id": prod2.id,
                "uom_id": prod2.uom_id.id, "unit_price": 10.0,
                "jun": 10.0, "jul": 10.0,
            })],
        })
        budget2 = self._approved_budget(template=tmpl2)
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_a.id)], limit=1,
        )
        self._set_stock(self.prod_stock, warehouse, 100.0)
        self._set_stock(prod2, warehouse, 5.0)  # insuficiente desde el inicio
        req = self._requirement(
            granularity="month", warehouse_id=warehouse.id,
            budget_ids=[(6, 0, [budget1.id, budget2.id])], include_programs=False,
        )
        lines1 = req.line_ids.filtered(
            lambda l: l.product_id == self.prod_stock
        ).sorted(key=lambda l: l.period_index)
        lines2 = req.line_ids.filtered(
            lambda l: l.product_id == prod2
        ).sorted(key=lambda l: l.period_index)
        self.assertAlmostEqual(lines1[0].shortage_quantity, 0.0, places=2)
        self.assertAlmostEqual(lines1[1].shortage_quantity, 20.0, places=2)
        # prod2 insuficiente desde la primera semana; no se contamina con prod_stock
        self.assertAlmostEqual(lines2[0].shortage_quantity, 5.0, places=2)
        self.assertAlmostEqual(lines2[1].shortage_quantity, 10.0, places=2)

    def test_r3_negative_stock_treated_as_zero_available(self):
        budget = self._two_month_budget(jun=60.0, jul=60.0)
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", self.company_a.id)], limit=1,
        )
        # existencia negativa (p. ej. un ajuste de inventario aún no
        # regularizado): se trata como 0 disponible, nunca como crédito.
        self.env["stock.quant"].sudo().create({
            "product_id": self.prod_stock.id,
            "location_id": warehouse.lot_stock_id.id,
            "quantity": -10.0,
        })
        req = self._requirement(
            granularity="month", warehouse_id=warehouse.id,
            budget_ids=[(6, 0, [budget.id])], include_programs=False,
        )
        lines = req.line_ids.sorted(key=lambda l: l.period_index)
        self.assertAlmostEqual(lines[0].available_quantity, -10.0, places=2)
        self.assertAlmostEqual(lines[0].shortage_quantity, 60.0, places=2)
        self.assertAlmostEqual(lines[1].shortage_quantity, 60.0, places=2)

    # ------------------------------------------------------------------
    # R4 — coherencia completa de variedad
    # ------------------------------------------------------------------
    def test_r4_case_and_whitespace_do_not_conflict(self):
        c1 = self.env["step.management.cost.center"].create({
            "code": "R4C1", "name": "R4 centro 1", "company_id": self.company_a.id,
            "hectares": 2.0, "variety": " reina ",
        })
        c2 = self.env["step.management.cost.center"].create({
            "code": "R4C2", "name": "R4 centro 2", "company_id": self.company_a.id,
            "hectares": 3.0, "variety": "REINA",
        })
        program = self._program(centers=[c1, c2], compute=False)
        self.assertTrue(program)

    def test_r4_header_variety_mismatch_rejected(self):
        with self.assertRaises(ValidationError):
            self._program(centers=[self.center_a], variety="Otra", compute=False)

    def test_r4_mixed_blank_and_informed_centers_rejected(self):
        blank = self.env["step.management.cost.center"].create({
            "code": "R4C3", "name": "R4 centro sin variedad",
            "company_id": self.company_a.id, "hectares": 2.0,
        })
        with self.assertRaises(ValidationError):
            self._program(centers=[self.center_a, blank], compute=False)

    def test_r4_all_blank_saves_draft_but_blocks_approval(self):
        b1 = self.env["step.management.cost.center"].create({
            "code": "R4C4", "name": "R4 blanco 1", "company_id": self.company_a.id,
            "hectares": 2.0,
        })
        b2 = self.env["step.management.cost.center"].create({
            "code": "R4C5", "name": "R4 blanco 2", "company_id": self.company_a.id,
            "hectares": 3.0,
        })
        program = self._program(centers=[b1, b2])  # compute=True por defecto
        self.assertEqual(program.state, "draft")
        with self.assertRaises(UserError):
            program.action_approve()

    def test_r4_import_infers_header_variety_from_centers(self):
        imp = self._make_program_import(
            _recipe_xlsx([self._recipe_row(dose=2.0)]),
            center_ids=[(6, 0, [self.center_a.id])],  # variedad "Reina"
        )
        imp.action_validate()
        imp.action_import()
        self.assertEqual(imp.program_id.variety, "Reina")

    # ------------------------------------------------------------------
    # R5 — endurecer el importador Excel
    # ------------------------------------------------------------------
    def test_r5_non_integer_week_is_row_error(self):
        imp = self._make_program_import(_recipe_xlsx([
            self._recipe_row(dose=2.0, week=20.5),
        ]))
        imp.action_validate()
        self.assertEqual(imp.error_count, 1)
        self.assertIn("entero", imp.line_ids.error)

    def test_r5_non_integer_phi_is_row_error(self):
        imp = self._make_program_import(_recipe_xlsx([
            self._recipe_row(dose=2.0, phi=7.5),
        ]))
        imp.action_validate()
        self.assertEqual(imp.error_count, 1)
        self.assertIn("entero", imp.line_ids.error)

    def test_r5_non_integer_rei_is_row_error(self):
        imp = self._make_program_import(_recipe_xlsx([
            self._recipe_row(dose=2.0, rei=12.5),
        ]))
        imp.action_validate()
        self.assertEqual(imp.error_count, 1)
        self.assertIn("entero", imp.line_ids.error)

    def test_r5_zero_dose_imports_draft_but_blocks_approval(self):
        imp = self._make_program_import(_recipe_xlsx([
            self._recipe_row(dose=0.0),
        ]))
        imp.action_validate()
        self.assertEqual(imp.error_count, 0, imp.line_ids.mapped("error"))
        imp.action_import()
        program = imp.program_id
        self.assertEqual(program.state, "draft")
        program.action_compute_applications()
        with self.assertRaises(UserError):
            program.action_approve()

    def test_r5_same_file_two_seasons_both_succeed(self):
        b64 = _recipe_xlsx([self._recipe_row(dose=2.0)])
        imp1 = self._make_program_import(b64, season="2026/2027")
        imp1.action_validate()
        imp1.action_import()
        imp2 = self._make_program_import(b64, season="2027/2028")
        imp2.action_validate()
        imp2.action_import()  # no debe bloquearse: distinta temporada
        self.assertEqual(imp2.state, "imported")

    def test_r5_same_intent_repeated_blocked(self):
        b64 = _recipe_xlsx([self._recipe_row(dose=2.0)])
        imp1 = self._make_program_import(b64)
        imp1.action_validate()
        imp1.action_import()
        imp2 = self._make_program_import(b64)
        imp2.action_validate()
        with self.assertRaises(UserError):
            imp2.action_import()
