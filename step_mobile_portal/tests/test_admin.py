from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import DEVICE, PortalCase


@tagged("post_install", "-at_install")
class TestAdministration(PortalCase):
    """Reglas de acceso con usuarios reales (no superusuario): administrador por empresa, consulta, sin permisos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_user = cls.env.ref("base.group_user")
        cls.g_manager = cls.env.ref("step_mobile_portal.group_step_app_manager")
        cls.g_view = cls.env.ref("step_mobile_portal.group_step_app_user")

        def user(login, company, *groups):
            return cls.env["res.users"].with_context(no_reset_password=True).create({
                "name": login, "login": login, "email": login, "company_id": company.id, "company_ids": [(6, 0, [company.id])],
                "groups_id": [(6, 0, [group_user.id, *[g.id for g in groups]])]})
        cls.admin_a = user("admin-a@example.test", cls.company_a, cls.g_manager)
        cls.admin_b = user("admin-b@example.test", cls.company_b, cls.g_manager)
        cls.viewer_a = user("viewer-a@example.test", cls.company_a, cls.g_view)
        cls.nobody = user("nadie@example.test", cls.company_a)
        # Dos personas con sus membresías: una en cada empresa.
        cls.p_a = cls.env["step.app.person"].create({"name": "Persona A", "email": "pa@example.test"})
        cls.p_b = cls.env["step.app.person"].create({"name": "Persona B", "email": "pb@example.test"})
        cls.m_a = cls.env["step.app.membership"].create({"person_id": cls.p_a.id, "company_id": cls.company_a.id, "state": "requested"})
        cls.m_b = cls.env["step.app.membership"].create({"person_id": cls.p_b.id, "company_id": cls.company_b.id, "state": "active"})

    def as_(self, user):
        return self.env["step.app.membership"].with_user(user)

    def test_administrador_del_sistema_accede_al_portal(self):
        self.nobody.write({"groups_id": [(4, self.env.ref("base.group_system").id)]})
        self.assertTrue(self.nobody.has_group("step_mobile_portal.group_step_app_manager"))
        menu = self.env.ref("step_mobile_portal.menu_step_app_root")
        self.assertIn(menu.id, self.env["ir.ui.menu"].with_user(self.nobody)._visible_menu_ids())
        self.assertEqual(self.nobody.company_ids, self.company_a)

    def test_usuario_sin_permisos_no_ve_nada(self):
        for model in ("step.app.membership", "step.app.person", "step.app.grant", "step.app.invitation", "step.app.audit", "step.app.device"):
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(self.nobody).search([])

    def test_administrador_ve_y_modifica_solo_su_empresa(self):
        self.assertEqual(self.as_(self.admin_a).search([]), self.m_a)
        self.assertEqual(self.as_(self.admin_b).search([]), self.m_b)
        with self.assertRaises(AccessError):
            self.m_b.with_user(self.admin_a).write({"state": "suspended"})
        with self.assertRaises(AccessError):
            self.m_b.with_user(self.admin_a).action_revoke()
        self.assertEqual(self.m_b.state, "active")

    def test_administrador_no_puede_conceder_en_membresia_de_otra_empresa(self):
        with self.assertRaises(AccessError):
            self.env["step.app.grant"].with_user(self.admin_a).create(
                {"membership_id": self.m_b.id, "module_id": self.module.id, "role_id": self.role.id})
        self.assertFalse(self.m_b.grant_ids)

    def test_consulta_lee_pero_no_modifica(self):
        self.assertEqual(self.as_(self.viewer_a).search([]), self.m_a)
        with self.assertRaises(AccessError):
            self.m_a.with_user(self.viewer_a).write({"state": "active"})
        with self.assertRaises(AccessError):
            self.env["step.app.invitation"].with_user(self.viewer_a).create({"email": "x@example.test", "company_id": self.company_a.id})

    def test_administrador_de_empresa_no_suspende_la_cuenta_global_ni_ve_identidades_ajenas(self):
        with self.assertRaises(AccessError):
            self.p_a.with_user(self.admin_a).action_suspend()
        self.assertEqual(self.env["step.app.person"].with_user(self.admin_a).search([]), self.p_a)
        self.env["step.app.identity"].create({"person_id": self.p_b.id, "provider": "password", "subject": "pb@example.test", "email": "pb@example.test"})
        self.assertFalse(self.env["step.app.identity"].with_user(self.admin_a).search([("person_id", "=", self.p_b.id)]))

    def test_administrador_revoca_dispositivo_perdido_solo_de_personas_de_su_empresa(self):
        session = self.api.register("pc@example.test", "clave-segura-2026", "Persona C", DEVICE)
        person = self.env["step.app.person"].search([("email", "=", "pc@example.test")])
        self.env["step.app.membership"].create({"person_id": person.id, "company_id": self.company_a.id, "state": "active"})
        device = person.device_ids
        device.with_user(self.admin_a).action_revoke()
        self.assertTrue(device.revoked_at)
        self.assertApiError("session_invalid", self.ctx, session)
        # Si la persona también trabaja en otra empresa, decide un administrador del sistema.
        self.api.register("pb2@example.test", "clave-segura-2026", "Persona AB", {**DEVICE, "uuid": "x2"})
        both = self.env["step.app.person"].search([("email", "=", "pb2@example.test")])
        for company in (self.company_a, self.company_b):
            self.env["step.app.membership"].create({"person_id": both.id, "company_id": company.id, "state": "active"})
        with self.assertRaises(AccessError):
            both.device_ids.with_user(self.admin_a).action_revoke()
        with self.assertRaises(AccessError):
            both.with_user(self.admin_a).action_revoke_sessions()
        self.assertFalse(both.device_ids.revoked_at)

    def test_asistente_aprueba_y_asigna_en_un_paso_con_auditoria(self):
        wizard = self.env["step.app.grant.wizard"].with_user(self.admin_a).create(
            {"membership_id": self.m_a.id, "role_ids": [(6, 0, [self.role.id])]})
        wizard.action_assign()
        self.assertEqual(self.m_a.state, "active")
        self.assertEqual(self.m_a.grant_ids.role_id, self.role)
        # Repetirlo no duplica la concesión vigente.
        self.env["step.app.grant.wizard"].with_user(self.admin_a).create(
            {"membership_id": self.m_a.id, "role_ids": [(6, 0, [self.role.id])]}).action_assign()
        self.assertEqual(len(self.m_a.grant_ids), 1)
        actions = self.env["step.app.audit"].with_user(self.admin_a).search([("company_id", "=", self.company_a.id)]).mapped("action")
        self.assertIn("grant_created", actions)
        self.assertIn("membership_state", actions)
        self.assertFalse(self.env["step.app.audit"].with_user(self.admin_a).search([("company_id", "=", self.company_b.id)]))
        # Los usuarios de la API ven el acceso de inmediato.
        self.p_a.sudo()
        # El admin B no puede usar el asistente sobre la membresía de A.
        with self.assertRaises(AccessError):
            self.env["step.app.grant.wizard"].with_user(self.admin_b).create(
                {"membership_id": self.m_a.id, "role_ids": [(6, 0, [self.role.id])]}).action_assign()

    def test_la_auditoria_no_se_puede_alterar_ni_por_el_administrador(self):
        entry = self.env["step.app.audit"].with_user(self.admin_a).search([], limit=1)
        with self.assertRaises(Exception):
            entry.write({"action": "x"})

    def test_cron_vence_invitaciones_y_el_codigo_deja_de_servir(self):
        inv = self.env["step.app.invitation"].with_user(self.admin_a).create({"email": "nuevo@example.test", "company_id": self.company_a.id})
        token = inv.issue_token()
        inv.sudo().expires_at = fields.Datetime.now() - timedelta(minutes=1)
        self.assertEqual(self.env["step.app.invitation"]._cron_expire(), 1)
        self.assertEqual(inv.state, "expired")
        session = self.register("nuevo@example.test")
        self.env["step.app.person"].search([("email", "=", "nuevo@example.test")]).identity_ids.write({"email_verified": True})
        self.assertApiError("invalid_invitation", self.api.accept_invitation, self.ctx(session), token)


@tagged("post_install", "-at_install")
class TestRecovery(PortalCase):

    def _email(self):
        return "ana@example.test"

    def test_recuperacion_cambia_la_clave_y_cierra_todas_las_sesiones(self):
        old = self.register()
        other_phone = self.api.login(self._email(), "clave-segura-2026", {**DEVICE, "uuid": "telefono-2"})
        identity = self.env["step.app.identity"].search([("subject", "=", self._email())])
        token = self.api._issue_recovery(identity)
        self.api.recover_confirm(self._email(), token, "otra-clave-larga-2027")
        for s in (old, other_phone):
            self.assertApiError("session_invalid", self.ctx, s)
        self.assertApiError("invalid_credentials", self.api.login, self._email(), "clave-segura-2026", DEVICE)
        self.assertTrue(self.api.login(self._email(), "otra-clave-larga-2027", DEVICE)["access_token"])
        # El código se consume.
        self.assertApiError("invalid_recovery", self.api.recover_confirm, self._email(), token, "tercera-clave-larga-1")

    def test_codigo_incorrecto_vencido_o_clave_debil(self):
        self.register()
        identity = self.env["step.app.identity"].search([("subject", "=", self._email())])
        token = self.api._issue_recovery(identity)
        self.assertApiError("invalid_recovery", self.api.recover_confirm, self._email(), "inventado", "otra-clave-larga-2027")
        self.assertApiError("weak_password", self.api.recover_confirm, self._email(), token, "corta")
        identity.reset_expires_at = fields.Datetime.now() - timedelta(minutes=1)
        self.assertApiError("invalid_recovery", self.api.recover_confirm, self._email(), token, "otra-clave-larga-2027")

    def test_la_solicitud_responde_igual_exista_o_no_la_cuenta_y_no_revela_el_codigo(self):
        self.register()
        self.assertEqual(self.api.recover_request(self._email()), {"ok": True})
        self.assertEqual(self.api.recover_request("fantasma@example.test"), {"ok": True})
        self.assertTrue(self.env["step.app.identity"].search([("subject", "=", self._email())]).reset_token_hash)
        self.assertFalse(self.env["step.app.identity"].search([("subject", "=", "fantasma@example.test")]))

    def test_recuperar_levanta_el_bloqueo_por_intentos(self):
        self.register()
        for _i in range(5):
            self.assertApiError("invalid_credentials", self.api.login, self._email(), "incorrecta-123", DEVICE)
        identity = self.env["step.app.identity"].search([("subject", "=", self._email())])
        self.api.recover_confirm(self._email(), self.api._issue_recovery(identity), "otra-clave-larga-2027")
        self.assertTrue(self.api.login(self._email(), "otra-clave-larga-2027", DEVICE)["access_token"])

    def test_modulo_deshabilitado_sale_del_catalogo_y_de_los_permisos(self):
        session = self.register()
        person = self.env["step.app.person"].search([("email", "=", self._email())])
        self.activate(person, self.company_a, [self.role])
        ctx = self.ctx(session, self.company_a.step_app_org_uid)
        self.api.require(ctx, "demo.read")
        self.module.active = False
        self.assertApiError("forbidden", self.api.require, ctx, "demo.read")
        catalog = self.api.catalog(ctx, {"demo": 1})
        self.assertEqual(catalog["modules"], [])
        self.assertNotIn("demo", catalog["server_modules"])


@tagged("post_install", "-at_install")
class TestManualVerification(PortalCase):
    def test_verificacion_manual_es_solo_del_sistema_y_queda_auditada(self):
        self.register()
        identity = self.env["step.app.identity"].search([("subject", "=", "ana@example.test")])
        manager = self.env["res.users"].create({"name": "m", "login": "m@example.test", "company_id": self.company_a.id,
                                                "company_ids": [(6, 0, [self.company_a.id])],
                                                "groups_id": [(6, 0, [self.env.ref("base.group_user").id, self.env.ref("step_mobile_portal.group_step_app_manager").id])]})
        with self.assertRaises(AccessError):
            identity.with_user(manager).action_mark_email_verified()
        self.assertFalse(identity.email_verified)
        identity.action_mark_email_verified()
        self.assertTrue(identity.email_verified)
        self.assertTrue(self.env["step.app.audit"].search([("action", "=", "email_verified_by_admin")]))
