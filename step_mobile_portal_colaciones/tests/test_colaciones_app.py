import json
from datetime import timedelta

from odoo import fields
from odoo.tests.common import HttpCase, tagged

DEVICE = {"uuid": "dev-col", "platform": "android", "label": "Prueba", "app_version": "1.3.0"}


def _iso(moment):
    return moment.replace(microsecond=0).isoformat() + "Z"


@tagged("post_install", "-at_install", "step_mobile_portal_colaciones")
class TestColacionesApp(HttpCase):
    """Recorrido con datos sintéticos: administrador asigna, persona consulta, operador registra (también tras un corte)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = cls.env["step.app.api"]
        cls.company = cls.env["res.company"].create({"name": "Empresa Colaciones (prueba)"})
        cls.other_company = cls.env["res.company"].create({"name": "Otra Empresa (prueba)"})
        product = cls.env["product.template"].create({"name": "Almuerzo prueba", "is_meal": True})
        supplier = cls.env["res.partner"].create({"name": "Casino prueba", "is_meal_supplier": True})
        cls.worker = cls.env["hr.employee"].create(
            {"name": "Trabajador ficticio", "company_id": cls.company.id, "meal_eligible": True, "barcode": "BR0001"})
        cls.worker2 = cls.env["hr.employee"].create(
            {"name": "Trabajador dos", "company_id": cls.company.id, "meal_eligible": True, "barcode": "BR0002"})
        vals = {"product_tmpl_id": product.id, "supplier_id": supplier.id, "identification_method": "barcode"}
        cls.totem = cls.env["step.colacion.totem"].create({"name": "Casino 1", "code": "T1", "company_id": cls.company.id, **vals})
        cls.totem2 = cls.env["step.colacion.totem"].create({"name": "Casino 2", "code": "T2", "company_id": cls.company.id, **vals})
        cls.foreign_totem = cls.env["step.colacion.totem"].create(
            {"name": "Ajeno", "code": "T9", "company_id": cls.other_company.id, **vals})
        cls.role_op = cls.env.ref("step_mobile_portal_colaciones.step_app_role_colaciones_operador")
        cls.role_person = cls.env.ref("step_mobile_portal_colaciones.step_app_role_colaciones_persona")

    def _session(self, email, roles, device=None, employee=None, scope=None):
        session = self.api.register(email, "clave-segura-2026", email.split("@")[0], device or DEVICE)
        person = self.env["step.app.person"].search([("email", "=", email)])
        membership = self.env["step.app.membership"].create(
            {"person_id": person.id, "company_id": self.company.id, "state": "active",
             "employee_id": employee.id if employee else False})
        for role in roles:
            self.env["step.app.grant"].create({"membership_id": membership.id, "module_id": role.module_id.id,
                                               "role_id": role.id, "scope_ids": scope or False})
        return session, membership

    def _call(self, method, path, session, payload=None):
        headers = {"Authorization": "Bearer " + session["access_token"], "X-Steps-Org": self.company.step_app_org_uid,
                   "Content-Type": "application/json"}
        response = self.url_open("/steps_app/v1/colaciones" + path, data=json.dumps(payload) if payload is not None else None,
                                 headers=headers, method=method)
        return response.status_code, response.json()

    def _batch(self, session, records, totem=None):
        return self._call("POST", "/register", session, {"totem_id": (totem or self.totem).id, "records": records})

    def test_operador_registra_una_sola_vez_y_deja_autoria(self):
        session, _m = self._session("op@example.test", [self.role_op])
        record = {"client_uuid": "u-1", "identifier": "BR0001", "offline": False}
        status, body = self._batch(session, [record])
        self.assertEqual((status, body["results"][0]["status"]), (200, "registered"))
        status, body = self._batch(session, [record])
        self.assertEqual(body["results"][0]["status"], "duplicate")
        registrations = self.env["step.colacion.registration"].search([("client_uuid", "=", "u-1")])
        self.assertEqual(len(registrations), 1)
        self.assertEqual(registrations.app_operator_id.email, "op@example.test")

    def test_persona_no_puede_registrar_ni_el_operador_consultar_ajenos(self):
        person_session, _m = self._session("p@example.test", [self.role_person], employee=self.worker)
        status, body = self._batch(person_session, [{"client_uuid": "u-2", "identifier": "BR0001", "offline": False}])
        self.assertEqual(body.get("results", [{}])[0].get("status"), "rejected")
        self.assertFalse(self.env["step.colacion.registration"].search([("client_uuid", "=", "u-2")]))
        op_session, _m = self._session("op2@example.test", [self.role_op], DEVICE | {"uuid": "dev-op2"})
        status, body = self._call("GET", "/me", op_session)
        self.assertEqual(status, 403)

    def test_persona_ve_solo_lo_suyo(self):
        op_session, _m = self._session("op3@example.test", [self.role_op], DEVICE | {"uuid": "dev-op3"})
        self._batch(op_session, [{"client_uuid": "m-1", "identifier": "BR0001", "offline": False},
                                 {"client_uuid": "m-2", "identifier": "BR0002", "offline": False}])
        session, _m = self._session("w@example.test", [self.role_person], DEVICE | {"uuid": "dev-w"}, employee=self.worker)
        status, body = self._call("GET", "/me", session)
        self.assertEqual(status, 200)
        self.assertTrue(body["linked"] and body["today"]["registered"])
        self.assertEqual(len(body["recent"]), 1)
        self.assertNotIn("Trabajador dos", json.dumps(body))

    def test_persona_sin_vinculo_no_ve_datos_aunque_coincida_el_nombre(self):
        self.env["hr.employee"].create({"name": "w", "company_id": self.company.id})
        session, _m = self._session("w2@example.test", [self.role_person], DEVICE | {"uuid": "dev-w2"})
        status, body = self._call("GET", "/me", session)
        self.assertEqual((status, body["linked"]), (200, False))

    def test_alcance_por_totem_y_empresa(self):
        session, _m = self._session("op4@example.test", [self.role_op], DEVICE | {"uuid": "dev-op4"}, scope=[self.totem.id])
        status, body = self._call("GET", "/totems", session)
        self.assertEqual([t["id"] for t in body["totems"]], [self.totem.id])
        status, body = self._batch(session, [{"client_uuid": "a-1", "identifier": "BR0001", "offline": False}], self.totem2)
        self.assertEqual(body["results"][0]["status"], "rejected") if status == 200 else self.assertEqual(status, 403)
        status, body = self._batch(session, [{"client_uuid": "a-2", "identifier": "BR0001", "offline": False}], self.foreign_totem)
        self.assertEqual(status, 403)

    def test_evento_offline_anterior_a_la_revocacion_se_acepta_y_posterior_no(self):
        session, membership = self._session("op5@example.test", [self.role_op], DEVICE | {"uuid": "dev-op5"})
        captured_before = fields.Datetime.now() - timedelta(hours=2)
        membership.action_suspend()
        captured_after = fields.Datetime.now() + timedelta(seconds=1)
        status, body = self._batch(session, [
            {"client_uuid": "o-1", "identifier": "BR0001", "offline": True, "event_datetime": _iso(captured_before)},
            {"client_uuid": "o-2", "identifier": "BR0002", "offline": True, "event_datetime": _iso(captured_after)},
        ])
        self.assertEqual(status, 200)
        self.assertEqual([r["status"] for r in body["results"]], ["registered", "rejected"])
        self.assertEqual(body["results"][1]["message"], "access_ended_before_capture")

    def test_membresia_revocada_corta_la_consulta_en_linea(self):
        session, membership = self._session("op6@example.test", [self.role_op], DEVICE | {"uuid": "dev-op6"})
        membership.action_revoke()
        status, body = self._call("GET", "/totems", session)
        self.assertEqual((status, body["error"]), (403, "organization_not_authorized"))
