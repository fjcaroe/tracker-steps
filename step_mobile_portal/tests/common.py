from odoo.tests.common import TransactionCase

from ..lib.step_app_core.errors import ApiError

DEVICE = {"uuid": "dev-1", "platform": "android", "label": "Pixel de prueba", "app_version": "1.3.0"}


class PortalCase(TransactionCase):
    """Datos sintéticos: dos empresas, un módulo de prueba y personas ficticias. Nada real."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.api = cls.env["step.app.api"]
        cls.company_a = cls.env["res.company"].create({"name": "Empresa A (prueba)"})
        cls.company_b = cls.env["res.company"].create({"name": "Empresa B (prueba)"})
        cls.module = cls.env["step.app.module"].create({"code": "demo", "name": "Demo", "contract_version": 1})
        cls.role = cls.env["step.app.module.role"].create(
            {"module_id": cls.module.id, "code": "operador", "name": "Operador", "permissions": "demo.read,demo.write"})
        cls.env["ir.config_parameter"].sudo().set_param("step_app.allow_test_provider", "1")

    def register(self, email="ana@example.test", password="clave-segura-2026", device=None):
        return self.api.register(email, password, "Ana Prueba", device or DEVICE)

    def ctx(self, session, org_uid=None):
        return self.api.authenticate(session["access_token"], org_uid)

    def activate(self, person, company, grants=()):
        membership = self.env["step.app.membership"].create({"person_id": person.id, "company_id": company.id, "state": "active"})
        for role in grants:
            self.env["step.app.grant"].create(
                {"membership_id": membership.id, "module_id": role.module_id.id, "role_id": role.id})
        return membership

    def assertApiError(self, code, func, *args, **kwargs):
        with self.assertRaises(ApiError) as cm:
            func(*args, **kwargs)
        self.assertEqual(cm.exception.code, code)
        return cm.exception
