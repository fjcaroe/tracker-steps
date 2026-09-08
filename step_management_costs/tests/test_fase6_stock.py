from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_management_costs import ManagementCostsCommon, extra_product_vals


@tagged("post_install", "-at_install")
class TestFase6Stock(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # R4 (revisión post Corte 1): `action_approve` bloquea un programa
        # cuyos centros no tienen ninguna variedad informada.
        cls.center_a.write({"variety": "Reina"})
        uom = cls.env.ref("uom.product_uom_unit")
        cls.prod_input = cls.env["product.product"].create(dict({
            "name": "Insumo X", "type": "consu", "uom_id": uom.id,
        }, **extra_product_vals(cls.env)))
        cls.prod_labor = cls.env["product.product"].create(dict({
            "name": "Servicio Poda", "type": "consu", "uom_id": uom.id,
        }, **extra_product_vals(cls.env)))

        cls.tmpl = cls.env["step.management.budget.template"].create({
            "name": "Plantilla insumo", "company_id": cls.company_a.id,
            "base_hectares": 1.0, "state": "active",
            "line_ids": [
                (0, 0, {
                    "category": "input", "group_id": cls.group_a.id,
                    "indicator": "Fertilizar", "product_id": cls.prod_input.id,
                    "uom_id": uom.id, "unit_price": 100.0, "jun": 12.0,
                }),
                (0, 0, {
                    "category": "labor", "group_id": cls.group_a.id,
                    "indicator": "Poda", "product_id": cls.prod_labor.id,
                    "uom_id": uom.id, "unit_price": 50.0, "jul": 8.0,
                }),
            ],
        })
        cls.budget = cls.env["step.management.operational.budget"].create({
            "description": "Ppto insumo", "season": "2026/2027",
            "template_id": cls.tmpl.id, "company_id": cls.company_a.id,
            "allocation_ids": [(0, 0, {
                "center_id": cls.center_a.id, "hectares": cls.center_a.hectares,
            })],
        })
        cls.budget.action_generate_lines()
        cls.budget.with_user(cls.user_approver).action_approve()

        cls.program = cls._approved_program([{
            "product_id": cls.prod_input.id, "dose_per_ha": 5.0, "week_number": 23,
        }])

    @classmethod
    def _approved_program(cls, lines, program_type="fert", centers=None):
        centers = centers or [cls.center_a]

        def _line_vals(line):
            vals = dict(line)
            # R2 (revisión post Corte 1): la consolidación de necesidades de
            # stock exige UdM en la fuente para convertir a la del producto;
            # por defecto se toma la propia UdM del producto, igual que hace
            # el importador de recetas.
            if not vals.get("uom_id") and vals.get("product_id"):
                product = cls.env["product.product"].browse(vals["product_id"])
                vals["uom_id"] = product.uom_id.id
            return vals

        program = cls.env["step.management.crop.program"].create({
            "company_id": cls.company_a.id, "program_type": program_type,
            "season": "2026/2027",
            "line_ids": [(0, 0, _line_vals(line)) for line in lines],
            "center_ids": [(6, 0, [c.id for c in centers])],
        })
        program.action_compute_applications()
        program.with_user(cls.user_approver).action_approve()
        return program

    def _requirement(self, granularity="week", compute=True, **kw):
        vals = {
            "company_id": self.company_a.id, "season": "2026/2027",
            "granularity": granularity,
        }
        vals.update(kw)
        requirement = self.env["step.management.stock.requirement"].create(vals)
        if compute:
            requirement.action_compute()
        return requirement

    # ------------------------------------------------------------------
    def test_budget_week_reconciles_with_source(self):
        req = self._requirement("week")
        lines = req.line_ids.filtered(lambda l: l.product_id == self.prod_input)
        self.assertAlmostEqual(sum(lines.mapped("budget_quantity")), 120.0, places=2)
        self.assertTrue(all(l.period_key.startswith("W") for l in lines))

    def test_month_granularity_merges_budget_and_program(self):
        req = self._requirement("month")
        line = req.line_ids.filtered(
            lambda l: l.period_key == "jun" and l.product_id == self.prod_input
        )
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.budget_quantity, 120.0, places=2)
        self.assertAlmostEqual(line.program_quantity, 50.0, places=2)  # 5 dosis × 10 ha
        self.assertAlmostEqual(line.total_quantity, 170.0, places=2)

    def test_season_granularity_single_bucket(self):
        req = self._requirement("season")
        line = req.line_ids.filtered(lambda l: l.product_id == self.prod_input)
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.budget_quantity, 120.0, places=2)
        self.assertAlmostEqual(line.program_quantity, 50.0, places=2)

    def test_sources_not_double_counted(self):
        req = self._requirement("season")
        line = req.line_ids.filtered(lambda l: l.product_id == self.prod_input)
        self.assertGreater(line.budget_quantity, 0)
        self.assertGreater(line.program_quantity, 0)
        self.assertAlmostEqual(
            line.total_quantity, line.budget_quantity + line.program_quantity, places=4
        )

    def test_only_input_category_from_budget(self):
        req = self._requirement("season")
        self.assertFalse(req.line_ids.filtered(lambda l: l.product_id == self.prod_labor))
        self.assertTrue(req.line_ids.filtered(lambda l: l.product_id == self.prod_input))

    def test_only_approved_sources_count(self):
        draft_budget = self.env["step.management.operational.budget"].create({
            "description": "borrador", "season": "2026/2027",
            "template_id": self.tmpl.id, "company_id": self.company_a.id,
            "allocation_ids": [(0, 0, {
                "center_id": self.center_a2.id, "hectares": self.center_a2.hectares,
            })],
        })
        draft_budget.action_generate_lines()  # 'calculated', no aprobado
        req = self._requirement("season")
        line = req.line_ids.filtered(lambda l: l.product_id == self.prod_input)
        self.assertAlmostEqual(line.budget_quantity, 120.0, places=2)  # sólo el aprobado

    def test_program_without_week_goes_to_no_week_bucket(self):
        prog = self._approved_program([{
            "product_id": self.prod_input.id, "dose_per_ha": 2.0,
        }])
        req = self._requirement(
            "week", include_budgets=False, program_ids=[(6, 0, [prog.id])],
        )
        line = req.line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.period_key, "SIN-SEM")
        self.assertAlmostEqual(line.program_quantity, 20.0, places=2)

    def test_idempotent_recompute(self):
        req = self._requirement("week")
        count = len(req.line_ids)
        total = sum(req.line_ids.mapped("total_quantity"))
        req.action_compute()
        self.assertEqual(len(req.line_ids), count)
        self.assertAlmostEqual(sum(req.line_ids.mapped("total_quantity")), total, places=2)

    def test_two_companies_isolation(self):
        req = self._requirement("season")
        self.assertTrue(all(l.company_id == self.company_a for l in req.line_ids))

    def test_cross_company_source_rejected(self):
        prog_b = self.env["step.management.crop.program"].create({
            "company_id": self.company_b.id, "program_type": "fert",
            "season": "2026/2027",
            "line_ids": [(0, 0, {"product_id": self.prod_input.id, "dose_per_ha": 1.0})],
        })
        with self.assertRaises(ValidationError):
            self.env["step.management.stock.requirement"].create({
                "company_id": self.company_a.id, "season": "2026/2027",
                "program_ids": [(6, 0, [prog_b.id])],
            })

    def test_roles(self):
        req = self.env["step.management.stock.requirement"].with_user(
            self.user_operator
        ).create({
            "company_id": self.company_a.id, "season": "2026/2027",
            "granularity": "season",
        })
        req.with_user(self.user_operator).action_compute()
        self.assertEqual(req.state, "computed")
        with self.assertRaises(AccessError):
            self.env["step.management.stock.requirement"].with_user(
                self.user_readonly
            ).create({"company_id": self.company_a.id, "season": "x"})

    def test_line_sql_unique(self):
        req = self._requirement("season")
        line = req.line_ids[0]
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["step.management.stock.requirement.line"].create({
                    "requirement_id": req.id, "product_id": line.product_id.id,
                    "period_key": line.period_key,
                })
