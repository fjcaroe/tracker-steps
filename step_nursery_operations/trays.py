from math import isfinite

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class NurseryTrayLoan(models.Model):
    _name = "step.nursery.tray.loan"
    _description = "Préstamo de bandejas retornables"
    _rec_name = "partner_id"
    _order = "due_date, id"
    _check_company_auto = True

    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    partner_id = fields.Many2one("res.partner", string="Cliente", required=True, check_company=True)
    product_id = fields.Many2one("product.product", string="Tipo de bandeja", required=True, check_company=True)
    quantity = fields.Integer(string="Bandejas a prestar", required=True)
    due_date = fields.Date(string="Vence el", required=True, index=True)
    transfer_type_id = fields.Many2one("stock.picking.type", string="Tipo de traslado", required=True, check_company=True)
    origin_id = fields.Many2one("stock.location", string="Origen", required=True, check_company=True)
    custody_id = fields.Many2one("stock.location", string="Custodia de bandejas", required=True, check_company=True)
    shipment_id = fields.Many2one("stock.picking", string="Despacho de plantines", check_company=True, ondelete="restrict")
    dispatch_id = fields.Many2one("stock.picking", string="Traslado de bandejas", check_company=True,
                                   ondelete="restrict", readonly=True, copy=False)
    currency_id = fields.Many2one(related="company_id.currency_id")
    charge_product_id = fields.Many2one("product.product", string="Servicio por no devolución", check_company=True)
    charge_price = fields.Monetary(string="Cargo por bandeja")
    invoice_id = fields.Many2one("account.move", string="Borrador de cobro", check_company=True,
                                  readonly=True, ondelete="restrict", copy=False)
    quantity_out = fields.Float(string="Entregadas", compute="_compute_balance", store=True)
    quantity_returned = fields.Float(string="Devueltas", compute="_compute_balance", store=True)
    quantity_pending = fields.Float(string="Pendientes", compute="_compute_balance", store=True)
    overdue = fields.Boolean(string="Vencido", compute="_compute_overdue")

    _sql_constraints = [
        ("loan_quantity", "CHECK(quantity > 0)", "Ingrese una cantidad positiva de bandejas."),
        ("loan_dispatch_key", "UNIQUE(dispatch_id)", "El traslado ya está asociado a otro préstamo."),
        ("loan_charge", "CHECK(charge_price >= 0)", "El cargo no puede ser negativo."),
    ]

    @api.constrains("product_id", "charge_product_id", "charge_price", "origin_id", "custody_id",
                    "transfer_type_id", "shipment_id", "partner_id")
    def _check_loan(self):
        for loan in self:
            if (not loan.product_id.is_storable or loan.product_id.uom_id != self.env.ref("uom.product_uom_unit")
                    or loan.origin_id == loan.custody_id or loan.origin_id.usage != "internal"
                    or loan.custody_id.usage != "internal" or loan.custody_id.company_id != loan.company_id
                    or loan.transfer_type_id.code != "internal"):
                raise ValidationError(_("Use una bandeja almacenable en unidades, tipo interno y dos ubicaciones válidas."))
            if (loan.custody_id.parent_path or "").startswith(loan.origin_id.parent_path or "/"):
                raise ValidationError(_("La custodia debe quedar fuera del origen disponible para reservar."))
            if not isfinite(loan.charge_price) or (loan.charge_product_id and loan.charge_product_id.type != "service"):
                raise ValidationError(_("Configure un producto de servicio y un importe de cobro válido."))
            if loan.shipment_id and (
                loan.shipment_id.picking_type_id.code != "outgoing"
                or loan.shipment_id.partner_id.commercial_partner_id != loan.partner_id.commercial_partner_id
            ):
                raise ValidationError(_("El despacho de plantines debe ser una salida del mismo cliente."))

    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("dispatch_id") or vals.get("invoice_id") for vals in vals_list):
            raise UserError(_("Genere el traslado y el cobro desde el préstamo."))
        return super().create(vals_list)

    def write(self, vals):
        if {"dispatch_id", "invoice_id"} & vals.keys():
            raise UserError(_("Genere el traslado y el cobro desde el préstamo."))
        if {"product_id", "partner_id", "quantity", "company_id", "origin_id", "custody_id",
            "transfer_type_id", "shipment_id"} & vals.keys() and self.filtered("dispatch_id"):
            raise UserError(_("Un préstamo con traslado conserva sus condiciones de entrega."))
        if {"due_date", "charge_price", "charge_product_id"} & vals.keys() and self.filtered("invoice_id"):
            raise UserError(_("Un préstamo con documento de cobro conserva su vencimiento y tarifa."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_unshipped(self):
        if self.filtered("dispatch_id"):
            raise UserError(_("No elimine un préstamo con movimientos de inventario vinculados."))

    @api.depends("dispatch_id.move_ids.state", "dispatch_id.move_ids.quantity",
                 "dispatch_id.move_ids.returned_move_ids.state", "dispatch_id.move_ids.returned_move_ids.quantity")
    def _compute_balance(self):
        for loan in self:
            moves = loan.dispatch_id.move_ids.filtered(lambda m: m.state == "done" and m.product_id == loan.product_id)
            returned = moves.returned_move_ids.filtered(lambda m: m.state == "done" and m.product_id == loan.product_id)
            loan.quantity_out = sum(m.product_uom._compute_quantity(m.quantity, loan.product_id.uom_id) for m in moves)
            loan.quantity_returned = sum(m.product_uom._compute_quantity(m.quantity, loan.product_id.uom_id) for m in returned)
            loan.quantity_pending = max(0, loan.quantity_out - loan.quantity_returned)

    @api.depends("due_date", "quantity_pending")
    def _compute_overdue(self):
        today = fields.Date.context_today(self)
        for loan in self:
            loan.overdue = bool(loan.due_date and loan.due_date < today and loan.quantity_pending > 0)

    def _lock_loan(self):
        self.check_access("write")
        self.env.cr.execute("SELECT id FROM step_nursery_tray_loan WHERE id = %s FOR UPDATE", (self.id,))
        self.invalidate_recordset()

    def _open_form(self, record):
        record.check_access("read")
        return {"type": "ir.actions.act_window", "res_model": record._name,
                "res_id": record.id, "view_mode": "form", "target": "current"}

    def action_create_dispatch(self):
        self.ensure_one()
        self._lock_loan()
        if self.dispatch_id:
            return self._open_form(self.dispatch_id)
        self._check_loan()
        picking = self.env["stock.picking"].with_company(self.company_id).create({
            "company_id": self.company_id.id, "partner_id": self.partner_id.id,
            "picking_type_id": self.transfer_type_id.id, "location_id": self.origin_id.id,
            "location_dest_id": self.custody_id.id,
            "origin": self.shipment_id.name or _("Préstamo de bandejas"),
        })
        self.env["stock.move"].create({
            "name": self.product_id.display_name, "picking_id": picking.id,
            "product_id": self.product_id.id, "product_uom_qty": self.quantity,
            "product_uom": self.product_id.uom_id.id, "company_id": self.company_id.id,
            "location_id": self.origin_id.id, "location_dest_id": self.custody_id.id,
        })
        super(NurseryTrayLoan, self).write({"dispatch_id": picking.id})
        picking.action_confirm()
        return self._open_form(picking)

    def action_return_trays(self):
        self.ensure_one()
        self.check_access("read")
        self.dispatch_id.check_access("read")
        if self.dispatch_id.state != "done" or not self.quantity_pending:
            raise UserError(_("El préstamo no tiene un traslado validado con saldo por devolver."))
        return {
            "type": "ir.actions.act_window", "name": _("Devolver bandejas"),
            "res_model": "stock.return.picking", "view_mode": "form", "target": "new",
            "context": dict(self.env.context, active_model="stock.picking",
                            active_id=self.dispatch_id.id, active_ids=self.dispatch_id.ids),
        }

    def action_draft_charge(self):
        self.ensure_one()
        self._lock_loan()
        if self.invoice_id:
            return self._open_form(self.invoice_id)
        invoice = self._draft_charge()
        if not invoice:
            raise UserError(_("Se requiere saldo vencido, tarifa y un producto de servicio configurado."))
        return self._open_form(invoice)

    def _draft_charge(self):
        self.ensure_one()
        if (self.invoice_id or self.due_date >= fields.Date.context_today(self)
                or float_compare(self.quantity_pending, 0, precision_rounding=1) <= 0
                or not self.charge_product_id or not self.charge_price):
            return self.env["account.move"]
        invoice = self.env["account.move"].with_company(self.company_id).create({
            "move_type": "out_invoice", "partner_id": self.partner_id.id,
            "company_id": self.company_id.id, "currency_id": self.currency_id.id,
            "invoice_origin": self.dispatch_id.name,
            "invoice_line_ids": [fields.Command.create({
                "product_id": self.charge_product_id.id, "quantity": self.quantity_pending,
                "price_unit": self.charge_price,
            })],
        })
        super(NurseryTrayLoan, self).write({"invoice_id": invoice.id})
        return invoice

    @api.model
    def _cron_draft_overdue_charges(self):
        today = fields.Date.context_today(self)
        for loan in self.search([
            ("due_date", "<", today), ("invoice_id", "=", False), ("charge_product_id", "!=", False),
            ("quantity_pending", ">", 0), ("charge_price", ">", 0),
        ], limit=100):
            with self.env.cr.savepoint():
                loan._lock_loan()
                loan._draft_charge()
