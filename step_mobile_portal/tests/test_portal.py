from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import DEVICE, PortalCase


@tagged("post_install", "-at_install")
class TestOnboarding(PortalCase):

    def test_registro_sin_empresa_no_da_acceso(self):
        session = self.register()
        ctx = self.ctx(session)
        me = self.api.me(ctx)
        self.assertEqual(me["onboarding"], "no_organization")
        self.assertEqual(me["memberships"], [])
        # No se crea usuario interno ni empleado.
        self.assertFalse(self.env["res.users"].search([("login", "=", "ana@example.test")]))
        self.assertApiError("organization_not_authorized", self.ctx, session, self.company_a.step_app_org_uid)
        self.assertApiError("organization_required", self.api.catalog, ctx)

    def test_correo_duplicado_y_contrasena_debil(self):
        self.register()
        self.assertApiError("email_in_use", self.register)
        self.assertApiError("weak_password", self.register, "otra@example.test", "corta")
        self.assertApiError("invalid_email", self.register, "no-es-correo")

    def test_login_bloquea_tras_intentos_fallidos(self):
        self.register()
        for _i in range(5):
            self.assertApiError("invalid_credentials", self.api.login, "ana@example.test", "incorrecta-123", DEVICE)
        self.assertApiError("too_many_attempts", self.api.login, "ana@example.test", "clave-segura-2026", DEVICE)

    def test_invitacion_requiere_codigo_valido_y_correo_verificado(self):
        session = self.register()
        invitation = self.env["step.app.invitation"].create({
            "email": "ana@example.test", "company_id": self.company_a.id,
            "line_ids": [(0, 0, {"role_id": self.role.id})]})
        token = invitation.issue_token()
        ctx = self.ctx(session)
        self.assertApiError("invalid_invitation", self.api.accept_invitation, ctx, "codigo-inventado")
        # Correo sin verificar: no puede aceptar aunque tenga el código.
        self.assertApiError("email_not_verified", self.api.accept_invitation, ctx, token)
        identity = self.env["step.app.person"].search([("email", "=", "ana@example.test")]).identity_ids
        identity.write({"email_verified": True})
        self.api.accept_invitation(ctx, token)
        ctx = self.ctx(session, self.company_a.step_app_org_uid)
        self.assertEqual({m["code"] for m in self.api.catalog(ctx, {"demo": 1})["modules"]}, {"demo"})
        # El código se consume.
        self.assertApiError("invalid_invitation", self.api.accept_invitation, ctx, token)

    def test_invitacion_para_otro_correo_no_sirve(self):
        session = self.register()
        invitation = self.env["step.app.invitation"].create({"email": "otra@example.test", "company_id": self.company_a.id})
        token = invitation.issue_token()
        self.env["step.app.person"].search([("email", "=", "ana@example.test")]).identity_ids.write({"email_verified": True})
        self.assertApiError("email_not_verified", self.api.accept_invitation, self.ctx(session), token)

    def test_solicitud_por_codigo_de_empresa_queda_pendiente(self):
        session = self.register()
        ctx = self.ctx(session)
        self.api.request_access(ctx, self.company_a.step_app_org_code, "Soy conductor")
        self.assertEqual(self.api.me(ctx)["onboarding"], "request_pending")
        self.assertApiError("organization_not_authorized", self.ctx, session, self.company_a.step_app_org_uid)
        self.assertApiError("invalid_org_code", self.api.request_access, ctx, "ZZZZZZZZ")


@tagged("post_install", "-at_install")
class TestIdentity(PortalCase):

    def test_proveedor_externo_no_se_une_por_correo(self):
        password_session = self.register("ana@example.test")
        google = self.api.login_test_provider("sub-777", "ana@example.test", "Otra Ana", {**DEVICE, "uuid": "dev-2"})
        mine = self.api.me(self.ctx(password_session))["person"]["id"]
        other = self.api.me(self.ctx(google))["person"]["id"]
        self.assertNotEqual(mine, other)
        # Mismo (proveedor, sub) vuelve a la misma persona.
        again = self.api.login_test_provider("sub-777", "ana@example.test", "Otra Ana", {**DEVICE, "uuid": "dev-3"})
        self.assertEqual(self.api.me(self.ctx(again))["person"]["id"], other)

    def test_google_sin_configuracion_o_con_token_invalido_se_rechaza(self):
        self.assertApiError("provider_not_configured", self.api.login_google, "x.y.z", DEVICE)
        self.env["ir.config_parameter"].sudo().set_param("step_app.google_client_ids", "cliente-1")
        exc = self.assertApiError("invalid_token", self.api.login_google, "no-es-un-jwt", DEVICE)
        self.assertEqual(exc.status, 401)

    def test_proveedor_de_prueba_apagado_por_defecto(self):
        self.env["ir.config_parameter"].sudo().set_param("step_app.allow_test_provider", "0")
        self.assertApiError("provider_not_configured", self.api.login_test_provider, "s", "a@example.test", "A", DEVICE)


@tagged("post_install", "-at_install")
class TestSessions(PortalCase):

    def test_renovacion_rota_y_detecta_reutilizacion(self):
        first = self.register()
        second = self.api.refresh(first["refresh_token"])
        self.assertNotEqual(first["refresh_token"], second["refresh_token"])
        self.ctx(second)
        # Reusar el refresh anterior revoca la sesión entera.
        self.assertApiError("session_revoked", self.api.refresh, first["refresh_token"])
        self.assertApiError("session_invalid", self.ctx, second)

    def test_token_de_acceso_vencido_y_logout(self):
        session = self.register()
        record = self.env["step.app.session"].search([("person_id.email", "=", "ana@example.test")])
        record.write({"access_expires_at": fields.Datetime.now() - timedelta(minutes=1)})
        self.assertApiError("token_expired", self.ctx, session)
        fresh = self.api.refresh(session["refresh_token"])
        self.api.logout(self.ctx(fresh))
        self.assertApiError("session_invalid", self.ctx, fresh)

    def test_dispositivo_revocado_cierra_sesion_y_no_vuelve(self):
        session = self.register()
        device = self.env["step.app.device"].search([("uuid", "=", "dev-1")])
        device.action_revoke()
        self.assertApiError("session_invalid", self.ctx, session)
        self.assertApiError("device_revoked", self.api.login, "ana@example.test", "clave-segura-2026", DEVICE)

    def test_dispositivo_compartido_exige_emparejamiento(self):
        self.assertApiError("shared_device_pairing_required", self.register, "t@example.test", "clave-segura-2026",
                            {**DEVICE, "kind": "shared"})

    def test_eliminacion_de_cuenta_retira_acceso_y_conserva_registros(self):
        session = self.register()
        person = self.env["step.app.person"].search([("email", "=", "ana@example.test")])
        self.activate(person, self.company_a)
        self.api.delete_account(self.ctx(session))
        self.assertApiError("session_invalid", self.ctx, session)
        self.assertApiError("invalid_credentials", self.api.login, "ana@example.test", "clave-segura-2026", DEVICE)
        self.assertEqual(person.state, "deletion_requested")
        self.assertTrue(self.env["step.app.audit"].search([("person_id", "=", person.id), ("action", "=", "deletion_requested")]))


@tagged("post_install", "-at_install")
class TestAuthorization(PortalCase):

    def setUp(self):
        super().setUp()
        self.session = self.register()
        self.person = self.env["step.app.person"].search([("email", "=", "ana@example.test")])

    def test_catalogo_solo_lo_asignado_y_compatible(self):
        self.activate(self.person, self.company_a, [self.role])
        ctx = self.ctx(self.session, self.company_a.step_app_org_uid)
        catalog = self.api.catalog(ctx, {"demo": 1})
        self.assertEqual([m["code"] for m in catalog["modules"]], ["demo"])
        self.assertEqual(catalog["modules"][0]["permissions"], ["demo.read", "demo.write"])
        self.assertTrue(catalog["offline_until"])
        # Una app que no entiende el contrato no recibe el módulo y se le avisa.
        old = self.api.catalog(ctx, {"demo": 0})
        self.assertEqual(old["modules"], [])
        self.assertEqual(old["incompatible_modules"][0]["reason"], "app_update_required")

    def test_aislamiento_entre_empresas(self):
        self.activate(self.person, self.company_a, [self.role])
        self.assertApiError("organization_not_authorized", self.ctx, self.session, self.company_b.step_app_org_uid)
        # Un identificador de organización inexistente da la misma respuesta (no revela empresas).
        self.assertApiError("organization_not_authorized", self.ctx, self.session, "no-existe")

    def test_revocar_concesion_o_membresia_cambia_el_acceso_real(self):
        membership = self.activate(self.person, self.company_a, [self.role])
        org = self.company_a.step_app_org_uid
        self.api.require(self.ctx(self.session, org), "demo.write")
        membership.grant_ids.action_revoke()
        self.assertApiError("forbidden", self.api.require, self.ctx(self.session, org), "demo.write")
        self.assertEqual(self.api.catalog(self.ctx(self.session, org), {"demo": 1})["modules"], [])
        # Las concesiones no se borran: conservan la historia.
        self.assertTrue(membership.grant_ids.revoked_at)
        membership.action_suspend()
        self.assertApiError("organization_not_authorized", self.ctx, self.session, org)

    def test_suspender_una_empresa_no_afecta_a_otra_membresia(self):
        a = self.activate(self.person, self.company_a, [self.role])
        self.activate(self.person, self.company_b, [self.role])
        a.action_suspend()
        self.assertApiError("organization_not_authorized", self.ctx, self.session, self.company_a.step_app_org_uid)
        self.api.catalog(self.ctx(self.session, self.company_b.step_app_org_uid), {"demo": 1})

    def test_concesion_vencida_no_otorga_permisos(self):
        membership = self.activate(self.person, self.company_a)
        self.env["step.app.grant"].create({
            "membership_id": membership.id, "module_id": self.module.id, "role_id": self.role.id,
            "valid_to": fields.Datetime.now() - timedelta(hours=1)})
        self.assertApiError("forbidden", self.api.require, self.ctx(self.session, self.company_a.step_app_org_uid), "demo.read")

    def test_vinculo_con_contacto_es_explicito_y_unico(self):
        membership = self.activate(self.person, self.company_a)
        partner = self.env["res.partner"].create({"name": "Conductor Ficticio"})
        membership.partner_id = partner
        other = self.env["step.app.person"].create({"name": "Otra persona"})
        with self.assertRaises(Exception):
            self.env["step.app.membership"].create(
                {"person_id": other.id, "company_id": self.company_a.id, "state": "active", "partner_id": partner.id})
        self.assertTrue(self.env["step.app.audit"].search([("person_id", "=", self.person.id), ("action", "=", "membership_link")]))

    def test_administrador_de_una_empresa_no_ve_la_otra(self):
        self.activate(self.person, self.company_a, [self.role])
        admin = self.env["res.users"].create({
            "name": "Admin A", "login": "admin-a@example.test", "company_id": self.company_a.id,
            "company_ids": [(6, 0, [self.company_a.id])],
            "groups_id": [(6, 0, [self.env.ref("step_mobile_portal.group_step_app_manager").id, self.env.ref("base.group_user").id])]})
        visible = self.env["step.app.membership"].with_user(admin).with_company(self.company_a).search([])
        self.assertEqual(visible.mapped("company_id"), self.company_a)
        hidden = self.env["step.app.membership"].with_user(admin).search([("company_id", "=", self.company_b.id)])
        self.assertFalse(hidden)

    def test_auditoria_es_de_solo_lectura(self):
        entry = self.env["step.app.audit"].search([], limit=1)
        with self.assertRaises(Exception):
            entry.write({"action": "x"})
        with self.assertRaises(Exception):
            entry.unlink()
