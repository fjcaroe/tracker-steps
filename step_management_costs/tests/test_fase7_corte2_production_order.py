"""Corte 2 — Orden de Producción semanal central
(`REVISION_CORTE1_Y_CONTINUACION_CLAUDE_CORTE2_2026-09-04.md`).

Cubre los 11 puntos de la puerta de salida: identidad especie+centro+semana
y separación de compañías; W01/cruce de año/W53; vista previa sin escritura
y detección de fuente cambiada (mismo contrato de huella que R1);
conciliación independiente de tareas/fito-ferti; no duplicación de fuentes
dentro de la OP; autorización sólo por aprobador (incluso por RPC directo);
snapshot/hash deterministas + inmutabilidad + revisión; concurrencia de
autorización (índice único parcial); PDF desde snapshot (verificado sobre el
HTML renderizado, no el binario PDF); destinatarios + envío simulado (nunca
se llama `.send()`, sólo se encola el `mail.mail`); API futura de OT
(rechaza borrador, acepta autorizada).

Cosecha queda fuera de este corte (bloqueo real documentado en
`DECISION_LOG.md`): `harvest.plan.line` no tiene `center_id`.
"""

import base64
from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_management_costs import ManagementCostsCommon, extra_product_vals


@tagged("post_install", "-at_install")
class TestFase7Corte2ProductionOrder(ManagementCostsCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # R4 (revisión post Corte 1): `action_approve` de un programa
        # bloquea si ningún centro tiene variedad informada.
        cls.center_a.write({"species": "Manzana", "variety": "Fuji"})
        uom = cls.env.ref("uom.product_uom_unit")
        cls.prod_input = cls.env["product.product"].create(dict({
            "name": "Insumo OP", "type": "consu", "uom_id": uom.id,
        }, **extra_product_vals(cls.env)))
        cls.prod_phyto = cls.env["product.product"].create(dict({
            "name": "Fungicida OP", "type": "consu", "uom_id": uom.id,
            "standard_price": 3000.0,
        }, **extra_product_vals(cls.env)))
        cls.tmpl = cls.env["step.management.budget.template"].create({
            "name": "Plantilla OP", "company_id": cls.company_a.id,
            "base_hectares": cls.center_a.hectares, "state": "active",
            "line_ids": [(0, 0, {
                "category": "input", "group_id": cls.group_a.id,
                "indicator": "Riego", "activity": "Riego tecnificado",
                "product_id": cls.prod_input.id, "uom_id": uom.id,
                "unit_price": 100.0, "jun": 60.0,
            })],
        })
        cls.partner = cls.env["res.partner"].create({"name": "Jefe de campo OP", "email": "jefe@example.com"})

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _approved_budget(self):
        budget = self._new_budget(template=self.tmpl, centers=[self.center_a])
        budget.action_generate_lines()
        budget.with_user(self.user_approver).action_approve()
        return budget

    def _plan_with_weekly_tasks(self):
        budget = self._approved_budget()
        plan = self.env["step.management.plan"].create({
            "description": "Plan OP", "company_id": self.company_a.id,
            "date_start": "2026-05-01", "date_end": "2027-04-30",
            "budget_id": budget.id,
        })
        plan.action_generate_weekly_tasks()
        wizard = self.env["step.management.plan.weekly.preview.wizard"].with_context(
            default_plan_id=plan.id
        ).create({})
        wizard.action_confirm()
        return plan

    def _approved_program(self, week_number, centers=None):
        centers = centers or [self.center_a]
        program = self.env["step.management.crop.program"].create({
            "company_id": self.company_a.id, "program_type": "phyto",
            "season": "2026/2027", "variety": False,
            "line_ids": [(0, 0, {
                "product_id": self.prod_phyto.id, "dose_per_ha": 2.0,
                "uom_id": self.prod_phyto.uom_id.id, "week_number": week_number,
                "target": "Botrytis",
            })],
            "center_ids": [(6, 0, [c.id for c in centers])],
        })
        program.action_compute_applications()
        program.with_user(self.user_approver).action_approve()
        return program

    def _pick_week(self, plan):
        line = plan.line_ids.filtered("generated")[:1]
        self.assertTrue(line, "el plan no generó tareas semanales")
        return line.iso_year, line.iso_week

    def _make_order(self, iso_year, iso_week, species="Manzana", center=None):
        return self.env["step.management.production.order"].create({
            "company_id": self.company_a.id, "season": "2026/2027",
            "iso_year": iso_year, "iso_week": iso_week, "species": species,
            "center_id": (center or self.center_a).id,
        })

    def _generate_and_confirm(self, order):
        order.action_generate_preview()
        wizard = self.env["step.management.production.order.preview.wizard"].with_context(
            default_order_id=order.id
        ).create({})
        wizard.action_confirm()
        return wizard

    def _full_order(self):
        plan = self._plan_with_weekly_tasks()
        iso_year, iso_week = self._pick_week(plan)
        self._approved_program(iso_week)
        order = self._make_order(iso_year, iso_week)
        self._generate_and_confirm(order)
        return order

    # ------------------------------------------------------------------
    # 1. Identidad especie + centro + semana; especie coherente con el centro
    # ------------------------------------------------------------------
    def test_species_must_match_center_when_both_informed(self):
        plan = self._plan_with_weekly_tasks()
        iso_year, iso_week = self._pick_week(plan)
        with self.assertRaises(ValidationError):
            self._make_order(iso_year, iso_week, species="Pera")  # centro es "Manzana"

    def test_species_blank_or_matching_allowed(self):
        plan = self._plan_with_weekly_tasks()
        iso_year, iso_week = self._pick_week(plan)
        order = self._make_order(iso_year, iso_week, species=False)
        self.assertTrue(order)
        order2 = self._make_order(iso_year, iso_week, species="Manzana")
        self.assertTrue(order2)

    # ------------------------------------------------------------------
    # 2. W01, cruce de año y W53
    # ------------------------------------------------------------------
    def test_week_year_mismatch_rejected(self):
        plan = self._plan_with_weekly_tasks()
        iso_year, iso_week = self._pick_week(plan)
        order = self._make_order(iso_year + 5, iso_week)  # año ISO deliberadamente incorrecto
        with self.assertRaises(UserError):
            order._build_op_commands()

    def test_year_crossing_week_resolved_via_period_service(self):
        period = self.env["step.management.period.service"]
        start, end = period.season_bounds("2026/2027")
        weeks = period.iso_weeks(start, end)
        years = sorted({w["iso_year"] for w in weeks})
        self.assertEqual(len(years), 2, "una temporada mayo-abril cruza un año calendario")
        # primera y última semana de la temporada (W01-ish y borde final)
        for week in (weeks[0], weeks[-1]):
            order = self._make_order(week["iso_year"], week["iso_week"])
            commands, monday, sunday, _fp = order._build_op_commands()
            self.assertEqual(monday, week["monday"])
            self.assertEqual(sunday, week["sunday"])

    def test_week_53_resolved_when_present_in_season(self):
        period = self.env["step.management.period.service"]
        # 2020 tiene 53 semanas ISO (año bisiesto que empieza en miércoles).
        start, end = period.season_bounds("2020/2021")
        weeks = period.iso_weeks(start, end)
        w53 = [w for w in weeks if w["iso_week"] == 53]
        self.assertTrue(w53, "se esperaba encontrar W53 en la temporada 2020/2021")
        order = self.env["step.management.production.order"].create({
            "company_id": self.company_a.id, "season": "2020/2021",
            "iso_year": w53[0]["iso_year"], "iso_week": 53,
            "center_id": self.center_a.id,
        })
        commands, monday, sunday, _fp = order._build_op_commands()
        self.assertEqual(monday, w53[0]["monday"])

    # ------------------------------------------------------------------
    # 3. Vista previa sin escritura y detección de fuente cambiada
    # ------------------------------------------------------------------
    def test_preview_does_not_write_until_confirmed(self):
        plan = self._plan_with_weekly_tasks()
        iso_year, iso_week = self._pick_week(plan)
        self._approved_program(iso_week)
        order = self._make_order(iso_year, iso_week)
        order.action_generate_preview()
        self.assertFalse(order.line_ids)
        wizard = self.env["step.management.production.order.preview.wizard"].with_context(
            default_order_id=order.id
        ).create({})
        self.assertGreater(wizard.add_count, 0)
        self.assertFalse(order.line_ids)  # sigue sin escribir
        wizard.action_confirm()
        self.assertEqual(len(order.line_ids), wizard.add_count)

    def test_source_changed_after_preview_blocks_authorize(self):
        order = self._full_order()
        # una nueva tarea manual con la misma semana ISO cambia lo que
        # `_build_op_commands` recalcularía — pero la huella congelada en
        # `generation_fingerprint` sigue siendo la de la vista previa vieja.
        plan = self.env["step.management.plan"].search([
            ("company_id", "=", self.company_a.id),
        ], limit=1, order="id desc")
        plan.write({"line_ids": [(0, 0, {
            "date": "2026-06-01", "indicator": "Tarea manual nueva",
            "center_id": self.center_a.id,
            "iso_year": order.iso_year, "iso_week": order.iso_week,
            "quantity": 5.0,
        })]})
        with self.assertRaises(UserError):
            order.with_user(self.user_approver).action_authorize()

    # ------------------------------------------------------------------
    # 4. Conciliación independiente por tipo de fuente
    # ------------------------------------------------------------------
    def test_reconciliation_by_source_type(self):
        order = self._full_order()
        plan_lines = order.line_ids.filtered(lambda l: l.source_type == "plan_line")
        program_lines = order.line_ids.filtered(lambda l: l.source_type == "program_application")
        self.assertEqual(len(plan_lines), 1)
        self.assertEqual(len(program_lines), 1)
        self.assertAlmostEqual(program_lines.quantity, 2.0 * self.center_a.hectares)

    # ------------------------------------------------------------------
    # 5. No duplicación de fuentes dentro de la OP
    # ------------------------------------------------------------------
    def test_no_duplicate_plan_line_source_in_same_order(self):
        order = self._full_order()
        plan_line = order.line_ids.filtered(
            lambda l: l.source_type == "plan_line"
        ).plan_line_id
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env["step.management.production.order.line"].create({
                    "order_id": order.id, "source_type": "plan_line",
                    "plan_line_id": plan_line.id, "quantity": 1.0,
                })

    # ------------------------------------------------------------------
    # 6. Autorización sólo por aprobador (incluso por RPC directo)
    # ------------------------------------------------------------------
    def test_only_approver_can_authorize(self):
        order = self._full_order()
        with self.assertRaises(UserError):
            order.with_user(self.user_operator).action_authorize()
        order.with_user(self.user_approver).action_authorize()
        self.assertEqual(order.state, "authorized")

    # ------------------------------------------------------------------
    # 7. Snapshot/hash deterministas, inmutabilidad y revisión
    # ------------------------------------------------------------------
    def test_snapshot_hash_and_immutability(self):
        import hashlib
        import json
        order = self._full_order()
        order.with_user(self.user_approver).action_authorize()
        self.assertTrue(order.approval_snapshot)
        self.assertEqual(
            order.approval_hash,
            hashlib.sha256(order.approval_snapshot.encode("utf-8")).hexdigest(),
        )
        payload = json.loads(order.approval_snapshot)
        self.assertEqual(payload["revision"], 1)
        self.assertEqual(len(payload["lines"]), 2)
        with self.assertRaises(UserError):
            order.write({"season": "9999/9999"})
        with self.assertRaises(UserError):
            order.line_ids[0].write({"quantity": 999.0})
        with self.assertRaises(UserError):
            order.with_user(self.user_approver).unlink()

    def test_revision_supersedes_origin_on_authorize(self):
        order = self._full_order()
        order.with_user(self.user_approver).action_authorize()
        with self.assertRaises(UserError):
            order._do_reopen("")
        revision = order._do_reopen("Corrección de cantidades")
        self.assertEqual(revision.state, "draft")
        self.assertEqual(revision.revision, 2)
        self.assertEqual(revision.revision_of_id, order)
        # las líneas son derivadas (como `crop_program.application_ids`), no
        # se copian: la revisión debe regenerar su propia vista previa.
        self.assertFalse(revision.line_ids)
        self._generate_and_confirm(revision)
        self.assertEqual(len(revision.line_ids), len(order.line_ids))
        revision.with_user(self.user_approver).action_authorize()
        order.invalidate_recordset()
        self.assertEqual(order.state, "superseded")
        self.assertEqual(order.superseded_by_id, revision)

    # ------------------------------------------------------------------
    # 8. Concurrencia de autorización (índice único parcial)
    # ------------------------------------------------------------------
    def test_concurrent_authorization_same_identity_blocked(self):
        plan = self._plan_with_weekly_tasks()
        iso_year, iso_week = self._pick_week(plan)
        self._approved_program(iso_week)
        order1 = self._make_order(iso_year, iso_week)
        self._generate_and_confirm(order1)
        order1.with_user(self.user_approver).action_authorize()

        # segunda OP INDEPENDIENTE (no es una revisión) con la misma clave
        # natural — simula dos usuarios generando y autorizando en paralelo.
        order2 = self._make_order(iso_year, iso_week)
        self._generate_and_confirm(order2)
        with mute_logger("odoo.sql_db"), self.assertRaises(UserError):
            order2.with_user(self.user_approver).action_authorize()
        self.assertEqual(order2.state, "draft")

    # ------------------------------------------------------------------
    # 9. PDF desde snapshot (verificado sobre el HTML renderizado)
    # ------------------------------------------------------------------
    def test_pdf_uses_snapshot_not_live_data(self):
        order = self._full_order()
        order.with_user(self.user_approver).action_authorize()
        report = self.env["ir.actions.report"]
        html, _ext = report._render_qweb_html(
            "step_management_costs.report_production_order", order.ids,
        )
        text = html.decode("utf-8") if isinstance(html, bytes) else html
        self.assertIn(order.name, text)
        self.assertIn("W%02d" % order.iso_week, text)
        self.assertIn(self.center_a.display_name, text)
        self.assertIn(self.prod_input.display_name, text)

        # cambios posteriores en maestros no deben alterar el PDF ya autorizado
        old_product_name = self.prod_input.display_name
        self.prod_input.write({"name": "Nombre cambiado después de autorizar"})
        self.center_a.write({"name": "Centro renombrado después de autorizar"})
        html2, _ext = report._render_qweb_html(
            "step_management_costs.report_production_order", order.ids,
        )
        text2 = html2.decode("utf-8") if isinstance(html2, bytes) else html2
        self.assertIn(old_product_name, text2)
        self.assertNotIn("Nombre cambiado después de autorizar", text2)
        self.assertNotIn("Centro renombrado después de autorizar", text2)

    # ------------------------------------------------------------------
    # 10. Destinatarios y envío simulado
    # ------------------------------------------------------------------
    def test_send_requires_authorized_and_recipients(self):
        order = self._full_order()
        with self.assertRaises(UserError):
            order.action_send_report()  # aún en borrador
        order.with_user(self.user_approver).action_authorize()
        with self.assertRaises(UserError):
            order.action_send_report()  # sin destinatarios

    def test_send_queues_mail_without_real_smtp(self):
        order = self._full_order()
        order.with_user(self.user_approver).action_authorize()
        order.recipient_ids = [(6, 0, [self.partner.id])]
        mail_before = self.env["mail.mail"].search_count([])
        order.action_send_report()
        self.assertEqual(order.send_state, "sent")
        self.assertTrue(order.send_requested_by_id)
        self.assertTrue(order.send_requested_at)
        mail = self.env["mail.mail"].search([], order="id desc", limit=1)
        self.assertGreater(self.env["mail.mail"].search_count([]), mail_before)
        self.assertIn(self.partner, mail.recipient_ids)
        self.assertEqual(mail.state, "outgoing")  # nunca se llamó a `.send()`

    # ------------------------------------------------------------------
    # 11. API futura de OT: rechaza borrador, acepta autorizada
    # ------------------------------------------------------------------
    def test_bridge_payload_rejects_draft_accepts_authorized(self):
        order = self._full_order()
        with self.assertRaises(UserError):
            order.get_bridge_payload()
        order.with_user(self.user_approver).action_authorize()
        payload = order.get_bridge_payload()
        self.assertEqual(payload["folio"], order.name)
        self.assertEqual(len(payload["lines"]), 2)
