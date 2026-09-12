import json

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools import mute_logger


def extra_company_vals(env):
    """V2 D: el entorno compartido de verificación puede tener otros
    módulos (ajenos a este addon) que agregan a `res.company` campos
    obligatorios sin un `default=` declarado en el propio campo Python (p.
    ej. un valor que normalmente sólo llega vía `ir.default`, mecanismo que
    Odoo omite mientras corre en modo instalación/actualización — que es
    justo cuando corren estas pruebas con `--test-enable`). Para no acoplar
    este fixture a esos módulos por nombre, se inspecciona `field.default`
    directamente (estático, no depende del contexto de ejecución, a
    diferencia de `default_get()`): cualquier campo obligatorio sin default
    de Python propio recibe aquí un valor mínimo neutro según su tipo. Si
    el entorno no tiene esos campos ajenos, ninguno cae en este caso y esta
    función no aporta nada."""
    Model = env["res.company"]
    vals = {}
    for name, field in Model._fields.items():
        if not field.required or field.default is not None or name == "name":
            continue
        if field.type in ("float", "monetary"):
            vals[name] = 0.0
        elif field.type == "integer":
            vals[name] = 0
        elif field.type == "boolean":
            vals[name] = False
        elif field.type == "selection":
            options = field.selection(Model) if callable(field.selection) else field.selection
            if options:
                vals[name] = options[0][0]
        elif field.type == "char":
            vals[name] = "-"
    return vals


def extra_product_vals(env):
    """V2 D: mismo criterio que `extra_analytic_account_vals`, aplicado a
    `product.product`/`product.template`. `step_hr` agrega allí
    `grupo_labor` (obligatorio, sin default) — se completa con un valor
    mínimo válido para que los fixtures de productos de las pruebas del
    núcleo sigan funcionando con el puente agrícola instalado. Sin
    `step_hr`, `_fields` no tiene la clave y esta función no hace nada."""
    Model = env["product.product"]
    field = Model._fields.get("grupo_labor")
    if not field or not field.required:
        return {}
    options = field.selection(Model) if callable(field.selection) else field.selection
    return {"grupo_labor": options[0][0]} if options else {}


def extra_analytic_account_vals(env, company):
    """V2 D: si un puente instalado junto a este addon (p. ej.
    `step_management_costs_agriculture` + `step_hr`) agrega campos
    obligatorios a `account.analytic.account` que el núcleo no conoce, los
    completa con un valor mínimo para que los fixtures de prueba
    compartidos sigan funcionando. No es un acoplamiento funcional con ese
    puente — sólo evita que un campo ajeno bloquee la cuenta analítica de
    prueba; sin el puente instalado, `_fields` no tiene esas claves y esta
    función no hace nada."""
    Model = env["account.analytic.account"]
    vals = {}
    if Model._fields.get("fundo_id") and Model._fields["fundo_id"].required:
        fundo = env["step.fundo"].create({
            "name": "MC Fundo (%s)" % company.name, "company_id": company.id,
        })
        vals["fundo_id"] = fundo.id
    for field_name, value in (
        ("type_costo", "fruta"), ("etapa_costo", "ope"), ("tipo_fruta", "conven"),
    ):
        field = Model._fields.get(field_name)
        if field and field.required:
            vals[field_name] = value
    return vals


class ManagementCostsCommon(TransactionCase):
    @classmethod
    def _extra_analytic_account_vals(cls, company):
        return extra_analytic_account_vals(cls.env, company)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.ref("base.main_company")
        cls.company_b = cls.env["res.company"].create(dict(
            {"name": "MC Company B"}, **extra_company_vals(cls.env),
        ))

        cls.plan = cls.env["account.analytic.plan"].create({"name": "MC Plan"})
        cls.aa_a = cls.env["account.analytic.account"].create(dict({
            "name": "MC Analytic A", "plan_id": cls.plan.id, "company_id": cls.company_a.id,
        }, **cls._extra_analytic_account_vals(cls.company_a)))
        cls.aa_b = cls.env["account.analytic.account"].create(dict({
            "name": "MC Analytic B", "plan_id": cls.plan.id, "company_id": cls.company_b.id,
        }, **cls._extra_analytic_account_vals(cls.company_b)))

        cls.group_a = cls.env["step.management.budget.group"].create({
            "code": "MOA", "name": "Mano de obra A", "company_id": cls.company_a.id,
        })
        cls.center_a = cls.env["step.management.cost.center"].create({
            "code": "CA01", "name": "Centro A", "company_id": cls.company_a.id,
            "hectares": 10.0, "analytic_account_id": cls.aa_a.id,
        })
        cls.center_a2 = cls.env["step.management.cost.center"].create({
            "code": "CA02", "name": "Centro A2", "company_id": cls.company_a.id,
            "hectares": 5.0, "analytic_account_id": cls.aa_a.id,
        })
        cls.center_a_no_aa = cls.env["step.management.cost.center"].create({
            "code": "CA03", "name": "Centro A sin cuenta", "company_id": cls.company_a.id,
            "hectares": 4.0,
        })
        cls.center_b = cls.env["step.management.cost.center"].create({
            "code": "CB01", "name": "Centro B", "company_id": cls.company_b.id,
            "hectares": 8.0, "analytic_account_id": cls.aa_b.id,
        })

        cls.template = cls._make_template("Plantilla mensual", {"jun": 12.0})
        cls.template_incomplete = cls._make_template(
            "Plantilla anual", {}, base_quantity=20.0,
        )

        common = {"company_id": cls.company_a.id, "company_ids": [(6, 0, [cls.company_a.id])]}
        cls.user_readonly = new_test_user(
            cls.env, login="mc_readonly",
            groups="step_management_costs.group_management_readonly", **common,
        )
        cls.user_operator = new_test_user(
            cls.env, login="mc_operator",
            groups="step_management_costs.group_management_user", **common,
        )
        cls.user_approver = new_test_user(
            cls.env, login="mc_approver",
            groups="step_management_costs.group_management_approver", **common,
        )

    @classmethod
    def _make_template(cls, name, months, base_quantity=0.0):
        return cls.env["step.management.budget.template"].create({
            "name": name, "company_id": cls.company_a.id, "base_hectares": 1.0,
            "state": "active",
            "line_ids": [(0, 0, {
                "category": "labor", "group_id": cls.group_a.id,
                "indicator": "Poda", "unit_price": 1000.0,
                "base_quantity": base_quantity, **months,
            })],
        })

    def _new_budget(self, template=None, centers=None):
        template = template or self.template
        centers = centers or [self.center_a]
        return self.env["step.management.operational.budget"].create({
            "description": "Presupuesto de prueba",
            "season": "2026/2027",
            "template_id": template.id,
            "company_id": self.company_a.id,
            "allocation_ids": [
                (0, 0, {"center_id": c.id, "hectares": c.hectares}) for c in centers
            ],
        })


class TestMultiCompany(ManagementCostsCommon):
    def test_check_company_rejects_cross_company_template(self):
        template_b = self.env["step.management.budget.template"].create({
            "name": "Plantilla B", "company_id": self.company_b.id,
            "base_hectares": 1.0, "state": "active",
        })
        with self.assertRaises(UserError):
            self.env["step.management.operational.budget"].create({
                "description": "cruzado", "season": "x",
                "company_id": self.company_a.id, "template_id": template_b.id,
            })

    def test_check_company_rejects_cross_company_center(self):
        with self.assertRaises(UserError):
            self._new_budget(centers=[self.center_b])

    def test_global_rule_isolates_centers(self):
        centers = self.env["step.management.cost.center"].with_user(self.user_operator).search([])
        self.assertIn(self.center_a, centers)
        self.assertNotIn(self.center_b, centers, "La regla global no aísla la compañía B")

    def test_related_company_id_populated(self):
        budget = self._new_budget()
        self.assertEqual(budget.allocation_ids.company_id, self.company_a)
        self.assertEqual(self.template.line_ids.company_id, self.company_a)


class TestBudgetIntegrity(ManagementCostsCommon):
    def test_budget_center_sql_unique(self):
        budget = self._new_budget()
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["step.management.budget.center"].create({
                    "budget_id": budget.id, "center_id": self.center_a.id, "hectares": 1.0,
                })

    def test_zero_hectares_rejected(self):
        budget = self._new_budget()
        with self.assertRaises(ValidationError):
            self.env["step.management.budget.center"].create({
                "budget_id": budget.id, "center_id": self.center_a2.id, "hectares": 0.0,
            })

    def test_generate_lines_idempotent(self):
        budget = self._new_budget()
        budget.action_generate_lines()
        folio, count = budget.name, budget.line_count
        budget.action_generate_lines()
        self.assertEqual(budget.name, folio, "El folio no debe reasignarse")
        self.assertEqual(budget.line_count, count, "Recalcular no debe duplicar líneas")

    def test_incomplete_distribution_blocks_approval(self):
        budget = self._new_budget(template=self.template_incomplete)
        budget.action_generate_lines()
        self.assertTrue(budget.line_ids)
        self.assertFalse(budget.line_ids.distribution_complete)
        self.assertEqual(budget.incomplete_line_count, len(budget.line_ids))
        with self.assertRaises(UserError):
            budget.with_user(self.user_approver).action_approve()

    def test_monthly_distribution_constraint(self):
        budget = self._new_budget()
        budget.action_generate_lines()
        line = budget.line_ids
        self.assertTrue(line.distribution_complete)
        with self.assertRaises(ValidationError):
            line.month_ids[0].quantity = line.month_ids[0].quantity + 5.0

    def test_complete_distribution_allows_approval(self):
        budget = self._new_budget()
        budget.action_generate_lines()
        budget.with_user(self.user_approver).action_approve()
        self.assertEqual(budget.state, "approved")


class TestRolesAndTransitions(ManagementCostsCommon):
    def test_operator_cannot_approve_even_by_rpc(self):
        budget = self._new_budget()
        budget.action_generate_lines()
        with self.assertRaises(UserError):
            budget.with_user(self.user_operator).action_approve()
        # llamada directa al método público (equivalente RPC)
        with self.assertRaises(UserError):
            budget.with_user(self.user_operator).action_approve()

    def test_readonly_cannot_write(self):
        budget = self._new_budget()
        with self.assertRaises(Exception):
            budget.with_user(self.user_readonly).write({"description": "x"})

    def test_approve_requires_analytic_account(self):
        budget = self._new_budget(centers=[self.center_a_no_aa])
        budget.action_generate_lines()
        with self.assertRaises(UserError):
            budget.with_user(self.user_approver).action_approve()

    def test_approve_wrong_state(self):
        budget = self._new_budget()  # draft, sin calcular
        with self.assertRaises(UserError):
            budget.with_user(self.user_approver).action_approve()


class TestImmutabilityAndSnapshot(ManagementCostsCommon):
    def _approved_budget(self):
        budget = self._new_budget()
        budget.action_generate_lines()
        budget.with_user(self.user_approver).action_approve()
        return budget

    def test_header_frozen_after_approval(self):
        budget = self._approved_budget()
        with self.assertRaises(UserError):
            budget.write({"description": "cambio prohibido"})
        with self.assertRaises(UserError):
            budget.write({"season": "9999/9999"})

    def test_detail_frozen_after_approval(self):
        budget = self._approved_budget()
        with self.assertRaises(UserError):
            budget.line_ids[0].write({"quantity": 999.0})
        with self.assertRaises(UserError):
            budget.line_ids[0].unlink()

    def test_unlink_blocked_after_approval(self):
        budget = self._approved_budget()
        with self.assertRaises(UserError):
            budget.with_user(self.user_approver).unlink()

    def test_snapshot_and_hash(self):
        import hashlib
        budget = self._approved_budget()
        self.assertTrue(budget.approval_snapshot)
        self.assertTrue(budget.approved_by_id)
        self.assertTrue(budget.approved_at)
        payload = json.loads(budget.approval_snapshot)
        self.assertEqual(payload["revision"], 1)
        self.assertEqual(
            budget.approval_hash,
            hashlib.sha256(budget.approval_snapshot.encode("utf-8")).hexdigest(),
        )

    def test_reopen_requires_reason(self):
        budget = self._approved_budget()
        with self.assertRaises(UserError):
            budget._do_reopen("")
        revision = budget._do_reopen("Corrección de tarifas")
        self.assertEqual(budget.state, "approved")
        self.assertEqual(revision.state, "draft")
        self.assertEqual(revision.reopen_reason, "Corrección de tarifas")
        self.assertEqual(len(revision.line_ids), len(budget.line_ids))
        with self.assertRaises(UserError):
            budget.write({"description": "corregido"})
        revision.write({"description": "corregido"})

    def test_new_revision_supersedes_on_approval(self):
        budget = self._approved_budget()
        action = budget.action_new_revision()
        rev2 = self.env["step.management.operational.budget"].browse(action["res_id"])
        self.assertEqual(rev2.revision, 2)
        self.assertEqual(rev2.revision_of_id, budget)
        self.assertEqual(rev2.state, "draft")
        rev2.action_generate_lines()
        rev2.with_user(self.user_approver).action_approve()
        budget.invalidate_recordset()
        self.assertEqual(budget.state, "superseded")
        self.assertEqual(budget.superseded_by_id, rev2)


class TestHistoricalCost(ManagementCostsCommon):
    def test_locked_blocks_non_manager(self):
        cost = self.env["step.management.historical.cost"].create({
            "name": "Gasto externo", "company_id": self.company_a.id,
            "date": "2025-06-30", "center_id": self.center_a.id,
            "origin": "external", "actual_amount": 1000.0, "locked": True,
        })
        with self.assertRaises(UserError):
            cost.with_user(self.user_operator).write({"actual_amount": 2000.0})
        with self.assertRaises(UserError):
            cost.with_user(self.user_operator).unlink()
        # el administrador sí puede
        cost.write({"actual_amount": 2000.0})

    def test_variance_percent_from_totals(self):
        cost = self.env["step.management.historical.cost"].create({
            "name": "x", "company_id": self.company_a.id, "date": "2025-06-30",
            "center_id": self.center_a.id, "budget_amount": 1000.0, "actual_amount": 1200.0,
        })
        self.assertAlmostEqual(cost.variance, 200.0)
        self.assertAlmostEqual(cost.variance_percent, 20.0)
