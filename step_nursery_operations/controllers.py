import json

from psycopg2.errors import UniqueViolation
from werkzeug.exceptions import BadRequest, Forbidden

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import Controller, request, route
from odoo.tools import file_open


ASSETS = "step_nursery_operations/static/src/offline/"
PRIVATE = [("Cache-Control", "private, no-store"), ("X-Content-Type-Options", "nosniff")]


class NurseryOfflineController(Controller):
    @route("/nursery-offline/", type="http", auth="public", methods=["GET"], sitemap=False)
    def shell(self):
        with file_open(ASSETS + "index.html", "rb") as asset:
            return request.make_response(asset.read(), [
                ("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-cache"),
                ("X-Content-Type-Options", "nosniff"),
                ("Content-Security-Policy",
                 "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"),
            ])

    @route("/nursery-offline/sw.js", type="http", auth="public", methods=["GET"], sitemap=False)
    def worker(self):
        with file_open(ASSETS + "sw.js", "rb") as asset:
            return request.make_response(asset.read(), [
                ("Content-Type", "text/javascript; charset=utf-8"), ("Cache-Control", "no-cache"),
                ("X-Content-Type-Options", "nosniff"),
            ])

    @staticmethod
    def _user():
        user = request.env.user
        if not user.has_group("step_nursery_operations.group_nursery_operator"):
            raise Forbidden()
        return user

    @route("/nursery-offline/session", type="http", auth="user", methods=["GET"], sitemap=False)
    def session(self):
        user = self._user()
        return request.make_json_response({
            "uid": user.id, "csrf": request.csrf_token(),
            "companies": [{"id": item.id, "name": item.name} for item in user.company_ids],
        }, headers=PRIVATE)

    @route("/nursery-offline/orders/<int:company_id>", type="http", auth="user", methods=["GET"], sitemap=False)
    def orders(self, company_id):
        user = self._user()
        if company_id not in user.company_ids.ids:
            raise Forbidden()
        orders = request.env["mrp.production"].with_context(allowed_company_ids=[company_id]).search([
            ("company_id", "=", company_id), ("step_nursery_plan_ids", "!=", False),
            ("state", "not in", ["done", "cancel"]),
        ], limit=100, order="date_start desc, id desc")
        return request.make_json_response([{"id": item.id, "name": item.name} for item in orders], headers=PRIVATE)

    @route("/nursery-offline/sync", type="http", auth="user", methods=["POST"], csrf=True, sitemap=False)
    def sync(self, uid=None, company=None, batch=None):
        user = self._user()
        try:
            if int(uid) != user.id or int(company) not in user.company_ids.ids:
                raise Forbidden()
            company = int(company)
            if not batch or len(batch) > 64000:
                raise ValueError
            records = json.loads(batch)
            if not isinstance(records, list) or not 1 <= len(records) <= 30:
                raise ValueError
        except (ValueError, TypeError) as error:
            raise BadRequest() from error
        event_model = request.env["step.nursery.event"].with_context(allowed_company_ids=[company])
        results = []
        for event in records:
            key = event.get("id") if isinstance(event, dict) else None
            try:
                with request.env.cr.savepoint():
                    item = event_model._ingest_offline_event(event)
                results.append({"id": key, "ok": True, "event_id": item.id})
            except UniqueViolation:
                results.append({"id": key, "ok": False, "error": "Captura en proceso. Reintente."})
            except AccessError:
                results.append({"id": key, "ok": False, "error": "No tiene acceso a la orden."})
            except (ValidationError, UserError) as error:
                results.append({"id": key, "ok": False, "error": str(error)})
        return request.make_json_response(results, headers=PRIVATE)
