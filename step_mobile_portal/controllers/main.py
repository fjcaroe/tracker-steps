"""API HTTP /steps_app/v1. JSON plano (sin el sobre JSON-RPC de Odoo), sin cookies ni CSRF: la credencial es el Bearer."""
import functools
import json
import logging

from odoo import http
from odoo.http import request

from ..lib.step_app_core.errors import ApiError

_logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 256 * 1024
NO_STORE = [("Cache-Control", "no-store"), ("Content-Type", "application/json")]


def json_response(payload, status=200):
    return request.make_response(json.dumps(payload), status=status, headers=NO_STORE)


def read_body():
    raw = request.httprequest.get_data()
    if len(raw) > MAX_BODY_BYTES:
        raise ApiError("payload_too_large", 413)
    if not raw:
        return {}
    try:
        body = json.loads(raw)
    except ValueError:
        raise ApiError("invalid_json", 400)
    if not isinstance(body, dict):
        raise ApiError("invalid_json", 400)
    return body


def bearer():
    header = request.httprequest.headers.get("Authorization", "")
    return header[7:].strip() if header.lower().startswith("bearer ") else None


def handle(func):
    """Convierte ApiError en respuesta JSON y evita filtrar trazas internas."""
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return json_response(func(self, *args, **kwargs))
        except ApiError as exc:
            return json_response(exc.payload(), exc.status)
        except Exception:  # pragma: no cover
            _logger.exception("Error inesperado en la API de Steps App")
            return json_response({"ok": False, "error": "server_error", "terminal": False}, 500)
    return wrapper


def service():
    return request.env["step.app.api"].sudo()


def authenticate(need_org=True, allow_ended=False):
    org = request.httprequest.headers.get("X-Steps-Org")
    ctx = service().authenticate(bearer(), org_uid=org if need_org else None, allow_ended=allow_ended)
    if need_org and not org:
        raise ApiError("organization_required", 400)
    return ctx


class StepsAppController(http.Controller):

    @http.route("/steps_app/v1/health", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def health(self, **kw):
        return service().health()

    # --- Registro e inicio de sesión ---------------------------------
    @http.route("/steps_app/v1/auth/register", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def register(self, **kw):
        b = read_body()
        return {"ok": True, **service().register(b.get("email"), b.get("password"), b.get("name"), b.get("device"))}

    @http.route("/steps_app/v1/auth/verify_email", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def verify_email(self, **kw):
        b = read_body()
        return service().verify_email(b.get("email"), b.get("code"))

    @http.route("/steps_app/v1/auth/login", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def login(self, **kw):
        b = read_body()
        return {"ok": True, **service().login(b.get("email"), b.get("password"), b.get("device"))}

    @http.route("/steps_app/v1/auth/google", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def google(self, **kw):
        b = read_body()
        return {"ok": True, **service().login_google(b.get("id_token"), b.get("device"))}

    @http.route("/steps_app/v1/auth/test", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def test_provider(self, **kw):
        b = read_body()
        return {"ok": True, **service().login_test_provider(b.get("subject"), b.get("email"), b.get("name"), b.get("device"))}

    @http.route("/steps_app/v1/auth/apple", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def apple(self, **kw):
        raise ApiError("provider_not_configured", 503, "Inicio de sesión con Apple pendiente de configuración.")

    @http.route("/steps_app/v1/auth/refresh", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def refresh(self, **kw):
        return {"ok": True, **service().refresh(read_body().get("refresh_token"))}

    @http.route("/steps_app/v1/auth/logout", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def logout(self, **kw):
        return service().logout(authenticate(need_org=False))

    @http.route("/steps_app/v1/auth/link/google", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def link_google(self, **kw):
        return service().link_google(authenticate(need_org=False), read_body().get("id_token"))

    # --- Perfil e incorporación ---------------------------------------
    @http.route("/steps_app/v1/me", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def me(self, **kw):
        return service().me(authenticate(need_org=False))

    @http.route("/steps_app/v1/invitations/accept", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def accept(self, **kw):
        return service().accept_invitation(authenticate(need_org=False), read_body().get("token"))

    @http.route("/steps_app/v1/access/request", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def request_access(self, **kw):
        b = read_body()
        return service().request_access(authenticate(need_org=False), b.get("org_code"), b.get("note"))

    @http.route("/steps_app/v1/catalog", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def catalog(self, supported="", **kw):
        pairs = (item.split(":", 1) for item in supported.split(",") if ":" in item)
        support = {code: int(v) for code, v in pairs if v.isdigit()}
        return service().catalog(authenticate(), support)

    # --- Dispositivos y cuenta ----------------------------------------
    @http.route("/steps_app/v1/devices", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def devices(self, **kw):
        return service().list_devices(authenticate(need_org=False))

    @http.route("/steps_app/v1/devices/<int:device_id>/revoke", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def revoke_device(self, device_id, **kw):
        return service().revoke_own_device(authenticate(need_org=False), device_id)

    @http.route("/steps_app/v1/account/delete", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def delete_account(self, **kw):
        return service().delete_account(authenticate(need_org=False))
