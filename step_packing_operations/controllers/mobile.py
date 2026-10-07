"""Captura móvil de tarjas con sincronización idempotente por número."""

from odoo import http, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request


class PackingMobile(http.Controller):

    @http.route("/packing/mobile", type="http", auth="user", website=False)
    def mobile_page(self, **kwargs):
        if not request.env.user.has_group("stock.group_stock_user"):
            raise AccessError(_("Se requiere acceso a Inventario para registrar tarjas."))
        return request.render("step_packing_operations.mobile_packing_page", {
            "user_id": request.env.user.id,
        })

    @http.route("/packing/mobile/sw.js", type="http", auth="user", website=False)
    def mobile_worker(self, **kwargs):
        # File is a public static asset; the route fixes the worker scope to /packing/mobile.
        from odoo.modules.module import get_module_resource
        with open(get_module_resource("step_packing_operations", "static", "src", "mobile_sw.js"), "rb") as stream:
            content = stream.read()
        return request.make_response(content, headers=[
            ("Content-Type", "application/javascript; charset=utf-8"),
            ("Service-Worker-Allowed", "/packing/mobile"),
            ("Cache-Control", "no-store"),
        ])

    @http.route("/packing/mobile/api", type="json", auth="user", methods=["POST"])
    def mobile_api(self, operation, **payload):
        if not request.env.user.has_group("stock.group_stock_user"):
            raise AccessError(_("Se requiere acceso a Inventario para registrar tarjas."))
        if operation == "orders":
            orders = request.env["step.packing.production"].search([
                ("step_packing_order_id", "!=", False),
                ("state", "=", "created"),
            ], limit=100, order="id desc")
            return [{
                "id": order.id, "name": order.name,
                "producer": order.fruit_grower_id.display_name or "",
                "variety": order.fruit_variety_id.display_name or "",
                "product": order.raw_product_id.display_name or order.product_id.display_name or "",
            } for order in orders]
        if operation == "scan":
            return self._scan(payload)
        raise UserError(_("Operación móvil desconocida."))

    def _scan(self, payload):
        try:
            production_id = int(payload.get("production_id") or 0)
        except (TypeError, ValueError):
            raise ValidationError(_("Seleccione una OT válida."))
        production = request.env["step.packing.production"].browse(production_id).exists()
        if not production or not production.step_packing_order_id or production.state != "created":
            raise ValidationError(_("La OT no está disponible para registrar tarjas."))
        kind = (payload.get("kind") or "").strip().upper()
        code = (payload.get("code") or "").strip()
        if kind not in ("C", "E", "N") or not code or len(code) > 80:
            raise ValidationError(_("Indique un tipo C/E/N y un número de tarja válido."))
        package_model = request.env["stock.quant.package"]
        package = package_model.search([("name", "=", code)], limit=1)
        if package and (not package.is_fruit_tag or package.step_tag_kind != kind):
            raise ValidationError(_("Ese número pertenece a otra tarja o a otro tipo."))
        if not package:
            if kind == "C":
                raise ValidationError(_("La tarja C debe recibirse y validarse primero en Inventario."))
            if not production.fruit_grower_id or not production.fruit_variety_id:
                raise ValidationError(_("Complete productor y variedad en la OT antes de crear tarjas."))
            try:
                quantity = float(payload.get("quantity") or 0)
                boxes = float(payload.get("boxes") or 0)
                kilos = float(payload.get("kilos") or 0)
            except (TypeError, ValueError):
                raise ValidationError(_("Cantidad, cajas y kilos deben ser números."))
            if min(quantity, boxes, kilos) <= 0:
                raise ValidationError(_("Cantidad, cajas y kilos deben ser positivos."))
            product = production.product_id
            product_code = (payload.get("product_code") or "").strip()
            if product_code:
                product = request.env["product.product"].search([
                    ("default_code", "=", product_code)], limit=1)
            if not product or kind == 'N' and not product_code:
                raise ValidationError(_("Indique el código del producto resultante."))
            result = "export" if kind == "E" else (payload.get("result") or "")
            if result not in ("export", "commercial", "precaliber", "waste") or (kind == "N" and result == "export"):
                raise ValidationError(_("Seleccione el resultado comercial, precalibre o desecho."))
            package = package_model.create({
                "name": code, "is_fruit_tag": True, "step_tag_kind": kind,
                "step_packing_production_id": production.id,
                "step_packing_result": result,
                "step_producer_id": production.fruit_grower_id.id,
                "fundo_id": production.fruit_fundo_id.id,
                "especie_id": production.fruit_species_id.id,
                "variedad_id": production.fruit_variety_id.id,
                "box_count": round(boxes),
                "ot_proceso": production.name,
                "op_folio": production.step_packing_order_id.name,
                "step_tag_line_ids": [(0, 0, {
                    "producer_id": production.fruit_grower_id.id,
                    "product_id": product.id,
                    "quantity": quantity, "boxes": boxes, "kilos": kilos,
                })],
            })
        other = request.env["step.packing.production"].search([
            ("id", "!=", production.id),
            "|", ("step_packing_input_tag_ids", "in", package.id),
                 ("step_packing_output_tag_ids", "in", package.id),
        ], limit=1)
        if other:
            raise ValidationError(_("La tarja ya está asociada a otra OT."))
        if kind == "C":
            if package.step_tag_state != "validated":
                raise ValidationError(_("La tarja C debe estar validada."))
            if package not in production.step_packing_input_tag_ids:
                production.write({"step_packing_input_tag_ids": [(4, package.id)]})
        else:
            if package.step_tag_state != "created":
                raise ValidationError(_("La tarja E/N debe estar creada, sin validar."))
            if package not in production.step_packing_output_tag_ids:
                production.write({"step_packing_output_tag_ids": [(4, package.id)]})
        return {
            "id": package.id, "code": package.name, "kind": kind,
            "report_url": "/report/pdf/step_inventory_fruit_tag.report_fruit_tag/%s" % package.id,
            "input_count": len(production.step_packing_input_tag_ids),
            "output_count": len(production.step_packing_output_tag_ids),
        }
