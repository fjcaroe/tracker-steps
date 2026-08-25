from odoo.exceptions import AccessError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "step_colaciones")
class TestColacionesAppUrl(TransactionCase):
    """URL propia de la aplicación: normalización, fallback y multiempresa."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.env["ir.config_parameter"].sudo().set_param(
            "web.base.url", "https://desarrollo.stepsapp.cl"
        )
        cls.product = cls.env["product.template"].create({
            "name": "Almuerzo URL", "is_meal": True,
        })
        cls.supplier = cls.env["res.partner"].create({
            "name": "Casino URL", "is_meal_supplier": True,
        })
        cls.totem = cls.env["step.colacion.totem"].create({
            "name": "Tótem URL",
            "code": "TOTEM-URL",
            "company_id": cls.company.id,
            "product_tmpl_id": cls.product.id,
            "supplier_id": cls.supplier.id,
        })
        # La pantalla de ajustes es para el Administrador de Colaciones, que no
        # necesita los ajustes generales de Odoo: se prueba con ese perfil.
        cls.manager = cls.env["res.users"].create({
            "name": "Administrador de Colaciones",
            "login": "colaciones.manager.test",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, [cls.company.id])],
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("step_colaciones.group_colaciones_manager").id,
            ])],
        })
        cls.plain_user = cls.env["res.users"].create({
            "name": "Usuario de Colaciones",
            "login": "colaciones.user.test",
            "company_id": cls.company.id,
            "company_ids": [(6, 0, [cls.company.id])],
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("step_colaciones.group_colaciones_user").id,
            ])],
        })

    def _settings_as(self, user, values):
        return self.env["step.colacion.settings"].with_user(user).create(values)

    def setUp(self):
        super().setUp()
        self.company.colaciones_pwa_base_url = False

    # ------------------------------------------------------------------
    # Normalización
    # ------------------------------------------------------------------
    def test_normalizes_trailing_slashes(self):
        normalize = self.company._normalize_colaciones_base_url
        self.assertEqual(
            normalize("https://colaciones.stepsapp.cl///"),
            "https://colaciones.stepsapp.cl",
        )
        self.assertEqual(
            normalize("  https://demo.stepsapp.cl/colaciones/app/  "),
            "https://demo.stepsapp.cl/colaciones/app",
        )

    def test_empty_value_is_not_an_error(self):
        self.assertEqual(self.company._normalize_colaciones_base_url(""), "")
        self.assertEqual(self.company._normalize_colaciones_base_url(None), "")

    def test_rejects_plain_http_outside_localhost(self):
        with self.assertRaises(ValidationError):
            self.company._normalize_colaciones_base_url("http://colaciones.stepsapp.cl")

    def test_allows_http_on_localhost(self):
        self.assertEqual(
            self.company._normalize_colaciones_base_url("http://localhost:8069/colaciones/app/"),
            "http://localhost:8069/colaciones/app",
        )

    def test_rejects_missing_scheme_and_host(self):
        for value in ("colaciones.stepsapp.cl", "ftp://colaciones.stepsapp.cl", "https://"):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    self.company._normalize_colaciones_base_url(value)

    def test_rejects_fragment_and_query(self):
        for value in (
            "https://colaciones.stepsapp.cl/#token=abc",
            "https://colaciones.stepsapp.cl/?token=abc",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValidationError):
                    self.company._normalize_colaciones_base_url(value)

    def test_constraint_blocks_invalid_value_on_company(self):
        with self.assertRaises(ValidationError):
            self.company.colaciones_pwa_base_url = "http://colaciones.stepsapp.cl"

    # ------------------------------------------------------------------
    # Construcción de la URL del tótem
    # ------------------------------------------------------------------
    def test_fallback_keeps_legacy_path(self):
        self.assertEqual(
            self.company.colaciones_app_base_url(),
            "https://desarrollo.stepsapp.cl/colaciones/app",
        )
        self.assertEqual(
            self.totem.totem_url,
            "https://desarrollo.stepsapp.cl/colaciones/app/#token=%s" % self.totem.access_token,
        )

    def test_configured_host_replaces_legacy_path(self):
        self.company.colaciones_pwa_base_url = "https://colaciones.stepsapp.cl/"
        self.totem.invalidate_recordset(["totem_url", "app_base_url"])
        self.assertEqual(
            self.totem.totem_url,
            "https://colaciones.stepsapp.cl/#token=%s" % self.totem.access_token,
        )
        self.assertEqual(self.totem.app_base_url, "https://colaciones.stepsapp.cl")

    def test_url_is_per_company(self):
        other_company = self.env["res.company"].create({"name": "Segunda Compañía"})
        other_company.colaciones_pwa_base_url = "https://colaciones-demo.stepsapp.cl"
        other_product = self.env["product.template"].create({
            "name": "Almuerzo B", "is_meal": True, "company_id": other_company.id,
        })
        other_totem = self.env["step.colacion.totem"].create({
            "name": "Tótem B",
            "code": "TOTEM-B",
            "company_id": other_company.id,
            "product_tmpl_id": other_product.id,
            "supplier_id": self.supplier.id,
        })
        self.assertTrue(self.totem.totem_url.startswith("https://desarrollo.stepsapp.cl/colaciones/app/"))
        self.assertTrue(other_totem.totem_url.startswith("https://colaciones-demo.stepsapp.cl/#token="))

    def test_changing_url_preserves_existing_tokens(self):
        token_before = self.totem.access_token
        self.company.colaciones_pwa_base_url = "https://colaciones.stepsapp.cl"
        self.totem.invalidate_recordset(["totem_url"])
        self.assertEqual(self.totem.access_token, token_before)
        self.assertTrue(self.totem.totem_url.endswith(token_before))

    def test_regenerate_token_changes_url_and_clears_device(self):
        token_before = self.totem.access_token
        self.totem._touch_device(device={"uuid": "install-1", "platform": "android", "app_version": "1.0.0"})
        self.assertEqual(self.totem.device_uuid, "install-1")
        self.totem.action_regenerate_token()
        self.assertNotEqual(self.totem.access_token, token_before)
        self.assertFalse(self.totem.device_uuid)
        self.assertTrue(self.totem.totem_url.endswith(self.totem.access_token))

    # ------------------------------------------------------------------
    # Pantalla de ajustes
    # ------------------------------------------------------------------
    def test_settings_screen_saves_normalized_value(self):
        settings = self._settings_as(self.manager, {
            "company_id": self.company.id,
            "pwa_base_url": "https://colaciones.stepsapp.cl//",
        })
        self.assertEqual(settings.effective_base_url, "https://colaciones.stepsapp.cl")
        self.assertEqual(settings.sample_totem_url, "https://colaciones.stepsapp.cl/#token=…")
        settings.action_apply()
        self.assertEqual(self.company.colaciones_pwa_base_url, "https://colaciones.stepsapp.cl")

    def test_settings_screen_can_clear_value(self):
        self.company.colaciones_pwa_base_url = "https://colaciones.stepsapp.cl"
        settings = self._settings_as(self.manager, {
            "company_id": self.company.id,
            "pwa_base_url": "",
        })
        settings.action_apply()
        self.assertFalse(self.company.colaciones_pwa_base_url)
        self.assertEqual(
            self.company.colaciones_app_base_url(),
            "https://desarrollo.stepsapp.cl/colaciones/app",
        )

    def test_settings_screen_rejects_invalid_value(self):
        settings = self._settings_as(self.manager, {
            "company_id": self.company.id,
            "pwa_base_url": "http://colaciones.stepsapp.cl",
        })
        with self.assertRaises(ValidationError):
            settings.action_apply()

    def test_settings_screen_requires_manager_group(self):
        # Un Usuario de Colaciones no puede siquiera abrir la pantalla: el
        # control está en las reglas de acceso y también en action_apply.
        with self.assertRaises(AccessError):
            self._settings_as(self.plain_user, {
                "company_id": self.company.id,
                "pwa_base_url": "https://colaciones.stepsapp.cl",
            }).action_apply()

    def test_settings_screen_rejects_another_company(self):
        other_company = self.env["res.company"].create({"name": "Compañía sin acceso"})
        settings = self._settings_as(self.manager, {
            "company_id": other_company.id,
            "pwa_base_url": "https://colaciones.stepsapp.cl",
        })
        with self.assertRaises(AccessError):
            settings.action_apply()

    def test_manager_cannot_change_app_versions(self):
        settings = self._settings_as(self.manager, {
            "company_id": self.company.id,
            "min_app_version": "9.9.9",
        })
        self.assertFalse(settings.can_edit_app_versions)
        settings.action_apply()
        self.assertNotEqual(
            self.env["ir.config_parameter"].sudo().get_param("colaciones.min_app_version"),
            "9.9.9",
        )
