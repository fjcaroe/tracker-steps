import hashlib
import json

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_management_costs import ManagementCostsCommon, extra_product_vals


@tagged("post_install", "-at_install")
class TestFase5Programs(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # R4 (revisión post Corte 1): `action_approve` bloquea un programa
        # cuyos centros no tienen ninguna variedad informada.
        cls.center_a.write({"variety": "Reina"})
        cls.center_a2.write({"variety": "Reina"})
        cls.prod_a = cls.env["product.product"].create(dict({
            "name": "Fungicida A", "type": "consu", "standard_price": 5000.0,
        }, **extra_product_vals(cls.env)))
        cls.prod_b = cls.env["product.product"].create(dict({
            "name": "Fertilizante B", "type": "consu", "standard_price": 800.0,
        }, **extra_product_vals(cls.env)))

    def _program(self, program_type="phyto", price_policy="standard",
                 lines=None, centers=None, compute=True, **kw):
        lines = lines or [{"product_id": self.prod_a.id, "dose_per_ha": 2.0}]
        centers = centers or [self.center_a]
        vals = {
            "company_id": self.company_a.id, "program_type": program_type,
            "season": "2026/2027", "price_policy": price_policy,
            "line_ids": [(0, 0, dict(line)) for line in lines],
            "center_ids": [(6, 0, [c.id for c in centers])],
        }
        vals.update(kw)
        program = self.env["step.management.crop.program"].create(vals)
        if compute:
            program.action_compute_applications()
        return program

    # ------------------------------------------------------------------
    # Amplificación por hectáreas (C2)
    # ------------------------------------------------------------------
    def test_amplify_by_hectares_phyto(self):
        program = self._program("phyto", lines=[
            {"product_id": self.prod_a.id, "dose_per_ha": 2.0},
        ])
        app = program.application_ids
        self.assertEqual(len(app), 1)
        self.assertAlmostEqual(app.hectares, 10.0)
        self.assertAlmostEqual(app.quantity, 20.0)  # 2 dosis/ha × 10 ha

    def test_amplify_by_hectares_fertilization_too(self):
        program = self._program("fert", lines=[
            {"product_id": self.prod_b.id, "dose_per_ha": 3.0},
        ])
        # C2: fertilización TAMBIÉN se amplifica por hectáreas
        self.assertAlmostEqual(program.application_ids.quantity, 30.0)

    def test_expansion_multi_center_and_idempotent(self):
        program = self._program(
            "phyto", centers=[self.center_a, self.center_a2],
            lines=[
                {"product_id": self.prod_a.id, "dose_per_ha": 1.0},
                {"product_id": self.prod_b.id, "dose_per_ha": 2.0},
            ],
        )
        self.assertEqual(len(program.application_ids), 4)  # 2 líneas × 2 centros
        count = len(program.application_ids)
        program.action_compute_applications()
        self.assertEqual(len(program.application_ids), count)

    # ------------------------------------------------------------------
    # Valorización (D07)
    # ------------------------------------------------------------------
    def test_valorization_standard_price(self):
        program = self._program("phyto", price_policy="standard", lines=[
            {"product_id": self.prod_a.id, "dose_per_ha": 2.0},
        ])
        program.action_approve()
        app = program.application_ids
        self.assertAlmostEqual(app.unit_price, 5000.0)
        self.assertAlmostEqual(app.amount, 100000.0)  # 20 × 5000
        self.assertIn("estándar", (app.price_source or "").lower())
        self.assertAlmostEqual(program.total_amount, 100000.0)

    def test_valorization_manual_price(self):
        program = self._program("phyto", price_policy="manual", lines=[
            {"product_id": self.prod_a.id, "dose_per_ha": 2.0, "manual_price": 7777.0},
        ])
        program.action_approve()
        self.assertAlmostEqual(program.application_ids.unit_price, 7777.0)
        self.assertAlmostEqual(program.application_ids.amount, 20.0 * 7777.0)

    def test_approval_snapshot_and_hash(self):
        program = self._program("phyto")
        program.action_approve()
        self.assertTrue(program.approval_snapshot)
        self.assertEqual(
            program.approval_hash,
            hashlib.sha256(program.approval_snapshot.encode("utf-8")).hexdigest(),
        )
        payload = json.loads(program.approval_snapshot)
        self.assertEqual(payload["revision"], 1)
        self.assertEqual(payload["program_type"], "phyto")
        self.assertAlmostEqual(payload["total_amount"], program.total_amount, places=2)
        self.assertEqual(len(payload["applications"]), 1)

    # ------------------------------------------------------------------
    # Inmutabilidad y revisiones
    # ------------------------------------------------------------------
    def test_approved_program_is_immutable(self):
        program = self._program("phyto")
        program.action_approve()
        with self.assertRaises(UserError):
            program.write({"season": "9999/9999"})
        with self.assertRaises(UserError):
            program.line_ids.write({"dose_per_ha": 1.0})
        with self.assertRaises(UserError):
            program.line_ids.unlink()
        with self.assertRaises(UserError):
            program.application_ids[0].write({"unit_price": 1.0})
        with self.assertRaises(UserError):
            program.application_ids[0].unlink()
        with self.assertRaises(UserError):
            program.unlink()

    def test_revision_flow_and_supersede(self):
        program = self._program("phyto")
        program.action_approve()
        with self.assertRaises(UserError):
            program._do_reopen("")
        revision = program._do_reopen("Cambio de dosis")
        self.assertEqual(program.state, "approved")
        self.assertEqual(revision.state, "draft")
        self.assertEqual(revision.revision, 2)
        self.assertEqual(revision.revision_of_id, program)
        self.assertEqual(len(revision.line_ids), len(program.line_ids))
        self.assertFalse(revision.application_ids)
        with self.assertRaises(UserError):
            program.action_new_revision()  # ya existe una sucesora activa
        revision.line_ids.write({"dose_per_ha": 4.0})
        revision.action_compute_applications()
        revision.action_approve()
        program.invalidate_recordset()
        self.assertEqual(program.state, "superseded")
        self.assertEqual(program.superseded_by_id, revision)
        self.assertAlmostEqual(revision.application_ids.quantity, 40.0)

    def test_duplicate_is_independent(self):
        program = self._program("phyto")
        program.action_approve()
        action = program.action_duplicate()
        dup = self.env["step.management.crop.program"].browse(action["res_id"])
        self.assertEqual(dup.state, "draft")
        self.assertEqual(dup.revision, 1)
        self.assertFalse(dup.revision_of_id)
        self.assertFalse(dup.application_ids)
        self.assertEqual(len(dup.line_ids), len(program.line_ids))
        self.assertNotEqual(dup.name, program.name)

    # ------------------------------------------------------------------
    # Roles / RPC / multicompañía / constraints
    # ------------------------------------------------------------------
    def test_roles_and_rpc(self):
        program = self.env["step.management.crop.program"].with_user(
            self.user_operator
        ).create({
            "company_id": self.company_a.id, "program_type": "phyto",
            "season": "2026/2027",
            "line_ids": [(0, 0, {"product_id": self.prod_a.id, "dose_per_ha": 2.0})],
            "center_ids": [(6, 0, [self.center_a.id])],
        })
        program.with_user(self.user_operator).action_compute_applications()
        self.assertTrue(program.application_ids)
        with self.assertRaises(UserError):
            program.with_user(self.user_operator).action_approve()
        with self.assertRaises(AccessError):
            self.env["step.management.crop.program"].with_user(
                self.user_readonly
            ).create({
                "company_id": self.company_a.id, "program_type": "phyto",
                "season": "x",
            })
        program.with_user(self.user_approver).action_approve()
        self.assertEqual(program.state, "approved")

    def test_cross_company_center_rejected(self):
        with self.assertRaises(ValidationError):
            self.env["step.management.crop.program"].create({
                "company_id": self.company_a.id, "program_type": "phyto",
                "season": "2026/2027",
                "line_ids": [(0, 0, {"product_id": self.prod_a.id, "dose_per_ha": 1.0})],
                "center_ids": [(6, 0, [self.center_b.id])],
            })

    def test_dose_and_week_constraints(self):
        with self.assertRaises(ValidationError):
            self._program("phyto", compute=False, lines=[
                {"product_id": self.prod_a.id, "dose_per_ha": -1.0},
            ])
        with self.assertRaises(ValidationError):
            self._program("phyto", compute=False, lines=[
                {"product_id": self.prod_a.id, "dose_per_ha": 1.0, "week_number": 60},
            ])

    def test_application_sql_unique_per_line_and_center(self):
        program = self._program("phyto")
        line = program.line_ids
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["step.management.crop.program.application"].create({
                    "program_id": program.id, "line_id": line.id,
                    "center_id": self.center_a.id, "hectares": 1.0,
                    "dose_per_ha": 1.0,
                })

    def test_phyto_phi_rei_carried_to_application(self):
        program = self._program("phyto", lines=[{
            "product_id": self.prod_a.id, "dose_per_ha": 2.0,
            "phi_days": 14, "rei_hours": 24, "target": "Botrytis",
        }])
        app = program.application_ids
        self.assertEqual(app.phi_days, 14)
        self.assertEqual(app.rei_hours, 24)
        self.assertEqual(app.target, "Botrytis")

    def test_fertilization_without_phi_rei_is_fine(self):
        program = self._program("fert", lines=[
            {"product_id": self.prod_b.id, "dose_per_ha": 3.0, "target": "Nitrógeno"},
        ])
        program.action_approve()
        self.assertEqual(program.state, "approved")
