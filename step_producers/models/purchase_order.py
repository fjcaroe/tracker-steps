"""Reference the producer contract from later fruit purchase orders."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    step_producer_contract_id = fields.Many2one(
        "step.producer.purchase.contract", string="Contrato productor", check_company=True,
        domain="[('partner_id', '=', partner_id), ('company_id', '=', company_id), ('state', 'in', ['confirmed', 'closed'])]",
    )

    @api.constrains("step_producer_contract_id", "partner_id", "company_id")
    def _check_step_producer_contract(self):
        for order in self.filtered("step_producer_contract_id"):
            contract = order.step_producer_contract_id
            if contract.partner_id != order.partner_id or contract.company_id != order.company_id:
                raise ValidationError(_("La orden de compra debe usar el mismo productor y empresa del contrato."))
            if any(line.step_producer_contract_product_id and
                   line.step_producer_contract_product_id.contract_id != contract
                   for line in order.order_line):
                raise ValidationError(_("Los productos de la orden deben pertenecer al contrato elegido."))


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    step_producer_contract_product_id = fields.Many2one(
        "step.producer.purchase.contract.product", string="Producto de contrato", check_company=True,
    )

    @api.onchange("product_id")
    def _onchange_step_producer_contract_product(self):
        for line in self:
            contract = line.order_id.step_producer_contract_id
            matches = contract.product_line_ids.filtered(lambda item: item.product_id == line.product_id)
            line.step_producer_contract_product_id = matches if len(matches) == 1 else False

    @api.constrains("step_producer_contract_product_id", "order_id", "product_id")
    def _check_step_producer_contract_product(self):
        for line in self.filtered("step_producer_contract_product_id"):
            contract_line = line.step_producer_contract_product_id
            if (contract_line.contract_id != line.order_id.step_producer_contract_id or
                    contract_line.product_id != line.product_id):
                raise ValidationError(_("La línea de compra debe corresponder a un producto del contrato elegido."))
