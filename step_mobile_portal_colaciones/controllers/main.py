"""Colaciones en la app Steps. Separa dos experiencias con permisos distintos:

- persona (`colaciones.read_own`): solo su habilitación y sus registros, a través del trabajador vinculado a su membresía;
- operador (`colaciones.register`): registra entregas en los tótems de su empresa y alcance, con su sesión personal.

El token del tótem nunca sale de Odoo y no sustituye a la sesión personal.
"""
from datetime import datetime, timezone

from odoo import fields, http
from odoo.http import request

from odoo.addons.step_mobile_portal.controllers.main import authenticate, handle, read_body, service
from odoo.addons.step_mobile_portal.lib.step_app_core import authz
from odoo.addons.step_mobile_portal.lib.step_app_core.errors import ApiError

MODULE = "colaciones"
MAX_RECORDS = 100


def _captured_at(record, now):
    """Instante de captura del evento: el del dispositivo si es offline (acotado por el tótem), el del servidor si no."""
    if not record.get("offline", True):
        return now
    try:
        parsed = datetime.fromisoformat(str(record.get("event_datetime", "")).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _totem_in_scope(ctx, totem_id):
    """Tótem de la empresa activa y dentro del alcance de alguna concesión de operador vigente."""
    try:
        totem_id = int(totem_id)
    except (TypeError, ValueError):
        return None
    totem = request.env["step.colacion.totem"].sudo().search(
        [("id", "=", totem_id), ("company_id", "=", ctx["company"].id), ("active", "=", True)], limit=1)
    return totem or None


class ColacionesController(http.Controller):

    @http.route("/steps_app/v1/colaciones/me", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def me(self, **kw):
        api = service()
        ctx = authenticate()
        api.require(ctx, "colaciones.read_own")
        employee = ctx["membership"].employee_id
        if not employee:
            return {"ok": True, "linked": False}
        Registration = request.env["step.colacion.registration"].sudo()
        domain = [("employee_id", "=", employee.id), ("company_id", "=", ctx["company"].id), ("state", "!=", "cancelled")]
        recent = Registration.search(domain, limit=30)
        today = Registration._meal_date_for(ctx["now"], ctx["company"])
        todays = recent.filtered(lambda r: r.meal_date == today)[:1]
        return {
            "ok": True, "linked": True, "employee": employee.name, "eligible": bool(employee.meal_eligible),
            "today": {"registered": bool(todays), "registration": todays.name if todays else None,
                      "event_datetime": todays.event_datetime.isoformat() + "Z" if todays else None},
            "recent": [{"registration": r.name, "meal_date": fields.Date.to_string(r.meal_date),
                        "product": r.product_tmpl_id.display_name} for r in recent],
        }

    @http.route("/steps_app/v1/colaciones/totems", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def totems(self, **kw):
        api = service()
        ctx = authenticate()
        api.require(ctx, "colaciones.register")
        grants = [g for g in api.grants_for(ctx, MODULE) if g["role"] == "operador"]
        totems = request.env["step.colacion.totem"].sudo().search(
            [("company_id", "=", ctx["company"].id), ("active", "=", True)])
        return {"ok": True, "max_batch_records": MAX_RECORDS, "totems": [{
            "id": t.id, "name": t.name, "code": t.code, "product": t.product_tmpl_id.display_name,
            "identification_method": t.identification_method, "allow_offline": t.allow_offline,
            "offline_max_hours": t.offline_max_hours,
        } for t in totems if any(authz.scope_allows(g, t.id) for g in grants)]}

    @http.route("/steps_app/v1/colaciones/register", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def register(self, **kw):
        """Registra entregas por lote. Cada captura recibe su propio estado; una inválida no aborta el lote."""
        api = service()
        ctx = authenticate(allow_ended=True)
        body = read_body()
        records = body.get("records")
        if not isinstance(records, list) or len(records) > MAX_RECORDS:
            raise ApiError("invalid_batch", 422, "El lote debe ser una lista de hasta %d capturas." % MAX_RECORDS)
        totem = _totem_in_scope(ctx, body.get("totem_id"))
        if not totem:
            raise ApiError("totem_not_authorized", 403)
        results, allowed = {}, []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                results[index] = {"client_uuid": None, "status": "rejected", "message": "invalid_record", "terminal": True}
                continue
            captured = _captured_at(record, ctx["now"])
            ok, reason = (False, "invalid_event_datetime") if captured is None else api.late_event_ok(
                ctx, MODULE, "operador", captured, totem.id)
            if not ok:
                results[index] = {"client_uuid": record.get("client_uuid"), "status": "rejected", "message": reason, "terminal": True}
            else:
                allowed.append((index, record))
        if allowed:
            device = {"uuid": ctx["device"].uuid, "platform": ctx["device"].platform, "app_version": ctx["device"].app_version}
            outcomes = totem.register_batch([r for _i, r in allowed], device=device)
            for (index, _record), outcome in zip(allowed, outcomes):
                outcome = dict(outcome)
                outcome["terminal"] = outcome.get("status") != "retry"
                results[index] = outcome
            uuids = [o["client_uuid"] for o in outcomes if o.get("status") == "registered" and o.get("client_uuid")]
            if uuids:
                request.env["step.colacion.registration"].sudo().search(
                    [("client_uuid", "in", uuids), ("app_operator_id", "=", False)]).write(
                    {"app_operator_id": ctx["person"].id, "app_device_id": ctx["device"].id})
        return {"ok": True, "server_time": ctx["now"].isoformat() + "Z", "results": [results[i] for i in range(len(records))]}
