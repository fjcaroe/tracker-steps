"""Capa de servicio de la API de Steps App.

Los controladores solo traducen HTTP; todas las reglas viven aquí para poder probarlas con TransactionCase.

Sobre `sudo()`: la API es pública a nivel HTTP (la credencial es el token de sesión), así que el entorno de
la petición no puede leer estos modelos. Se usa `sudo()` únicamente DESPUÉS de autenticar la sesión y toda
consulta posterior se acota explícitamente a la persona y a la empresa autorizadas; nunca se confía en un
`company_id` recibido del cliente.
"""
import logging
from datetime import timedelta

from odoo import _, api, fields, models

from ..lib.step_app_core import authz, passwords, providers, sessions, tokens
from ..lib.step_app_core.errors import ApiError

_logger = logging.getLogger(__name__)

API_VERSION = 1
MAX_DEVICES = 20
LOCK_AFTER_FAILURES = 5
LOCK_MINUTES = 15
VERIFY_HOURS = 48
TOUCH_EVERY = timedelta(seconds=60)


class StepAppApi(models.AbstractModel):
    _name = "step.app.api"
    _description = "Servicio de la API de Steps App"

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @api.model
    def _now(self):
        return fields.Datetime.now()

    @api.model
    def _param(self, key, default=""):
        return self.env["ir.config_parameter"].sudo().get_param(key, default)

    @api.model
    def health(self):
        return {"ok": True, "api_version": API_VERSION, "server_time": self._now().isoformat() + "Z",
                "providers": self._providers_available()}

    @api.model
    def _providers_available(self):
        return {
            "password": True,
            "google": bool(self._google_client_ids()),
            "apple": False,
            "test": self._param("step_app.allow_test_provider") == "1",
        }

    @api.model
    def _google_client_ids(self):
        return [c.strip() for c in self._param("step_app.google_client_ids").split(",") if c.strip()]

    # ------------------------------------------------------------------
    # Dispositivos y sesiones
    # ------------------------------------------------------------------
    @api.model
    def _device_for(self, person, info):
        info = info if isinstance(info, dict) else {}
        uuid_ = str(info.get("uuid") or "").strip()[:64]
        if not uuid_:
            raise ApiError("device_required", 400, _("Falta el identificador del dispositivo."))
        if info.get("kind") == "shared":
            # El modo tótem exige emparejamiento propio (pendiente): no se habilita con una cuenta personal.
            raise ApiError("shared_device_pairing_required", 403, _("Un dispositivo compartido requiere emparejamiento."))
        Device = self.env["step.app.device"].sudo()
        device = Device.search([("person_id", "=", person.id), ("uuid", "=", uuid_)], limit=1)
        if device and device.revoked_at:
            raise ApiError("device_revoked", 403, _("Este dispositivo fue revocado."))
        values = {"platform": str(info.get("platform") or "")[:32], "label": str(info.get("label") or "")[:64],
                  "app_version": str(info.get("app_version") or "")[:32], "last_seen_at": self._now()}
        if device:
            device.write(values)
            return device
        if Device.search_count([("person_id", "=", person.id), ("revoked_at", "=", False)]) >= MAX_DEVICES:
            raise ApiError("too_many_devices", 409, _("Demasiados dispositivos activos. Revoque alguno."))
        return Device.create({"person_id": person.id, "uuid": uuid_, "kind": "personal", **values})

    @api.model
    def _open_session(self, person, device_info):
        if person.state != "active":
            raise ApiError("account_not_active", 403, _("La cuenta no está activa."))
        device = self._device_for(person, device_info)
        now = self._now()
        pair = sessions.issue(now)
        self.env["step.app.session"].sudo().create({
            "person_id": person.id, "device_id": device.id, "access_hash": pair["access_hash"],
            "access_expires_at": pair["access_expires_at"], "refresh_hash": pair["refresh_hash"],
            "refresh_expires_at": pair["refresh_expires_at"], "last_used_at": now, "validated_at": now})
        return {"access_token": pair["access"], "refresh_token": pair["refresh"],
                "access_expires_at": pair["access_expires_at"].isoformat() + "Z",
                "refresh_expires_at": pair["refresh_expires_at"].isoformat() + "Z"}

    @api.model
    def refresh(self, refresh_token):
        """Rota el par de tokens. Presentar un refresh ya usado revoca la sesión: indica robo o copia."""
        Session = self.env["step.app.session"].sudo()
        digest = tokens.hash_token(refresh_token or "")
        record = Session.search(["|", ("refresh_hash", "=", digest), ("previous_refresh_hash", "=", digest)], limit=1)
        now = self._now()
        data = None if not record else {
            "refresh_hash": record.refresh_hash, "previous_refresh_hash": record.previous_refresh_hash,
            "refresh_expires_at": record.refresh_expires_at, "revoked_at": record.revoked_at}
        verdict = sessions.classify_refresh(data, refresh_token or "", now)
        if verdict == sessions.REUSED:
            record.write({"revoked_at": now, "revoked_reason": "refresh_reuse"})
            self.env["step.app.audit"].log("refresh_reuse_detected", person=record.person_id)
            raise ApiError("session_revoked", 401, _("Sesión cerrada por seguridad. Vuelva a iniciar sesión."))
        if verdict != sessions.OK:
            raise ApiError("session_invalid", 401, _("La sesión no es válida. Vuelva a iniciar sesión."))
        person = record.person_id
        if person.state != "active" or record.device_id.revoked_at:
            raise ApiError("session_revoked", 401, _("La sesión fue revocada."))
        pair = sessions.issue(now)
        record.write({"access_hash": pair["access_hash"], "access_expires_at": pair["access_expires_at"],
                      "previous_refresh_hash": record.refresh_hash, "refresh_hash": pair["refresh_hash"],
                      "refresh_expires_at": pair["refresh_expires_at"], "last_used_at": now})
        return {"access_token": pair["access"], "refresh_token": pair["refresh"],
                "access_expires_at": pair["access_expires_at"].isoformat() + "Z",
                "refresh_expires_at": pair["refresh_expires_at"].isoformat() + "Z"}

    @api.model
    def logout(self, ctx):
        ctx["session"].write({"revoked_at": self._now(), "revoked_reason": "logout"})
        return {"ok": True}

    # ------------------------------------------------------------------
    # Registro e inicio de sesión
    # ------------------------------------------------------------------
    @api.model
    def register(self, email, password, name, device):
        email = passwords.normalize_email(email)
        if not passwords.valid_email(email):
            raise ApiError("invalid_email", 422, _("Correo inválido."))
        problem = passwords.password_problem(password, email)
        if problem:
            raise ApiError("weak_password", 422, _("La contraseña no cumple la política (%s).", problem))
        name = (name or "").strip()[:128] or email.split("@")[0]
        Identity = self.env["step.app.identity"].sudo()
        if Identity.search_count([("provider", "=", "password"), ("subject", "=", email)]):
            raise ApiError("email_in_use", 409, _("Ese correo ya tiene una cuenta."))
        person = self.env["step.app.person"].sudo().create({"name": name, "email": email})
        identity = Identity.create({"person_id": person.id, "provider": "password", "subject": email, "email": email,
                                    "secret_hash": passwords.hash_password(password)})
        self._issue_verification(identity)
        result = self._open_session(person, device)
        self.env["step.app.audit"].log("person_registered", person=person, detail="password")
        return result

    @api.model
    def _issue_verification(self, identity):
        token = tokens.new_token(24)
        identity.write({"verify_token_hash": tokens.hash_token(token),
                        "verify_expires_at": self._now() + timedelta(hours=VERIFY_HOURS)})
        if self._param("step_app.send_mail") == "1":
            self.env["mail.mail"].sudo().create({
                "subject": _("Confirme su correo de Steps"), "email_to": identity.email,
                "body_html": _("<p>Su código de verificación es <b>%s</b>. Vence en %s horas.</p>", token, VERIFY_HOURS),
            }).send()
        else:
            _logger.info("Correo de verificación no enviado (step_app.send_mail desactivado) para identidad %s", identity.id)
        return token

    @api.model
    def verify_email(self, email, token):
        identity = self.env["step.app.identity"].sudo().search(
            [("provider", "=", "password"), ("subject", "=", passwords.normalize_email(email))], limit=1)
        if (not identity or not tokens.verify_token(token, identity.verify_token_hash)
                or not identity.verify_expires_at or identity.verify_expires_at < self._now()):
            raise ApiError("invalid_verification", 400, _("Código inválido o vencido."))
        identity.write({"email_verified": True, "verify_token_hash": False, "verify_expires_at": False})
        self.env["step.app.audit"].log("email_verified", person=identity.person_id)
        return {"ok": True}

    @api.model
    def login(self, email, password, device):
        email = passwords.normalize_email(email)
        identity = self.env["step.app.identity"].sudo().search(
            [("provider", "=", "password"), ("subject", "=", email)], limit=1)
        now = self._now()
        if identity and identity.locked_until and identity.locked_until > now:
            raise ApiError("too_many_attempts", 429, _("Demasiados intentos. Espere unos minutos."))
        valid = passwords.verify_password(password, identity.secret_hash if identity else None)
        if not identity or not valid:
            if identity:
                failures = identity.failed_attempts + 1
                identity.write({"failed_attempts": failures,
                                "locked_until": now + timedelta(minutes=LOCK_MINUTES) if failures >= LOCK_AFTER_FAILURES else False})
            raise ApiError("invalid_credentials", 401, _("Correo o contraseña incorrectos."))
        identity.write({"failed_attempts": 0, "locked_until": False})
        return self._open_session(identity.person_id, device)

    @api.model
    def login_google(self, id_token, device):
        try:
            claims = providers.verify_google_id_token(id_token, self._google_client_ids())
        except providers.ProviderError as exc:
            status = 503 if exc.code == "provider_not_configured" else 401
            raise ApiError(exc.code, status, _("No se pudo validar la cuenta de Google."))
        return self._login_external("google", claims, device)

    @api.model
    def login_test_provider(self, subject, email, name, device):
        """Proveedor de prueba: solo existe con `step_app.allow_test_provider=1`. Jamás debe activarse en producción."""
        if self._param("step_app.allow_test_provider") != "1":
            raise ApiError("provider_not_configured", 503, _("Proveedor no disponible."))
        claims = {"subject": str(subject), "email": passwords.normalize_email(email), "email_verified": True, "name": name or ""}
        return self._login_external("test", claims, device)

    @api.model
    def _login_external(self, provider, claims, device):
        """Se identifica por (proveedor, sub). Un correo coincidente NO une la cuenta con otra persona existente."""
        Identity = self.env["step.app.identity"].sudo()
        identity = Identity.search([("provider", "=", provider), ("subject", "=", claims["subject"])], limit=1)
        if not identity:
            person = self.env["step.app.person"].sudo().create(
                {"name": claims["name"] or claims["email"] or "Persona", "email": claims["email"] or False})
            identity = Identity.create({"person_id": person.id, "provider": provider, "subject": claims["subject"],
                                        "email": claims["email"], "email_verified": claims["email_verified"]})
            self.env["step.app.audit"].log("person_registered", person=person, detail=provider)
        else:
            identity.write({"email": claims["email"], "email_verified": claims["email_verified"]})
        return self._open_session(identity.person_id, device)

    @api.model
    def link_google(self, ctx, id_token):
        """Vincular otro proveedor exige una sesión válida de la cuenta destino (prueba de control), no coincidencia de correo."""
        try:
            claims = providers.verify_google_id_token(id_token, self._google_client_ids())
        except providers.ProviderError as exc:
            raise ApiError(exc.code, 503 if exc.code == "provider_not_configured" else 401)
        Identity = self.env["step.app.identity"].sudo()
        existing = Identity.search([("provider", "=", "google"), ("subject", "=", claims["subject"])], limit=1)
        if existing and existing.person_id != ctx["person"]:
            raise ApiError("identity_in_use", 409, _("Esa cuenta de Google ya pertenece a otra persona."))
        if not existing:
            Identity.create({"person_id": ctx["person"].id, "provider": "google", "subject": claims["subject"],
                             "email": claims["email"], "email_verified": claims["email_verified"]})
            self.env["step.app.audit"].log("identity_linked", person=ctx["person"], detail="google")
        return {"ok": True}

    # ------------------------------------------------------------------
    # Autenticación de cada llamada
    # ------------------------------------------------------------------
    @api.model
    def authenticate(self, access_token, org_uid=None):
        """Resuelve sesión, persona y (si se indica) membresía activa. Lanza ApiError ante cualquier problema."""
        if not access_token:
            raise ApiError("unauthenticated", 401, _("Falta la sesión."))
        Session = self.env["step.app.session"].sudo()
        record = Session.search([("access_hash", "=", tokens.hash_token(access_token))], limit=1)
        now = self._now()
        data = None if not record else {"access_hash": record.access_hash, "access_expires_at": record.access_expires_at,
                                       "revoked_at": record.revoked_at}
        verdict = sessions.classify_access(data, access_token, now)
        if verdict == sessions.EXPIRED:
            raise ApiError("token_expired", 401, _("La sesión venció; renuévela."))
        if verdict != sessions.OK:
            raise ApiError("session_invalid", 401, _("La sesión no es válida."))
        person, device = record.person_id, record.device_id
        if person.state != "active" or device.revoked_at:
            raise ApiError("session_revoked", 401, _("La sesión fue revocada."))
        if not record.last_used_at or now - record.last_used_at > TOUCH_EVERY:
            record.write({"last_used_at": now})
        ctx = {"session": record, "person": person, "device": device, "now": now, "membership": None, "company": None}
        if org_uid:
            company = self.env["res.company"].sudo().search([("step_app_org_uid", "=", org_uid)], limit=1)
            membership = company and self.env["step.app.membership"].sudo().search(
                [("person_id", "=", person.id), ("company_id", "=", company.id)], limit=1)
            # Misma respuesta para «empresa inexistente» y «sin membresía»: no revela qué empresas existen.
            if not membership or not authz.membership_active_at(self._membership_dict(membership), now):
                raise ApiError("organization_not_authorized", 403, _("No tiene acceso activo a esa empresa."))
            ctx.update(membership=membership, company=company)
        return ctx

    @api.model
    def _membership_dict(self, membership):
        return {"id": membership.id, "state": membership.state, "valid_from": membership.valid_from,
                "valid_to": membership.valid_to}

    @api.model
    def _grant_dicts(self, membership):
        return [{"id": g.id, "membership_id": g.membership_id.id, "module": g.module_id.code, "role": g.role_id.code,
                 "valid_from": g.valid_from, "valid_to": g.valid_to, "revoked_at": g.revoked_at,
                 "scope_ids": g.scope_ids or []} for g in membership.sudo().grant_ids]

    @api.model
    def _role_permissions(self):
        roles = self.env["step.app.module.role"].sudo().search([("module_id.active", "=", True)])
        return {(r.module_id.code, r.code): r.permission_list() for r in roles}

    @api.model
    def permissions(self, ctx):
        if not ctx["membership"]:
            return set()
        return authz.effective_permissions(self._membership_dict(ctx["membership"]), self._grant_dicts(ctx["membership"]),
                                           self._role_permissions(), ctx["now"])

    @api.model
    def require(self, ctx, permission):
        if permission not in self.permissions(ctx):
            raise ApiError("forbidden", 403, _("No tiene permiso para esta acción."))

    @api.model
    def grants_for(self, ctx, module):
        """Concesiones vigentes (módulo dado) de la membresía activa: para validar alcance en cada módulo."""
        return [g for g in self._grant_dicts(ctx["membership"])
                if g["module"] == module and authz.grant_active_at(g, ctx["now"])]

    # ------------------------------------------------------------------
    # Perfil, catálogo, incorporación
    # ------------------------------------------------------------------
    @api.model
    def me(self, ctx):
        person = ctx["person"]
        identities = person.sudo().identity_ids
        memberships = [{
            "org_uid": m.company_id.step_app_org_uid, "name": m.company_id.name, "state": m.state,
        } for m in person.sudo().membership_ids]
        return {
            "ok": True, "person": {"id": person.id, "name": person.name, "email": person.email, "state": person.state},
            "email_verified": any(i.email_verified for i in identities),
            "providers": sorted(set(identities.mapped("provider"))),
            "memberships": memberships,
            "onboarding": self._onboarding_state(memberships),
            "device": {"id": ctx["device"].id},
        }

    @api.model
    def _onboarding_state(self, memberships):
        if any(m["state"] == "active" for m in memberships):
            return "ready"
        if any(m["state"] == "invited" for m in memberships):
            return "invitation_pending"
        if any(m["state"] == "requested" for m in memberships):
            return "request_pending"
        return "no_organization"

    @api.model
    def catalog(self, ctx, supported=None):
        """Módulos habilitados para la empresa activa. `supported` mapea módulo -> versión de contrato que la app entiende."""
        if not ctx["membership"]:
            raise ApiError("organization_required", 400, _("Falta la empresa activa."))
        supported = supported or {}
        now = ctx["now"]
        grants = self._grant_dicts(ctx["membership"])
        modules = self.env["step.app.module"].sudo().search([])
        installed = {m.code for m in modules}
        enabled = authz.enabled_modules(self._membership_dict(ctx["membership"]), grants, installed, now)
        by_code = {m.code: m for m in modules}
        roles = self._role_permissions()
        result, incompatible = [], []
        for code in enabled:
            module = by_code[code]
            if supported.get(code) != module.contract_version:
                incompatible.append({"code": code, "server_contract": module.contract_version, "reason": "app_update_required"})
                continue
            active_roles = sorted({g["role"] for g in grants if g["module"] == code and authz.grant_active_at(g, now)})
            permissions = sorted({p for r in active_roles for p in roles.get((code, r), ())})
            result.append({"code": code, "name": module.name, "icon": module.icon, "contract_version": module.contract_version,
                           "roles": active_roles, "permissions": permissions})
        ctx["session"].write({"validated_at": now})
        hours = ctx["company"].step_app_offline_hours or authz.DEFAULT_OFFLINE_HOURS
        return {"ok": True, "server_time": now.isoformat() + "Z", "organization": {"org_uid": ctx["company"].step_app_org_uid, "name": ctx["company"].name},
                "modules": result, "incompatible_modules": incompatible,
                "offline_until": authz.offline_until(now, hours).isoformat() + "Z"}

    @api.model
    def accept_invitation(self, ctx, token):
        """El código prueba que quien acepta recibió la invitación; además el correo debe ser el invitado y estar verificado."""
        digest = tokens.hash_token(token or "")
        invitation = self.env["step.app.invitation"].sudo().search([("token_hash", "=", digest), ("state", "=", "pending")], limit=1)
        now = ctx["now"]
        if not invitation or not invitation.expires_at or invitation.expires_at < now:
            raise ApiError("invalid_invitation", 400, _("Invitación inválida o vencida."))
        person = ctx["person"]
        verified = {i.email for i in person.sudo().identity_ids if i.email_verified and i.email}
        if invitation.email not in verified:
            raise ApiError("email_not_verified", 403, _("Verifique el correo invitado antes de aceptar."))
        Membership = self.env["step.app.membership"].sudo()
        membership = Membership.search([("person_id", "=", person.id), ("company_id", "=", invitation.company_id.id)], limit=1)
        if membership and membership.state == "active":
            pass
        elif membership:
            membership.write({"state": "active"})
        else:
            membership = Membership.create({"person_id": person.id, "company_id": invitation.company_id.id, "state": "active"})
        for line in invitation.line_ids:
            self.env["step.app.grant"].sudo().create({
                "membership_id": membership.id, "module_id": line.role_id.module_id.id, "role_id": line.role_id.id,
                "valid_to": line.valid_to or False})
        invitation.write({"state": "accepted", "token_hash": False, "membership_id": membership.id})
        self.env["step.app.audit"].log("invitation_accepted", person=person, company=invitation.company_id)
        return {"ok": True, "org_uid": invitation.company_id.step_app_org_uid}

    @api.model
    def request_access(self, ctx, org_code, note=""):
        company = self.env["res.company"].sudo().search([("step_app_org_code", "=", (org_code or "").strip().upper())], limit=1)
        if not company:
            raise ApiError("invalid_org_code", 404, _("Código de empresa no reconocido."))
        Membership = self.env["step.app.membership"].sudo()
        membership = Membership.search([("person_id", "=", ctx["person"].id), ("company_id", "=", company.id)], limit=1)
        if membership and membership.state in ("active", "requested", "invited", "suspended"):
            return {"ok": True, "state": membership.state}
        values = {"person_id": ctx["person"].id, "company_id": company.id, "state": "requested", "request_note": (note or "")[:500]}
        if membership:
            membership.write(values)
        else:
            Membership.create(values)
        return {"ok": True, "state": "requested"}

    @api.model
    def list_devices(self, ctx):
        return {"ok": True, "devices": [{
            "id": d.id, "label": d.label, "platform": d.platform, "app_version": d.app_version,
            "last_seen_at": d.last_seen_at.isoformat() + "Z" if d.last_seen_at else None,
            "revoked": bool(d.revoked_at), "current": d == ctx["device"],
        } for d in ctx["person"].sudo().device_ids]}

    @api.model
    def revoke_own_device(self, ctx, device_id):
        device = ctx["person"].sudo().device_ids.filtered(lambda d: d.id == int(device_id))
        if not device:
            raise ApiError("device_not_found", 404, _("Dispositivo no encontrado."))
        device.action_revoke()
        return {"ok": True}

    @api.model
    def delete_account(self, ctx):
        ctx["person"].request_deletion()
        return {"ok": True}
