import json
from datetime import datetime, timedelta, timezone

from odoo.exceptions import ValidationError
from odoo.tests.common import HttpCase, tagged

from ..models.meal_totem import MAX_BATCH_RECORDS


def _iso(moment):
    return moment.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@tagged("post_install", "-at_install", "step_colaciones")
class TestColacionesApi(HttpCase):
    """Contrato HTTP consumido por la PWA y por la App móvil."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.product = cls.env["product.template"].create({"name": "Almuerzo API", "is_meal": True})
        cls.supplier = cls.env["res.partner"].create({"name": "Casino API", "is_meal_supplier": True})
        cls.employee = cls.env["hr.employee"].create({
            "name": "Trabajador API",
            "company_id": cls.company.id,
            "meal_eligible": True,
            "barcode": "API0001",
        })
        cls.blocked = cls.env["hr.employee"].create({
            "name": "Trabajador sin colación",
            "company_id": cls.company.id,
            "meal_eligible": False,
            "barcode": "API0002",
        })
        cls.totem = cls.env["step.colacion.totem"].create({
            "name": "Tótem API",
            "code": "TOTEM-API",
            "company_id": cls.company.id,
            "product_tmpl_id": cls.product.id,
            "supplier_id": cls.supplier.id,
            "identification_method": "barcode",
        })
        cls.token = cls.totem.access_token

    # ------------------------------------------------------------------
    def _post(self, path, payload):
        response = self.url_open(
            path,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        return response, response.json()

    def _get(self, path):
        response = self.url_open(path)
        return response, response.json()

    # ------------------------------------------------------------------
    # Health y configuración
    # ------------------------------------------------------------------
    def test_health_declares_contract(self):
        response, body = self._get("/colaciones/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["api_version"], 2)
        self.assertIn("batch_sync", body["capabilities"])
        self.assertEqual(body["max_batch_records"], MAX_BATCH_RECORDS)
        self.assertTrue(body["server_time"].endswith("Z"))

    def test_configuration_returns_operational_fields_only(self):
        response, body = self._get("/colaciones/api/totem/%s" % self.token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["code"], "TOTEM-API")
        self.assertEqual(body["identification_method"], "barcode")
        self.assertNotIn("access_token", body)
        self.assertEqual(response.headers.get("Cache-Control"), "no-store")

    def test_unknown_token_answers_json_404(self):
        response, body = self._get("/colaciones/api/totem/token-invalido")
        self.assertEqual(response.status_code, 404)
        self.assertFalse(body["ok"])
        self.assertTrue(body["terminal"])
        self.assertEqual(body["error"], "totem_not_found")
        self.assertIn("application/json", response.headers.get("Content-Type", ""))

    def test_revoked_token_stops_working(self):
        old_token = self.totem.access_token
        self.totem.action_regenerate_token()
        response, body = self._get("/colaciones/api/totem/%s" % old_token)
        self.assertEqual(response.status_code, 404)
        response, body = self._post("/colaciones/api/register", {
            "token": old_token,
            "identifier": "API0001",
            "client_uuid": "api-revoked-1",
        })
        self.assertEqual(response.status_code, 404)
        self.assertTrue(body["terminal"])

    def test_archived_totem_is_not_reachable(self):
        self.totem.active = False
        response, _body = self._get("/colaciones/api/totem/%s" % self.token)
        self.assertEqual(response.status_code, 404)
        self.totem.active = True

    # ------------------------------------------------------------------
    # Registro individual
    # ------------------------------------------------------------------
    def test_register_online_and_duplicate(self):
        response, body = self._post("/colaciones/api/register", {
            "token": self.token,
            "identifier": "API0001",
            "client_uuid": "api-online-1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["employee"], "Trabajador API")

        # Mismo UUID: idempotente, no crea un segundo registro.
        response, repeated = self._post("/colaciones/api/register", {
            "token": self.token,
            "identifier": "API0001",
            "client_uuid": "api-online-1",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(repeated["duplicate"])

        # UUID distinto, mismo trabajador/producto/día: duplicado funcional.
        response, same_day = self._post("/colaciones/api/register", {
            "token": self.token,
            "identifier": "API0001",
            "client_uuid": "api-online-2",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(same_day["duplicate"])
        self.assertEqual(self.env["step.colacion.registration"].search_count([
            ("employee_id", "=", self.employee.id),
            ("product_tmpl_id", "=", self.product.id),
        ]), 1)

    def test_register_rejects_unknown_and_not_eligible(self):
        response, body = self._post("/colaciones/api/register", {
            "token": self.token,
            "identifier": "NO-EXISTE",
            "client_uuid": "api-unknown-1",
        })
        self.assertEqual(response.status_code, 422)
        self.assertTrue(body["terminal"])

        response, body = self._post("/colaciones/api/register", {
            "token": self.token,
            "identifier": "API0002",
            "client_uuid": "api-blocked-1",
        })
        self.assertEqual(response.status_code, 422)
        self.assertTrue(body["terminal"])
        self.assertIn("habilitado", body["message"])

    def test_register_requires_client_uuid(self):
        response, body = self._post("/colaciones/api/register", {
            "token": self.token,
            "identifier": "API0001",
        })
        self.assertEqual(response.status_code, 422)
        self.assertTrue(body["terminal"])

    # ------------------------------------------------------------------
    # Antigüedad y reloj
    # ------------------------------------------------------------------
    def test_offline_capture_too_old_is_rejected(self):
        stale = datetime.now(timezone.utc) - timedelta(hours=self.totem.offline_max_hours + 2)
        with self.assertRaises(ValidationError):
            self.totem.register_identifier(
                "API0001", "api-stale-1", event_datetime=_iso(stale), offline=True
            )

    def test_device_clock_in_the_future_is_rejected(self):
        future = datetime.now(timezone.utc) + timedelta(hours=3)
        with self.assertRaises(ValidationError):
            self.totem.register_identifier(
                "API0001", "api-future-1", event_datetime=_iso(future), offline=True
            )

    def test_offline_disabled_totem_rejects_offline_capture(self):
        self.totem.allow_offline = False
        with self.assertRaises(ValidationError):
            self.totem.register_identifier(
                "API0001", "api-nooffline-1",
                event_datetime=_iso(datetime.now(timezone.utc)), offline=True,
            )
        self.totem.allow_offline = True

    # ------------------------------------------------------------------
    # Sincronización por lote
    # ------------------------------------------------------------------
    def test_batch_returns_one_result_per_uuid(self):
        moment = _iso(datetime.now(timezone.utc) - timedelta(minutes=5))
        response, body = self._post("/colaciones/api/sync", {
            "token": self.token,
            "device": {"uuid": "install-abc", "platform": "android", "app_version": "1.0.0"},
            "records": [
                {"client_uuid": "batch-1", "identifier": "API0001", "event_datetime": moment, "offline": True},
                {"client_uuid": "batch-2", "identifier": "NO-EXISTE", "event_datetime": moment, "offline": True},
                {"client_uuid": "batch-3", "identifier": "API0002", "event_datetime": moment, "offline": True},
                {"client_uuid": "batch-1", "identifier": "API0001", "event_datetime": moment, "offline": True},
            ],
        })
        self.assertEqual(response.status_code, 200)
        statuses = {item["client_uuid"]: item["status"] for item in body["results"]}
        self.assertEqual(len(body["results"]), 4)
        self.assertEqual(statuses["batch-2"], "rejected")
        self.assertEqual(statuses["batch-3"], "rejected")
        # batch-1 aparece dos veces: la primera se registra, la segunda es duplicado.
        first, repeated = [item for item in body["results"] if item["client_uuid"] == "batch-1"]
        self.assertEqual(first["status"], "registered")
        self.assertEqual(repeated["status"], "duplicate")
        self.assertEqual(self.env["step.colacion.registration"].search_count([
            ("client_uuid", "in", ["batch-1", "batch-2", "batch-3"])
        ]), 1)

    def test_batch_records_device_information(self):
        self._post("/colaciones/api/sync", {
            "token": self.token,
            "device": {"uuid": "install-xyz", "platform": "ios", "app_version": "1.2.3"},
            "records": [],
        })
        self.totem.invalidate_recordset()
        self.assertEqual(self.totem.device_uuid, "install-xyz")
        self.assertEqual(self.totem.device_platform, "ios")
        self.assertEqual(self.totem.device_app_version, "1.2.3")
        self.assertTrue(self.totem.last_sync_at)

    def test_batch_over_limit_is_rejected(self):
        moment = _iso(datetime.now(timezone.utc))
        records = [
            {"client_uuid": "over-%s" % index, "identifier": "API0001", "event_datetime": moment}
            for index in range(MAX_BATCH_RECORDS + 1)
        ]
        response, body = self._post("/colaciones/api/sync", {
            "token": self.token, "records": records,
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(body["error"], "invalid_batch")

    def test_batch_requires_a_list(self):
        response, body = self._post("/colaciones/api/sync", {
            "token": self.token, "records": {"client_uuid": "x"},
        })
        self.assertEqual(response.status_code, 422)
        self.assertEqual(body["error"], "invalid_batch")

    def test_batch_with_unknown_token_is_terminal(self):
        response, body = self._post("/colaciones/api/sync", {
            "token": "no-existe", "records": [],
        })
        self.assertEqual(response.status_code, 404)
        self.assertTrue(body["terminal"])

    # ------------------------------------------------------------------
    # Multiempresa
    # ------------------------------------------------------------------
    def test_employee_from_another_company_is_rejected(self):
        other_company = self.env["res.company"].create({"name": "Compañía Ajena API"})
        self.env["hr.employee"].create({
            "name": "Ajeno",
            "company_id": other_company.id,
            "meal_eligible": True,
            "barcode": "API9999",
        })
        response, body = self._post("/colaciones/api/register", {
            "token": self.token,
            "identifier": "API9999",
            "client_uuid": "api-other-company-1",
        })
        self.assertEqual(response.status_code, 422)
        self.assertTrue(body["terminal"])

    def test_client_cannot_choose_product_supplier_or_price(self):
        response, body = self._post("/colaciones/api/register", {
            "token": self.token,
            "identifier": "API0001",
            "client_uuid": "api-tamper-1",
            "product_tmpl_id": 1,
            "supplier_id": 1,
            "unit_cost": 999999,
            "state": "validated",
        })
        self.assertEqual(response.status_code, 200)
        registration = self.env["step.colacion.registration"].search([
            ("client_uuid", "=", "api-tamper-1")
        ])
        self.assertEqual(registration.product_tmpl_id, self.product)
        self.assertEqual(registration.supplier_id, self.supplier)
        self.assertEqual(registration.state, "entered")
        self.assertEqual(registration.unit_cost, 0)
        self.assertEqual(registration.total_cost, 0)
        self.assertTrue(body["ok"])

    def test_identifier_is_stored_masked(self):
        self.totem.register_identifier("API0001", "api-mask-1")
        registration = self.env["step.colacion.registration"].search([
            ("client_uuid", "=", "api-mask-1")
        ])
        self.assertNotIn("API0001", registration.identifier_masked)
        self.assertTrue(registration.identifier_masked.endswith("0001"))
