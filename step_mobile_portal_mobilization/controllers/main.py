"""Movilización en la app Steps: servicios del conductor con sesión personal, y consulta del supervisor.

No debilita la API de dispositivos existente (/mobilization/v1, credenciales por dispositivo): este puente
autentica a la PERSONA, resuelve su chofer por un vínculo explícito de la membresía y solo opera sobre viajes de ese
chofer y de la empresa activa. Los viajes ajenos responden 404 igual que los inexistentes.
"""
from datetime import datetime, timedelta, timezone

from odoo import _, fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from odoo.addons.step_mobile_portal.controllers.main import authenticate, handle, read_body, service
from odoo.addons.step_mobile_portal.lib.step_app_core.errors import ApiError

MODULE = "mobilization"
MAX_EVENTS = 200
INCIDENT_CATEGORIES = ("breakdown", "delay", "passenger", "safety", "other")
CONTRACT_EXTENSIONS = ["events", "events_void", "incidents", "stops"]
METHODS = ("pin", "barcode", "nfc", "manual")
EVENT_TYPES = ("boarding", "alighting")


def _iso(value):
    return value.isoformat() + "Z" if value else None


def _parse(value):
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else parsed


def _driver(ctx):
    partner = ctx["membership"].partner_id
    if not partner or not partner.step_chofer:
        raise ApiError("driver_not_linked", 403, _("Su cuenta no está vinculada a un chofer."))
    return partner


def _own_trip(ctx, trip_id):
    trip = request.env["step.movi.registry"].sudo().search(
        [("id", "=", trip_id), ("chofer_id", "=", _driver(ctx).id), ("company_id", "=", ctx["company"].id)], limit=1)
    if not trip:
        raise ApiError("trip_not_found", 404, _("Servicio no encontrado."))
    return trip


def _trip_payload(trip, with_events=False):
    data = {
        "id": trip.id, "uuid": trip.uuid, "name": trip.name, "state": trip.state, "date": fields.Date.to_string(trip.date),
        "scheduled_time": _iso(trip.scheduled_time), "route": trip.recorrido_id.display_name, "direction": trip.direction,
        "vehicle": trip.vehicle_id.display_name, "capacity": trip.capacity, "aboard_count": trip.aboard_count,
        "boarded_count": trip.boarded_count, "alighted_count": trip.alighted_count, "overcapacity": trip.overcapacity,
    }
    data["stops"] = [{"name": l.name, "lat": l.latitude or None, "lon": l.longitude or None} for l in trip.recorrido_id.route_line]
    if with_events:
        data["incidents"] = [{"key": i.key, "category": i.category, "text": i.text, "device_datetime": _iso(i.device_datetime),
                              "by": i.person_id.name} for i in request.env["step.app.mobilization.incident"].sudo().search([("trip_id", "=", trip.id)], limit=50)]
        data["events"] = [{
            "idempotency_key": e.idempotency_key, "passenger": e.passenger_id.name, "event_type": e.event_type,
            "device_datetime": _iso(e.device_datetime), "state": e.state,
            "by": e.app_person_id.name if e.app_person_id else None,
        } for e in trip.passenger_event_ids.sorted("device_datetime")[-200:]]
        data["aboard"] = sorted(set(e.passenger_id.name for e in trip.passenger_event_ids.filtered(lambda x: x.state == "valid" and x.event_type == "boarding"))
                                - set(e.passenger_id.name for e in trip.passenger_event_ids.filtered(lambda x: x.state == "valid" and x.event_type == "alighting")))
    return data


def _resolve_passenger(trip, item):
    """Pasajero autorizado = empleado activo de la empresa del viaje. Se resuelve en servidor; el chofer nunca recibe nóminas."""
    Employee = request.env["hr.employee"].sudo()
    domain = [("company_id", "=", trip.company_id.id), ("active", "=", True)]
    method, identifier = item.get("method"), str(item.get("identifier") or "").strip()
    if method in ("pin", "barcode") and identifier:
        employees = Employee.search(domain + [(method if method == "pin" else "barcode", "=", identifier)], limit=2)
    elif method in ("manual", "nfc") and item.get("passenger_id"):
        try:
            employees = Employee.search(domain + [("id", "=", int(item["passenger_id"]))], limit=1)
        except (TypeError, ValueError):
            employees = Employee
    else:
        employees = Employee
    return employees if len(employees) == 1 else None


class MobilizationAppController(http.Controller):

    # ---- Conductor --------------------------------------------------------
    @http.route("/steps_app/v1/mobilization/trips", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def trips(self, **kw):
        api = service()
        ctx = authenticate()
        api.require(ctx, "mobilization.drive")
        since = fields.Date.context_today(request.env["step.movi.registry"]) - timedelta(days=1)
        trips = request.env["step.movi.registry"].sudo().search([
            ("chofer_id", "=", _driver(ctx).id), ("company_id", "=", ctx["company"].id),
            ("state", "in", ("draft", "open")), ("date", ">=", since)], limit=50, order="date, scheduled_time, id")
        return {"ok": True, "server_time": _iso(ctx["now"]), "trips": [_trip_payload(t) for t in trips]}

    @http.route("/steps_app/v1/mobilization/trips/<int:trip_id>", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def trip(self, trip_id, **kw):
        api = service()
        ctx = authenticate()
        api.require(ctx, "mobilization.drive")
        return {"ok": True, "trip": _trip_payload(_own_trip(ctx, trip_id), with_events=True)}

    @http.route("/steps_app/v1/mobilization/trips/<int:trip_id>/open", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def open_trip(self, trip_id, **kw):
        api = service()
        ctx = authenticate()
        api.require(ctx, "mobilization.drive")
        trip = _own_trip(ctx, trip_id)
        if trip.state == "draft":
            try:
                trip.action_open()
            except (UserError, ValidationError) as exc:
                raise ApiError("cannot_open", 422, str(exc))
        elif trip.state != "open":
            raise ApiError("invalid_state", 409, _("El servicio ya no está disponible para iniciar."))
        return {"ok": True, "trip": _trip_payload(trip)}

    @http.route("/steps_app/v1/mobilization/trips/<int:trip_id>/close", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def close_trip(self, trip_id, **kw):
        api = service()
        ctx = authenticate()
        api.require(ctx, "mobilization.drive")
        trip = _own_trip(ctx, trip_id)
        if trip.state == "open":
            trip.action_close()
        elif trip.state not in ("closed", "validated", "costed", "accounted"):
            raise ApiError("invalid_state", 409, _("El servicio no está abierto."))
        return {"ok": True, "trip": _trip_payload(trip)}

    @http.route("/steps_app/v1/mobilization/passengers", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def passengers(self, q="", **kw):
        """Búsqueda por nombre para marcación manual: mínimo 3 letras, 20 resultados, solo nombre e id, solo de la empresa."""
        api = service()
        ctx = authenticate()
        api.require(ctx, "mobilization.drive")
        q = (q or "").strip()
        if len(q) < 3:
            return {"ok": True, "passengers": []}
        found = request.env["hr.employee"].sudo().search(
            [("company_id", "=", ctx["company"].id), ("active", "=", True), ("name", "ilike", q)], limit=20)
        return {"ok": True, "passengers": [{"id": e.id, "name": e.name} for e in found]}

    @http.route("/steps_app/v1/mobilization/trips/<int:trip_id>/events", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def events(self, trip_id, **kw):
        """Lote de marcaciones idempotentes (por `idempotency_key` y dispositivo). Cada evento recibe su estado."""
        api = service()
        ctx = authenticate(allow_ended=True)
        trip = _own_trip(ctx, trip_id)
        items = read_body().get("events")
        if not isinstance(items, list) or len(items) > MAX_EVENTS:
            raise ApiError("invalid_batch", 422, "El lote debe ser una lista de hasta %d eventos." % MAX_EVENTS)
        mdevice = request.env["step.mobilization.driver.device"]._for_app(ctx["device"], _driver(ctx), ctx["company"])
        Event = request.env["step.mobilization.passenger.event"].sudo()
        results = []
        for item in items:
            results.append(self._apply(api, ctx, trip, mdevice, Event, item if isinstance(item, dict) else {}))
        return {"ok": True, "results": results, "trip": _trip_payload(trip)}

    def _apply(self, api, ctx, trip, mdevice, Event, item):
        key = str(item.get("idempotency_key") or "").strip()[:64]
        if not key:
            return {"idempotency_key": None, "status": "rejected", "message": "idempotency_key_required", "terminal": True}

        def rejected(reason):
            return {"idempotency_key": key, "status": "rejected", "message": reason, "terminal": True}

        existing = Event.search([("trip_id", "=", trip.id), ("device_id", "=", mdevice.id), ("idempotency_key", "=", key)], limit=1)
        if existing:
            return {"idempotency_key": key, "status": "duplicate", "terminal": True}
        captured = _parse(item.get("device_datetime"))
        if captured is None:
            return rejected("invalid_device_datetime")
        if captured > ctx["now"] + timedelta(minutes=5):
            return rejected("device_clock_ahead")
        ok, reason = api.late_event_ok(ctx, MODULE, "conductor", captured)
        if not ok:
            return rejected(reason)
        if item.get("event_type") not in EVENT_TYPES or item.get("method") not in METHODS:
            return rejected("invalid_event")
        if trip.state != "open":
            return rejected("trip_not_open")
        passenger = _resolve_passenger(trip, item)
        if not passenger:
            return rejected("passenger_not_authorized")

        def number(name):
            try:
                return float(item.get(name) or 0.0)
            except (TypeError, ValueError):
                return 0.0
        try:
            with request.env.cr.savepoint():
                event = Event.create({
                    "trip_id": trip.id, "passenger_id": passenger.id, "event_type": item["event_type"],
                    "device_datetime": captured, "server_datetime": fields.Datetime.now(),
                    "latitude": number("latitude"), "longitude": number("longitude"), "accuracy": number("accuracy"),
                    "location_source": item.get("location_source") if item.get("location_source") in ("gps", "network", "manual") else "unknown",
                    "method": item["method"], "device_id": mdevice.id, "device_uuid": mdevice.device_uuid,
                    "idempotency_key": key, "app_person_id": ctx["person"].id,
                })
        except (UserError, ValidationError) as exc:
            return rejected(str(exc))
        except Exception:
            return {"idempotency_key": key, "status": "retry", "message": "server_error", "terminal": False}
        return {"idempotency_key": key, "status": "created", "event_id": event.id, "terminal": True}

    @http.route("/steps_app/v1/mobilization/trips/<int:trip_id>/events/void", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def void_event(self, trip_id, **kw):
        """Corrección: el conductor anula una marca PROPIA de un servicio abierto (el evento no se borra: queda anulado con motivo)."""
        api = service()
        ctx = authenticate(allow_ended=True)
        trip = _own_trip(ctx, trip_id)
        body = read_body()
        key, reason = str(body.get("idempotency_key") or "").strip()[:64], str(body.get("reason") or "").strip()[:200]
        if not key or not reason:
            raise ApiError("invalid_void", 422, _("Indique la marca y el motivo."))
        # La política de captura aplica al instante de la corrección, no al de la marca original.
        captured = _parse(body.get("device_datetime")) or ctx["now"]
        ok, why = api.late_event_ok(ctx, MODULE, "conductor", captured)
        if not ok:
            return {"ok": True, "status": "rejected", "message": why, "terminal": True}
        event = request.env["step.mobilization.passenger.event"].sudo().search(
            [("trip_id", "=", trip.id), ("idempotency_key", "=", key), ("app_person_id", "=", ctx["person"].id)], limit=1)
        if not event:
            return {"ok": True, "status": "rejected", "message": "event_not_found", "terminal": True}
        if event.state == "void":
            return {"ok": True, "status": "duplicate", "terminal": True, "trip": _trip_payload(trip)}
        if trip.state != "open":
            return {"ok": True, "status": "rejected", "message": "trip_not_open", "terminal": True}
        event.action_void(reason)
        return {"ok": True, "status": "voided", "terminal": True, "trip": _trip_payload(trip)}

    @http.route("/steps_app/v1/mobilization/trips/<int:trip_id>/incidents", type="http", auth="public", methods=["POST"], csrf=False)
    @handle
    def incident(self, trip_id, **kw):
        """Incidencias del servicio: idempotentes por clave, con la autoría de la persona (también si se capturan sin conexión)."""
        api = service()
        ctx = authenticate(allow_ended=True)
        trip = _own_trip(ctx, trip_id)
        body = read_body()
        key = str(body.get("key") or "").strip()[:64]
        text = str(body.get("text") or "").strip()[:500]
        captured = _parse(body.get("device_datetime"))
        if not key or not text or captured is None or body.get("category") not in INCIDENT_CATEGORIES:
            return {"ok": True, "status": "rejected", "message": "invalid_incident", "terminal": True}
        Incident = request.env["step.app.mobilization.incident"].sudo()
        if Incident.search_count([("trip_id", "=", trip.id), ("key", "=", key)]):
            return {"ok": True, "status": "duplicate", "terminal": True}
        ok, why = api.late_event_ok(ctx, MODULE, "conductor", captured)
        if not ok:
            return {"ok": True, "status": "rejected", "message": why, "terminal": True}
        Incident.create({"trip_id": trip.id, "key": key, "person_id": ctx["person"].id, "category": body["category"],
                         "text": text, "device_datetime": captured})
        return {"ok": True, "status": "created", "terminal": True}

    @http.route("/steps_app/v1/mobilization/contract", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def contract(self, **kw):
        """Extensiones disponibles en este servidor: un cliente más nuevo puede degradar con elegancia ante un Odoo más antiguo."""
        return {"ok": True, "module": MODULE, "contract_version": 1, "extensions": CONTRACT_EXTENSIONS}

    # ---- Supervisor --------------------------------------------------------
    @http.route("/steps_app/v1/mobilization/supervisor/trips", type="http", auth="public", methods=["GET"], csrf=False)
    @handle
    def supervisor_trips(self, date="", **kw):
        api = service()
        ctx = authenticate()
        api.require(ctx, "mobilization.supervise")
        Trip = request.env["step.movi.registry"].sudo()
        try:
            day = fields.Date.from_string(date) if date else fields.Date.context_today(Trip)
        except ValueError:
            raise ApiError("invalid_date", 422)
        trips = Trip.search([("company_id", "=", ctx["company"].id), ("date", "=", day), ("state", "!=", "cancelled")], limit=200)
        return {"ok": True, "date": fields.Date.to_string(day),
                "trips": [{**_trip_payload(t, with_events=True), "driver": t.chofer_id.name} for t in trips]}
