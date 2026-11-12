from datetime import timedelta
from math import isfinite

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare


class NurseryDelivery(models.Model):
    _name = "step.nursery.delivery"
    _description = "Cuota de entrega de plantines"
    _rec_name = "delivery_at"
    _order = "delivery_at, id"
    _check_company_auto = True

    line_id = fields.Many2one("sale.order.line", string="Línea de venta", required=True,
                              check_company=True, ondelete="cascade", index=True)
    company_id = fields.Many2one(related="line_id.company_id", store=True, index=True)
    delivery_at = fields.Datetime(string="Entrega pactada", required=True)
    quantity = fields.Float(string="Cantidad", digits="Product Unit of Measure", required=True)
    uom_id = fields.Many2one(related="line_id.product_uom", string="Unidad")
    procurement_group_id = fields.Many2one("procurement.group", readonly=True, copy=False)
    _sql_constraints = [
        ("delivery_date", "UNIQUE(line_id, delivery_at)", "La línea ya tiene una entrega para esta fecha."),
        ("delivery_quantity", "CHECK(quantity > 0)", "La cantidad a entregar debe ser positiva."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        orders = self.env["sale.order.line"].browse([v.get("line_id") for v in vals_list if v.get("line_id")]).order_id
        self._check_quotation(orders)
        if any(v.get("procurement_group_id") for v in vals_list):
            raise UserError(_("El grupo de entrega se asigna al confirmar el pedido."))
        return super().create(vals_list)

    def write(self, vals):
        self._check_quotation(self.line_id.order_id)
        if "line_id" in vals or "procurement_group_id" in vals:
            raise UserError(_("No se puede reasignar una cuota a otra línea o grupo."))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_unconfirmed(self):
        self._check_quotation(self.line_id.order_id)

    @api.model
    def _check_quotation(self, orders):
        if orders.filtered(lambda order: order.state not in ("draft", "sent")):
            raise UserError(_("Las cuotas se editan antes de confirmar el pedido."))

    def _procurement_group(self):
        self.ensure_one()
        order = self.line_id.order_id
        if self.procurement_group_id:
            return self.procurement_group_id
        group = self.env["procurement.group"].create(dict(
            self.line_id._prepare_procurement_group_vals(),
            name="%s / %s" % (order.name, fields.Datetime.to_string(self.delivery_at)),
        ))
        # This is only called by the native stock launch from a sale order.
        super(NurseryDelivery, self).write({"procurement_group_id": group.id})
        return group


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_confirm(self):
        for line in self.order_line.filtered("step_nursery_delivery_ids"):
            line._check_nursery_schedule()
        return super().action_confirm()


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    step_nursery_delivery_ids = fields.One2many("step.nursery.delivery", "line_id", string="Cuotas de entrega",
                                              copy=False, groups="sales_team.group_sale_salesman")

    def _check_nursery_schedule(self):
        self.ensure_one()
        schedule = self.step_nursery_delivery_ids
        rounding = self.product_uom.rounding
        if (not self.product_id.is_storable or self.display_type
                or not all(isfinite(row.quantity) and row.quantity > 0 for row in schedule)
                or float_compare(sum(schedule.mapped("quantity")), self.product_uom_qty,
                                 precision_rounding=rounding)):
            raise ValidationError(_("Las cuotas de un producto almacenable deben sumar la cantidad vendida."))
        if any(row.delivery_at < self.order_id.date_order for row in schedule):
            raise ValidationError(_("Las entregas no pueden anteceder a la fecha del pedido."))

    def write(self, vals):
        if {"product_uom_qty", "product_uom", "product_id", "order_id"} & vals.keys():
            for line in self.filtered(lambda item: item.state == "sale" and item.step_nursery_delivery_ids):
                if any(key in vals and vals[key] != current for key, current in (
                    ("product_uom_qty", line.product_uom_qty), ("product_uom", line.product_uom.id),
                    ("product_id", line.product_id.id), ("order_id", line.order_id.id),
                )):
                    raise UserError(_("La línea tiene cuotas confirmadas. Modifique las entregas en Inventario."))
        return super().write(vals)

    def _create_procurements(self, product_qty, procurement_uom, origin, values):
        self.ensure_one()
        schedule = self.step_nursery_delivery_ids
        if not schedule:
            return super()._create_procurements(product_qty, procurement_uom, origin, values)
        self._check_nursery_schedule()
        expected = self.product_uom._compute_quantity(self.product_uom_qty, procurement_uom, round=False)
        if float_compare(expected, product_qty, precision_rounding=procurement_uom.rounding):
            raise UserError(_("No se pueden relanzar parcialmente las cuotas de esta línea. Revise sus despachos."))
        procurements = []
        for installment in schedule:
            qty = self.product_uom._compute_quantity(installment.quantity, procurement_uom, round=False)
            installment_values = dict(
                values,
                group_id=installment._procurement_group(),
                date_deadline=installment.delivery_at,
                date_planned=installment.delivery_at - timedelta(days=self.company_id.security_lead),
            )
            procurements += super()._create_procurements(qty, procurement_uom, origin, installment_values)
        return procurements
