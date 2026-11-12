from math import isfinite

from odoo import _, api, Command, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_compare


_RESERVATION_SCOPE = object()


class NurseryCustody(models.Model):
    _name = "step.nursery.custody"
    _description = "Cuenta de semilla de terceros por lote y ubicación"
    _rec_name = "lot_id"
    _check_company_auto = True

    receipt_line_id = fields.Many2one("stock.move.line", string="Recepción inicial", required=True,
                                       check_company=True, ondelete="restrict")
    company_id = fields.Many2one(related="receipt_line_id.company_id", store=True, index=True)
    owner_id = fields.Many2one(related="receipt_line_id.owner_id", string="Dueño", store=True, index=True)
    lot_id = fields.Many2one(related="receipt_line_id.lot_id", string="Lote de semilla", store=True, index=True)
    product_id = fields.Many2one(related="receipt_line_id.product_id")
    location_id = fields.Many2one(related="receipt_line_id.location_dest_id", string="Ubicación de custodia", store=True)
    unit_id = fields.Many2one(related="product_id.uom_id")
    variety_id = fields.Many2one(related="lot_id.step_nursery_variety_id")
    germination_pct = fields.Float(related="lot_id.step_nursery_germination_pct")
    received = fields.Float(string="Recibido", compute="_compute_totals")
    consumed = fields.Float(string="Consumido", compute="_compute_totals")
    returned = fields.Float(string="Devuelto", compute="_compute_totals")
    available = fields.Float(string="Saldo físico en custodia", compute="_compute_totals")
    _sql_constraints = [
        ("custody_identity", "UNIQUE(company_id, owner_id, lot_id, location_id)",
         "Ya existe custodia para este lote, dueño y ubicación."),
    ]

    @api.constrains("receipt_line_id")
    def _check_receipt(self):
        for row in self:
            line = row.receipt_line_id
            if (line.state != "done" or not line.lot_id or not line.owner_id or line.quantity <= 0
                    or line.owner_id == line.company_id.partner_id or line.product_id.tracking != "lot"
                    or line.location_id.usage not in ("supplier", "customer")
                    or line.location_dest_id.usage != "internal"
                    or line.location_dest_id.company_id != line.company_id):
                raise ValidationError(_("Seleccione una recepción validada con lote y propietario externo a la empresa."))

    def write(self, vals):
        if "receipt_line_id" in vals and any(row.receipt_line_id.id != vals["receipt_line_id"] for row in self):
            raise UserError(_("La custodia conserva su recepción de origen."))
        return super().write(vals)

    @api.depends("receipt_line_id", "lot_id.step_nursery_stock_line_ids.state",
                 "lot_id.step_nursery_stock_line_ids.quantity", "lot_id.step_nursery_stock_line_ids.owner_id",
                 "lot_id.step_nursery_stock_line_ids.location_id", "lot_id.step_nursery_stock_line_ids.location_dest_id",
                 "lot_id.step_nursery_quant_ids.quantity")
    def _compute_totals(self):
        line_model = self.env["stock.move.line"]
        quant_model = self.env["stock.quant"]
        for row in self:
            row.received = row.consumed = row.returned = row.available = 0
            if not row.receipt_line_id:
                continue
            common = [("company_id", "=", row.company_id.id), ("owner_id", "=", row.owner_id.id),
                      ("lot_id", "=", row.lot_id.id), ("product_id", "=", row.product_id.id)]
            moves = line_model.search(common + [("state", "=", "done"), "|",
                ("location_id", "=", row.location_id.id), ("location_dest_id", "=", row.location_id.id)])
            for line in moves:
                qty = line.product_uom_id._compute_quantity(line.quantity, row.unit_id, round=False)
                if line.location_dest_id == row.location_id and line.location_id.usage in ("supplier", "customer"):
                    row.received += qty
                elif line.location_id == row.location_id and line.location_dest_id.usage == "production":
                    row.consumed += qty
                elif line.location_id == row.location_id and line.location_dest_id.usage in ("supplier", "customer"):
                    row.returned += qty
            row.available = sum(quant_model.search(common + [
                ("location_id", "=", row.location_id.id),
            ]).mapped("quantity"))


class StockLot(models.Model):
    _inherit = "stock.lot"

    step_nursery_stock_line_ids = fields.One2many("stock.move.line", "lot_id")
    step_nursery_quant_ids = fields.One2many("stock.quant", "lot_id")


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    step_nursery_custody_id = fields.Many2one("step.nursery.custody", string="Semilla en custodia",
                                              check_company=True, ondelete="restrict")
    step_nursery_customer_id = fields.Many2one(related="step_nursery_custody_id.owner_id", string="Cliente de maquila")
    step_nursery_packages = fields.One2many("stock.quant.package", "step_nursery_production_id", string="Bandejas etiquetadas")

    def action_confirm(self):
        for order in self.filtered(lambda mo: mo.step_nursery_custody_id and mo.state == "draft"):
            custody = order.step_nursery_custody_id
            custody._check_receipt()
            seed = order.move_raw_ids.filtered(lambda move: move.product_id == custody.product_id and move.state == "draft")
            if len(seed) != 1 or seed.product_uom_qty <= 0:
                raise UserError(_("La receta debe incluir una única línea del producto recibido en custodia."))
            seed.write({"location_id": custody.location_id.id, "procure_method": "make_to_stock"})
        return super().action_confirm()

    def write(self, vals):
        if "step_nursery_custody_id" in vals and self.filtered(
                lambda mo: mo.state != "draft" and mo.step_nursery_custody_id.id != vals["step_nursery_custody_id"]):
            raise UserError(_("La semilla del cliente no se cambia después de confirmar la orden."))
        return super().write(vals)

    def _get_backorder_mo_vals(self):
        values = super()._get_backorder_mo_vals()
        values["step_nursery_custody_id"] = self.step_nursery_custody_id.id
        return values


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _get_gather_domain(self, product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False):
        domain = super()._get_gather_domain(product_id, location_id, lot_id, package_id, owner_id, strict)
        scope = self.env.context.get("step_nursery_exact_seed")
        if isinstance(scope, tuple) and len(scope) == 3 and scope[0] is _RESERVATION_SCOPE:
            domain = expression.AND([domain, [("lot_id", "=", scope[1]), ("location_id", "=", scope[2])]])
        return domain


class StockMove(models.Model):
    _inherit = "stock.move"

    def _step_seed_custody(self):
        self.ensure_one()
        custody = self.raw_material_production_id.step_nursery_custody_id
        return custody if custody.product_id == self.product_id else self.env["step.nursery.custody"]

    def _update_reserved_quantity(self, need, location_id, lot_id=None, package_id=None, owner_id=None, strict=True):
        self.ensure_one()
        custody = self._step_seed_custody()
        if not custody:
            return super()._update_reserved_quantity(need, location_id, lot_id, package_id, owner_id, strict)
        if (location_id != custody.location_id or (lot_id and lot_id != custody.lot_id)
                or (owner_id and owner_id != custody.owner_id)):
            return 0
        scoped = self.with_context(step_nursery_exact_seed=(_RESERVATION_SCOPE, custody.lot_id.id, custody.location_id.id))
        return super(StockMove, scoped)._update_reserved_quantity(
            need, location_id, custody.lot_id, package_id, custody.owner_id, strict)

    def _action_done(self, cancel_backorder=False):
        totals = {}
        for move in self.filtered(lambda row: row.state not in ("done", "cancel") and row.picked):
            custody = move._step_seed_custody()
            if not custody:
                continue
            consumed = move.move_line_ids.filtered(lambda row: row.picked and row.quantity > 0)
            if not consumed or any(line.owner_id != custody.owner_id or line.lot_id != custody.lot_id
                                  or line.location_id != custody.location_id for line in consumed):
                raise UserError(_("El consumo de maquila debe usar solo el lote y dueño de la orden."))
            for package in {line.package_id for line in consumed}:
                key = (move.company_id.id, move.product_id.id, custody.lot_id.id,
                       custody.owner_id.id, custody.location_id.id, package.id)
                taken = totals.get(key, 0) + sum(
                    line.quantity_product_uom for line in consumed if line.package_id == package)
                totals[key] = taken
                quants = self.env["stock.quant"].search([
                    ("company_id", "=", move.company_id.id), ("product_id", "=", move.product_id.id),
                    ("lot_id", "=", custody.lot_id.id), ("owner_id", "=", custody.owner_id.id),
                    ("location_id", "=", custody.location_id.id), ("package_id", "=", package.id or False),
                ])
                if quants:
                    self.env.cr.execute("SELECT id FROM stock_quant WHERE id IN %s ORDER BY id FOR UPDATE",
                                        (tuple(quants.ids),))
                if float_compare(taken, sum(quants.mapped("quantity")),
                                 precision_rounding=move.product_id.uom_id.rounding) > 0:
                    raise UserError(_("La semilla del cliente es insuficiente. No se permite dejar custodia negativa."))
        return super()._action_done(cancel_backorder=cancel_backorder)


class StockPackage(models.Model):
    _inherit = "stock.quant.package"

    step_nursery_production_id = fields.Many2one("mrp.production", string="Orden de vivero",
                                                ondelete="restrict", index=True)
    step_nursery_package_customer_id = fields.Many2one(related="step_nursery_production_id.step_nursery_customer_id",
                                                       string="Cliente de maquila")
    step_nursery_package_lot_id = fields.Many2one(related="step_nursery_production_id.lot_producing_id",
                                                  string="Lote de plantines")

    @api.constrains("step_nursery_production_id", "company_id")
    def _check_nursery_production(self):
        for pack in self.filtered("step_nursery_production_id"):
            order = pack.step_nursery_production_id
            order.check_access("read")
            if (order.company_id not in self.env.companies or (pack.company_id and order.company_id != pack.company_id)
                    or not (order.step_nursery_plan_ids or order.step_nursery_custody_id)):
                raise ValidationError(_("Seleccione una orden de vivero de la misma empresa autorizada."))

    step_nursery_sown_at = fields.Datetime(string="Siembra confirmada", readonly=True, copy=False)

    def action_step_nursery_mark_sown(self):
        self.ensure_one()
        self.check_access("write")
        self.step_nursery_production_id.check_access("read")
        if self.step_nursery_production_id.state not in ("progress", "to_close", "done"):
            raise UserError(_("Inicie la siembra de la orden antes de confirmar esta bandeja."))
        if not self.step_nursery_sown_at:
            self.step_nursery_sown_at = fields.Datetime.now()
        return True

    def action_step_nursery_package_label(self):
        self.ensure_one()
        self.check_access("read")
        self.step_nursery_production_id.check_access("read")
        if not self.step_nursery_production_id or not self.step_nursery_package_lot_id:
            raise UserError(_("Vincule la bandeja a una orden con lote de plantines antes de imprimir."))
        return self.env.ref("step_nursery_operations.action_nursery_package_label").report_action(self)


class NurseryServiceBill(models.Model):
    _name = "step.nursery.service.bill"
    _description = "Preparación de factura de servicio de maquila"
    _rec_name = "production_id"
    _check_company_auto = True

    production_id = fields.Many2one("mrp.production", required=True, ondelete="restrict", check_company=True)
    company_id = fields.Many2one(related="production_id.company_id", store=True, index=True)
    partner_id = fields.Many2one(related="production_id.step_nursery_customer_id")
    currency_id = fields.Many2one(related="company_id.currency_id")
    basis = fields.Selection([("trays", "Bandejas sembradas"), ("plants", "Plantines entregados")], required=True)
    shipment_id = fields.Many2one("stock.picking", string="Despacho", check_company=True, ondelete="restrict")
    tray_loan_id = fields.Many2one("step.nursery.tray.loan", string="Préstamo de bandejas", check_company=True)
    service_id = fields.Many2one("product.product", string="Servicio", required=True, check_company=True)
    price = fields.Monetary(string="Precio por unidad de cobro", required=True)
    extra_product_id = fields.Many2one("product.product", string="Insumo adicional", check_company=True)
    extra_price = fields.Monetary(string="Importe del insumo adicional")
    invoice_id = fields.Many2one("account.move", check_company=True, readonly=True, copy=False, ondelete="restrict")

    _sql_constraints = [
        ("shipment_once", "UNIQUE(production_id, shipment_id)", "El despacho de esta orden ya tiene una preparación."),
        ("bill_positive", "CHECK(price > 0 AND extra_price >= 0)", "Revise los valores de cobro."),
    ]

    def init(self):
        self.env.cr.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS step_nursery_service_by_trays_once
            ON step_nursery_service_bill (production_id) WHERE basis = 'trays'
        """)

    @api.constrains("production_id", "service_id", "basis", "shipment_id", "tray_loan_id",
                    "price", "extra_product_id", "extra_price")
    def _check_billing(self):
        for bill in self:
            if (not bill.partner_id or bill.service_id.type != "service"
                    or not isfinite(bill.price) or not isfinite(bill.extra_price)
                    or bool(bill.extra_price) != bool(bill.extra_product_id)):
                raise ValidationError(_("Seleccione una orden de maquila, un servicio y valores válidos."))
            if ((bill.basis == "plants" and not bill.shipment_id) or
                (bill.shipment_id and (bill.shipment_id.picking_type_id.code != "outgoing"
                 or bill.shipment_id.partner_id.commercial_partner_id != bill.partner_id.commercial_partner_id))):
                raise ValidationError(_("Use un despacho de plantines del cliente de la orden."))
            if bill.tray_loan_id and (
                bill.tray_loan_id.partner_id.commercial_partner_id != bill.partner_id.commercial_partner_id
                or (bill.shipment_id and bill.tray_loan_id.shipment_id != bill.shipment_id)
            ):
                raise ValidationError(_("El préstamo debe corresponder al cliente y al despacho de la maquila."))

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get("default_invoice_id") or any(vals.get("invoice_id") for vals in vals_list):
            raise UserError(_("Genere el documento con la acción Preparar factura."))
        return super().create(vals_list)

    def write(self, vals):
        if "invoice_id" in vals or self.filtered("invoice_id"):
            raise UserError(_("La preparación vinculada a una factura conserva sus datos."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _keep_invoice_source(self):
        if self.filtered("invoice_id"):
            raise UserError(_("No elimine la preparación vinculada a una factura."))

    def _get_service_qty(self):
        self.ensure_one()
        order = self.production_id
        if order.state != "done" or not order.lot_producing_id:
            raise UserError(_("Termine la orden y registre el lote de salida."))
        if self.basis == "trays":
            return len(order.step_nursery_packages.filtered("step_nursery_sown_at"))
        if self.shipment_id.state != "done":
            raise UserError(_("Valide el despacho antes de preparar el cobro por planta entregada."))
        lines = self.shipment_id.move_line_ids.filtered(lambda row:
            row.state == "done" and row.lot_id == order.lot_producing_id and row.product_id == order.product_id)
        unit = self.env.ref("uom.product_uom_unit")
        return sum(line.product_uom_id._compute_quantity(line.quantity, unit, round=False) for line in lines)

    def action_create_invoice(self):
        self.ensure_one()
        self.check_access("write")
        self.env.cr.execute("SELECT id FROM step_nursery_service_bill WHERE id=%s FOR UPDATE", (self.id,))
        self.invalidate_recordset()
        if not self.invoice_id:
            self._check_billing()
            qty = self._get_service_qty()
            if not qty:
                raise UserError(_("Confirme las bandejas sembradas o registre el despacho del lote antes de facturar."))
            if self.basis == "plants" and self.search_count([
                ("production_id", "=", self.production_id.id), ("basis", "=", "trays"), ("invoice_id", "!=", False),
            ]):
                raise UserError(_("Esta orden ya se cobró por bandejas."))
            if self.basis == "trays" and self.search_count([
                ("production_id", "=", self.production_id.id), ("basis", "=", "plants"), ("invoice_id", "!=", False),
            ]):
                raise UserError(_("Esta orden ya se cobró por plantines."))
            # Lock a shared writable native row before either basis is billed, so a competing
            # preparation cannot post two bases for the same order under repeatable read.
            self.production_id.check_access("read")
            self.env.cr.execute("SELECT id FROM mrp_production WHERE id=%s FOR UPDATE", (self.production_id.id,))
            self.env.cr.execute("UPDATE mrp_production SET write_date=write_date WHERE id=%s", (self.production_id.id,))
            lines = [Command.create({"product_id": self.service_id.id, "quantity": qty, "price_unit": self.price})]
            if self.extra_product_id:
                lines.append(Command.create({"product_id": self.extra_product_id.id, "quantity": 1,
                                             "price_unit": self.extra_price}))
            invoice = self.env["account.move"].with_company(self.company_id).create({
                "move_type": "out_invoice", "company_id": self.company_id.id, "partner_id": self.partner_id.id,
                "invoice_origin": self.production_id.name, "invoice_line_ids": lines,
            })
            super(NurseryServiceBill, self).write({"invoice_id": invoice.id})
        self.invoice_id.check_access("read")
        return {"type": "ir.actions.act_window", "name": _("Factura de maquila"), "res_model": "account.move",
                "res_id": self.invoice_id.id, "view_mode": "form", "target": "current"}
