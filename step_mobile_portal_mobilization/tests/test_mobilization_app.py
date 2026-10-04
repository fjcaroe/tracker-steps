import json
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import HttpCase, tagged


def _iso(moment):
    return moment.replace(microsecond=0).isoformat() + "Z"


@tagged("post_install", "-at_install", "step_mobile_portal_mobilization")
class TestMobilizationApp(HttpCase):
    """Recorrido con datos sintéticos: asignación en Odoo → conductor → eventos con y sin red → supervisor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = cls.env["step.app.api"]
        cls.company = cls.env["res.company"].create({"name": "Empresa Movilización (prueba)"})
        cls.other = cls.env["res.company"].create({"name": "Otra (prueba)"})
        brand = cls.env["fleet.vehicle.model.brand"].create({"name": "Marca prueba"})
        model = cls.env["fleet.vehicle.model"].create({"name": "Modelo prueba", "brand_id": brand.id})
        cls.vehicle = cls.env["fleet.vehicle"].create({
            "model_id": model.id, "company_id": cls.company.id, "step_max_pass": 2, "step_min_pass": 1,
            "step_mobilization_enabled": True})
        cls.transporter = cls.env["res.partner"].create({"name": "Transportista prueba", "step_trans_person": True})
        cls.driver1 = cls.env["res.partner"].create({"name": "Chofer Uno", "step_chofer": True, "transpor_id": cls.transporter.id})
        cls.driver2 = cls.env["res.partner"].create({"name": "Chofer Dos", "step_chofer": True, "transpor_id": cls.transporter.id})
        cls.route = cls.env["hr.route"].create({"name": "Ruta prueba", "company_id": cls.company.id})
        cls.emp1 = cls.env["hr.employee"].create({"name": "Pasajero Uno", "company_id": cls.company.id, "barcode": "P001"})
        cls.emp_foreign = cls.env["hr.employee"].create({"name": "Pasajero Ajeno", "company_id": cls.other.id, "barcode": "P999"})
        cls.role_driver = cls.env.ref("step_mobile_portal_mobilization.step_app_role_mobilization_conductor")
        cls.role_sup = cls.env.ref("step_mobile_portal_mobilization.step_app_role_mobilization_supervisor")

    def _trip(self, driver):
        return self.env["step.movi.registry"].create({
            "company_id": self.company.id, "recorrido_id": self.route.id, "vehicle_id": self.vehicle.id,
            "partner_id": self.transporter.id, "chofer_id": driver.id, "direction": "ida"})

    def _person(self, email, role, partner=None, device_uuid="dev-m"):
        session = self.api.register(email, "clave-segura-2026", email.split("@")[0],
                                    {"uuid": device_uuid, "platform": "android", "app_version": "1.3.0"})
        person = self.env["step.app.person"].search([("email", "=", email)])
        membership = self.env["step.app.membership"].create(
            {"person_id": person.id, "company_id": self.company.id, "state": "active", "partner_id": partner.id if partner else False})
        self.env["step.app.grant"].create({"membership_id": membership.id, "module_id": role.module_id.id, "role_id": role.id})
        return session, membership

    def _call(self, method, path, session, payload=None):
        headers = {"Authorization": "Bearer " + session["access_token"], "X-Steps-Org": self.company.step_app_org_uid,
                   "Content-Type": "application/json"}
        response = self.url_open("/steps_app/v1/mobilization" + path, data=json.dumps(payload) if payload is not None else None,
                                 headers=headers, method=method)
        return response.status_code, response.json()

    def _event(self, key, when=None, identifier="P001", event_type="boarding"):
        return {"idempotency_key": key, "method": "barcode", "identifier": identifier, "event_type": event_type,
                "device_datetime": _iso(when or fields.Datetime.now())}

    def test_conductor_requiere_vinculo_explicito_con_un_chofer(self):
        session = self.api.register("c0@example.test", "clave-segura-2026", "C", {"uuid": "dev-0"})
        person = self.env["step.app.person"].search([("email", "=", "c0@example.test")])
        membership = self.env["step.app.membership"].create({"person_id": person.id, "company_id": self.company.id, "state": "active"})
        with self.assertRaises(ValidationError):
            self.env["step.app.grant"].create({"membership_id": membership.id, "module_id": self.role_driver.module_id.id,
                                               "role_id": self.role_driver.id})
        self.assertTrue(session)

    def test_conductor_ve_solo_sus_servicios(self):
        mine, other = self._trip(self.driver1), self._trip(self.driver2)
        session, _m = self._person("c1@example.test", self.role_driver, self.driver1, "dev-c1")
        status, body = self._call("GET", "/trips", session)
        self.assertEqual([t["id"] for t in body["trips"]], [mine.id])
        status, body = self._call("GET", "/trips/%d" % other.id, session)
        self.assertEqual((status, body["error"]), (404, "trip_not_found"))
        status, body = self._call("POST", "/trips/%d/open" % other.id, session)
        self.assertEqual(status, 404)

    def test_eventos_llegan_una_sola_vez_y_conservan_autoria(self):
        trip = self._trip(self.driver1)
        session, _m = self._person("c2@example.test", self.role_driver, self.driver1, "dev-c2")
        self.assertEqual(self._call("POST", "/trips/%d/open" % trip.id, session)[0], 200)
        batch = {"events": [self._event("k1"), self._event("k2", event_type="alighting")]}
        status, body = self._call("POST", "/trips/%d/events" % trip.id, session, batch)
        self.assertEqual([r["status"] for r in body["results"]], ["created", "created"])
        status, body = self._call("POST", "/trips/%d/events" % trip.id, session, batch)  # reenvío del mismo lote
        self.assertEqual([r["status"] for r in body["results"]], ["duplicate", "duplicate"])
        events = trip.passenger_event_ids
        self.assertEqual(len(events), 2)
        self.assertEqual(events.mapped("app_person_id.email"), ["c2@example.test"] * 2)

    def test_pasajero_de_otra_empresa_o_desconocido_se_rechaza(self):
        trip = self._trip(self.driver1)
        session, _m = self._person("c3@example.test", self.role_driver, self.driver1, "dev-c3")
        self._call("POST", "/trips/%d/open" % trip.id, session)
        status, body = self._call("POST", "/trips/%d/events" % trip.id, session, {"events": [
            self._event("x1", identifier="P999"), self._event("x2", identifier="NOEXISTE")]})
        self.assertEqual([r["message"] for r in body["results"]], ["passenger_not_authorized"] * 2)
        self.assertFalse(trip.passenger_event_ids)

    def test_evento_en_viaje_cerrado_se_rechaza_de_forma_definitiva(self):
        trip = self._trip(self.driver1)
        session, _m = self._person("c4@example.test", self.role_driver, self.driver1, "dev-c4")
        self._call("POST", "/trips/%d/open" % trip.id, session)
        self.assertEqual(self._call("POST", "/trips/%d/close" % trip.id, session)[0], 200)
        status, body = self._call("POST", "/trips/%d/events" % trip.id, session, {"events": [self._event("z1")]})
        self.assertEqual((body["results"][0]["status"], body["results"][0]["terminal"]), ("rejected", True))

    def test_evento_offline_capturado_antes_de_la_revocacion_se_acepta(self):
        trip = self._trip(self.driver1)
        session, membership = self._person("c5@example.test", self.role_driver, self.driver1, "dev-c5")
        self._call("POST", "/trips/%d/open" % trip.id, session)
        before = fields.Datetime.now() - timedelta(minutes=30)
        membership.action_revoke()
        after = fields.Datetime.now() + timedelta(seconds=1)
        status, body = self._call("POST", "/trips/%d/events" % trip.id, session, {"events": [
            self._event("r1", before), self._event("r2", after, identifier="P001", event_type="alighting")]})
        self.assertEqual(status, 200)
        self.assertEqual([r["status"] for r in body["results"]], ["created", "rejected"])
        # En línea, una membresía revocada ya no consulta nada.
        self.assertEqual(self._call("GET", "/trips", session)[0], 403)

    def test_supervisor_consulta_el_resultado_y_el_conductor_no_supervisa(self):
        trip = self._trip(self.driver1)
        driver_session, _m = self._person("c6@example.test", self.role_driver, self.driver1, "dev-c6")
        self._call("POST", "/trips/%d/open" % trip.id, driver_session)
        self._call("POST", "/trips/%d/events" % trip.id, driver_session, {"events": [self._event("s1")]})
        sup_session, _m = self._person("sup@example.test", self.role_sup, None, "dev-sup")
        status, body = self._call("GET", "/supervisor/trips", sup_session)
        self.assertEqual(status, 200)
        self.assertEqual(body["trips"][0]["boarded_count"], 1)
        self.assertEqual(body["trips"][0]["events"][0]["by"], "c6")
        self.assertEqual(self._call("GET", "/supervisor/trips", driver_session)[0], 403)

    def test_dispositivo_de_la_app_no_sirve_para_la_api_de_dispositivos(self):
        trip = self._trip(self.driver1)
        session, _m = self._person("c7@example.test", self.role_driver, self.driver1, "dev-c7")
        self._call("POST", "/trips/%d/open" % trip.id, session)
        self._call("POST", "/trips/%d/events" % trip.id, session, {"events": [self._event("d1")]})
        mdevice = self.env["step.mobilization.driver.device"].search([("app_device_id", "!=", False)], limit=1)
        self.assertFalse(mdevice.token_hash)
        response = self.url_open("/mobilization/v1/catalog", headers={"X-Device-UUID": mdevice.device_uuid, "X-Device-Token": "x"})
        self.assertEqual(response.status_code, 401)
