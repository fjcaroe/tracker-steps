import json
import logging

from odoo import fields, http, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

from ..models.meal_totem import MAX_BATCH_RECORDS


_logger = logging.getLogger(__name__)

#: Versión del contrato HTTP. La aplicación usa este número para saber qué
#: endpoints puede utilizar contra un servidor concreto.
API_VERSION = 2

#: Capacidades declaradas por el servidor. La App nunca debe asumirlas: las
#: consulta en /colaciones/api/health antes de usar el endpoint por lote.
API_CAPABILITIES = [
    "totem_config",
    "register",
    "batch_sync",
    "device_info",
    "server_time",
]

NO_STORE = [("Cache-Control", "no-store")]


class StepColacionesTotemController(http.Controller):

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _get_totem(self, token):
        if not token or not isinstance(token, str):
            return request.env["step.colacion.totem"].sudo().browse()
        return request.env["step.colacion.totem"].sudo().search([
            ("access_token", "=", token),
            ("active", "=", True),
        ], limit=1)

    def _server_time(self):
        return fields.Datetime.now().replace(microsecond=0).isoformat() + "Z"

    def _json(self, payload, status=200):
        return request.make_json_response(payload, status=status, headers=NO_STORE)

    def _totem_not_found(self):
        return self._json({
            "ok": False,
            "terminal": True,
            "error": "totem_not_found",
            "server_time": self._server_time(),
            "message": _("El tótem no existe o está deshabilitado."),
        }, status=404)

    def _payload(self):
        payload = request.httprequest.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}

    def _device(self, payload):
        device = payload.get("device")
        return device if isinstance(device, dict) else None

    # ------------------------------------------------------------------
    # Página servida por Odoo (compatibilidad histórica)
    # ------------------------------------------------------------------
    @http.route(
        "/colaciones/totem/<string:token>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        sitemap=False,
    )
    def totem_page(self, token, **kwargs):
        totem = self._get_totem(token)
        if not totem:
            return request.not_found()
        totem._touch_device()
        response = request.render("step_colaciones.totem_page", {"totem": totem})
        response.headers["Cache-Control"] = "private, max-age=0, must-revalidate"
        return response

    # ------------------------------------------------------------------
    # API
    # ------------------------------------------------------------------
    @http.route(
        "/colaciones/api/health",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        sitemap=False,
    )
    def health(self, **kwargs):
        """Contrato soportado y hora del servidor.

        No requiere token: no expone ningún dato de negocio y permite que la
        aplicación distinga "servidor caído" de "token revocado".
        """
        params = request.env["ir.config_parameter"].sudo()
        return self._json({
            "ok": True,
            "api_version": API_VERSION,
            "capabilities": API_CAPABILITIES,
            "max_batch_records": MAX_BATCH_RECORDS,
            "server_time": self._server_time(),
            "min_app_version": params.get_param("colaciones.min_app_version", "1.0.0"),
            "recommended_app_version": params.get_param("colaciones.recommended_app_version", "1.0.0"),
        })

    @http.route(
        "/colaciones/api/totem/<string:token>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        sitemap=False,
    )
    def totem_configuration(self, token, **kwargs):
        """Expone solo la configuración operativa que necesita la aplicación."""
        totem = self._get_totem(token)
        if not totem:
            return self._totem_not_found()
        totem._touch_device()
        return self._json(totem.totem_configuration())

    @http.route(
        "/colaciones/api/register",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def register(self, **kwargs):
        payload = self._payload()
        totem = self._get_totem(payload.get("token"))
        if not totem:
            return self._totem_not_found()
        try:
            result = totem.register_identifier(
                payload.get("identifier"),
                payload.get("client_uuid"),
                event_datetime=payload.get("event_datetime"),
                offline=bool(payload.get("offline")),
            )
        except (ValidationError, UserError) as exc:
            totem._touch_device(device=self._device(payload))
            return self._json({
                "ok": False,
                "duplicate": False,
                "terminal": True,
                "error": "rejected",
                "server_time": self._server_time(),
                "message": str(exc),
            }, status=422)
        totem._touch_device(device=self._device(payload), synced=True)
        result["server_time"] = self._server_time()
        return self._json(result)

    @http.route(
        "/colaciones/api/sync",
        type="http",
        auth="public",
        methods=["POST"],
        csrf=False,
    )
    def sync(self, **kwargs):
        """Sincronización por lote con respuesta individual por UUID."""
        payload = self._payload()
        totem = self._get_totem(payload.get("token"))
        if not totem:
            return self._totem_not_found()
        records = payload.get("records")
        try:
            results = totem.register_batch(records, device=self._device(payload))
        except (ValidationError, UserError) as exc:
            return self._json({
                "ok": False,
                "terminal": True,
                "error": "invalid_batch",
                "server_time": self._server_time(),
                "message": str(exc),
            }, status=422)
        return self._json({
            "ok": True,
            "api_version": API_VERSION,
            "server_time": self._server_time(),
            "results": results,
        })

    # ------------------------------------------------------------------
    # PWA servida por Odoo (compatibilidad histórica)
    # ------------------------------------------------------------------
    @http.route(
        "/colaciones/manifest/<string:token>.webmanifest",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def manifest(self, token, **kwargs):
        totem = self._get_totem(token)
        if not totem:
            return request.not_found()
        manifest = {
            "name": "Colaciones - %s" % totem.name,
            "short_name": "Colaciones",
            "start_url": "/colaciones/totem/%s" % token,
            "scope": "/colaciones/",
            "display": "standalone",
            "background_color": "#f4f7f1",
            "theme_color": "#123f2b",
            "icons": [{
                "src": "/step_colaciones/static/description/icon.png",
                "sizes": "1254x1254",
                "type": "image/png",
                "purpose": "any maskable",
            }],
        }
        return request.make_response(
            json.dumps(manifest, ensure_ascii=False),
            headers=[
                ("Content-Type", "application/manifest+json; charset=utf-8"),
                ("Cache-Control", "private, max-age=3600"),
            ],
        )

    @http.route(
        "/colaciones/sw.js",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
    )
    def service_worker(self, **kwargs):
        script = r'''
const CACHE = "step-colaciones-v1";
const STATIC = [
  "/step_colaciones/static/src/totem/totem.css",
  "/step_colaciones/static/src/totem/totem.js",
  "/step_colaciones/static/description/icon.png"
];
self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(STATIC)));
  self.skipWaiting();
});
self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys().then((keys) => Promise.all(
    keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))
  )));
  self.clients.claim();
});
self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;
  event.respondWith((async () => {
    try {
      const response = await fetch(event.request);
      if (response.ok) {
        const cache = await caches.open(CACHE);
        cache.put(event.request, response.clone());
      }
      return response;
    } catch (error) {
      const cached = await caches.match(event.request);
      if (cached) return cached;
      if (event.request.mode === "navigate") {
        const cache = await caches.open(CACHE);
        const keys = await cache.keys();
        const page = keys.find((request) => request.url.includes("/colaciones/totem/"));
        if (page) return cache.match(page);
      }
      throw error;
    }
  })());
});
'''
        return request.make_response(
            script,
            headers=[
                ("Content-Type", "application/javascript; charset=utf-8"),
                ("Service-Worker-Allowed", "/colaciones/"),
                ("Cache-Control", "no-cache"),
            ],
        )
