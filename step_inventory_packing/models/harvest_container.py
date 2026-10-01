"""Envases de cosecha en ubicaciones internas por productor.

Los traslados nativos conservan inventario y valoración de la empresa;
los saldos se leen de stock.quant, sin un libro paralelo de unidades.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    step_is_harvest_container = fields.Boolean(string="Es envase de cosecha")


class StockLocation(models.Model):
    _inherit = "stock.location"

    step_producer_id = fields.Many2one("res.partner", string="Productor de envases", index=True)

    @api.constrains("step_producer_id", "usage")
    def _check_step_container_location(self):
        for location in self:
            if location.step_producer_id and location.usage != "internal":
                raise ValidationError(_("La ubicación de envases del productor debe ser interna."))


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _step_container_location(self, company):
        self.ensure_one()
        location = self.env["stock.location"].search([
            ("step_producer_id", "=", self.id), ("company_id", "=", company.id),
        ], limit=1)
        if not location:
            warehouse = self.env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
            if not warehouse:
                raise UserError(_("La empresa necesita una bodega antes de crear la ubicación de envases."))
            location = self.env["stock.location"].create({
                "name": "Envases en productor: %s" % self.display_name,
                "usage": "internal",
                "location_id": warehouse.view_location_id.id,
                "company_id": company.id,
                "step_producer_id": self.id,
            })
        return location

    def action_step_container_location(self):
        self.ensure_one()
        company = self.company_id or self.env.company
        location = self._step_container_location(company)
        return {
            "type": "ir.actions.act_window", "name": _("Envases en productor"),
            "res_model": "stock.location", "res_id": location.id,
            "view_mode": "form", "target": "current",
        }


class HarvestContainerTransfer(models.Model):
    _name = "step.harvest.container.transfer"
    _description = "Movimiento de envases de cosecha"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(default="Nuevo", readonly=True, copy=False)
    state = fields.Selection([("draft", "Borrador"), ("done", "Validado")],
                             default="draft", required=True, tracking=True)
    direction = fields.Selection([("issue", "Entrega al productor"),
                                  ("return", "Devolución a bodega")],
                                 required=True, default="return")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    producer_id = fields.Many2one("res.partner", string="Productor", required=True)
    fruit_picking_id = fields.Many2one("stock.picking", string="Recepción o despacho de fruta")
    warehouse_id = fields.Many2one("stock.warehouse", string="Bodega", required=True,
                                   default=lambda self: self.env["stock.warehouse"].search([
                                       ("company_id", "=", self.env.company.id)], limit=1))
    line_ids = fields.One2many("step.harvest.container.transfer.line", "transfer_id", string="Envases")
    picking_id = fields.Many2one("stock.picking", string="Movimiento de inventario", readonly=True, copy=False)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "Nuevo") == "Nuevo":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "step.harvest.container.transfer") or "Nuevo"
        return super().create(vals_list)

    def write(self, vals):
        locked = {"name", "state", "direction", "company_id", "producer_id",
                  "fruit_picking_id", "warehouse_id", "line_ids", "picking_id"}
        if locked.intersection(vals) and any(record.state == "done" for record in self):
            raise UserError(_("Un movimiento de envases validado no puede modificarse."))
        return super().write(vals)

    def unlink(self):
        if any(record.state == "done" for record in self):
            raise UserError(_("Un movimiento de envases validado no puede borrarse."))
        return super().unlink()

    def action_validate(self):
        for record in self:
            if record.state != "draft" or not record.line_ids:
                raise UserError(_("Agregue envases a un movimiento en borrador."))
            if record.warehouse_id.company_id != record.company_id:
                raise ValidationError(_("La bodega debe pertenecer a la empresa del movimiento."))
            if record.producer_id.company_id and record.producer_id.company_id != record.company_id:
                raise ValidationError(_("El productor pertenece a otra empresa."))
            if record.fruit_picking_id:
                if record.fruit_picking_id.company_id != record.company_id or record.fruit_picking_id.state != "done":
                    raise ValidationError(_("El documento de fruta debe estar validado y ser de la misma empresa."))
                if record.fruit_picking_id.partner_id != record.producer_id:
                    raise ValidationError(_("El productor debe coincidir con el documento de fruta."))
            products = record.line_ids.mapped("product_id")
            if len(products) != len(record.line_ids):
                raise ValidationError(_("Registre cada tipo de envase una sola vez por movimiento."))
            if any(not line.product_id.product_tmpl_id.step_is_harvest_container or
                   not line.product_id.is_storable or line.quantity <= 0 for line in record.line_ids):
                raise ValidationError(_("Seleccione envases de cosecha almacenables con cantidad positiva."))
            producer_location = record.producer_id._step_container_location(record.company_id)
            warehouse_location = record.warehouse_id.lot_stock_id
            source, destination = ((warehouse_location, producer_location)
                                   if record.direction == "issue" else (producer_location, warehouse_location))
            picking = self.env["stock.picking"].create({
                "picking_type_id": record.warehouse_id.int_type_id.id,
                "company_id": record.company_id.id,
                "partner_id": record.producer_id.id,
                "origin": record.name,
                "location_id": source.id,
                "location_dest_id": destination.id,
                "move_ids": [(0, 0, {
                    "name": line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.quantity,
                    "product_uom": line.product_id.uom_id.id,
                    "location_id": source.id,
                    "location_dest_id": destination.id,
                }) for line in record.line_ids],
            })
            picking.action_confirm()
            picking.action_assign()
            for line in record.line_ids:
                move = picking.move_ids.filtered(lambda row: row.product_id == line.product_id)
                if not move.move_line_ids or sum(move.move_line_ids.mapped("quantity")) < line.quantity:
                    raise ValidationError(_("No hay existencias disponibles de %s en %s.") %
                                          (line.product_id.display_name, source.display_name))
            picking.button_validate()
            if picking.state != "done":
                raise UserError(_("Complete la validación del traslado de envases en Inventario."))
            record.write({"picking_id": picking.id, "state": "done"})
        return True


class HarvestContainerTransferLine(models.Model):
    _name = "step.harvest.container.transfer.line"
    _description = "Envase en movimiento de cosecha"

    transfer_id = fields.Many2one("step.harvest.container.transfer", required=True, ondelete="cascade")
    product_id = fields.Many2one("product.product", string="Envase", required=True,
                                 domain="[('product_tmpl_id.step_is_harvest_container', '=', True)]")
    quantity = fields.Float(string="Cantidad", required=True, digits="Product Unit of Measure")
    uom_id = fields.Many2one(related="product_id.uom_id", string="UdM")

    @api.constrains("quantity")
    def _check_quantity(self):
        if any(line.quantity <= 0 for line in self):
            raise ValidationError(_("La cantidad de envases debe ser positiva."))

    @api.model_create_multi
    def create(self, vals_list):
        parents = self.env["step.harvest.container.transfer"].browse([
            vals["transfer_id"] for vals in vals_list if vals.get("transfer_id")])
        if any(parent.state == "done" for parent in parents):
            raise UserError(_("No agregue líneas a un movimiento validado."))
        return super().create(vals_list)

    def write(self, vals):
        if vals and any(line.transfer_id.state == "done" for line in self):
            raise UserError(_("Las líneas de un movimiento validado no pueden modificarse."))
        return super().write(vals)

    def unlink(self):
        if any(line.transfer_id.state == "done" for line in self):
            raise UserError(_("Las líneas de un movimiento validado no pueden borrarse."))
        return super().unlink()


class StockPicking(models.Model):
    _inherit = "stock.picking"

    step_container_transfer_ids = fields.One2many(
        "step.harvest.container.transfer", "fruit_picking_id", string="Movimientos de envases")

    def action_step_container_return(self):
        self.ensure_one()
        if not self.step_fruit_reception_kind or self.state != "done" or not self.fruit_fundo_id.partner_id:
            raise UserError(_("Valide la recepción de fruta con productor antes de registrar sus envases."))
        return {
            "type": "ir.actions.act_window", "name": _("Envases recibidos con fruta"),
            "res_model": "step.harvest.container.transfer", "view_mode": "form", "target": "current",
            "context": {
                "default_direction": "return", "default_producer_id": self.fruit_fundo_id.partner_id.id,
                "default_fruit_picking_id": self.id, "default_company_id": self.company_id.id,
            },
        }


class HarvestContainerOpening(models.TransientModel):
    _name = "step.harvest.container.opening"
    _description = "Inventario inicial de envases en productor"

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company)
    line_ids = fields.One2many("step.harvest.container.opening.line", "opening_id", string="Saldos iniciales")

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise UserError(_("El inventario inicial requiere permisos de administrador de Inventario."))
        if not self.line_ids:
            raise UserError(_("Agregue al menos un saldo inicial."))
        keys = [(line.producer_id.id, line.product_id.id) for line in self.line_ids]
        if len(keys) != len(set(keys)):
            raise ValidationError(_("No repita el mismo envase para un productor."))
        for line in self.line_ids:
            if not line.product_id.is_storable or not line.product_id.product_tmpl_id.step_is_harvest_container:
                raise ValidationError(_("El producto debe ser un envase de cosecha almacenable."))
            if line.quantity < 0:
                raise ValidationError(_("El saldo inicial no puede ser negativo."))
            location = line.producer_id._step_container_location(self.company_id)
            quant_model = self.env["stock.quant"].with_company(self.company_id)
            if quant_model._get_available_quantity(line.product_id, location) or quant_model.search_count([
                ("product_id", "=", line.product_id.id), ("location_id", "=", location.id),
            ]):
                raise UserError(_("Ya existe saldo o historia de %s en %s; use un ajuste de inventario.") %
                                (line.product_id.display_name, line.producer_id.display_name))
            quant = quant_model.with_context(inventory_mode=True).create({
                "product_id": line.product_id.id,
                "location_id": location.id,
                "inventory_quantity": line.quantity,
            })
            result = quant.action_apply_inventory()
            if result:
                raise UserError(_("Revise la configuración de trazabilidad del envase antes del inventario inicial."))
        return {"type": "ir.actions.act_window_close"}


class HarvestContainerOpeningLine(models.TransientModel):
    _name = "step.harvest.container.opening.line"
    _description = "Saldo inicial de envases por productor"

    opening_id = fields.Many2one("step.harvest.container.opening", required=True, ondelete="cascade")
    producer_id = fields.Many2one("res.partner", string="Productor", required=True)
    product_id = fields.Many2one("product.product", string="Envase", required=True)
    quantity = fields.Float(string="Cantidad inicial", required=True, digits="Product Unit of Measure")
