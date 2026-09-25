from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'
    purchase_contract_id = fields.Many2one('step.management.purchase.contract', string='Contrato de compra',
        check_company=True, copy=False, domain="[('partner_id', '=', partner_id), ('company_id', '=', company_id), ('state', '=', 'confirmed'), ('is_superseded', '=', False)]")

    @api.constrains('purchase_contract_id', 'partner_id', 'currency_id', 'company_id')
    def _check_purchase_contract(self):
        for order in self.filtered('purchase_contract_id'):
            c = order.purchase_contract_id
            if c.partner_id != order.partner_id or c.currency_id != order.currency_id:
                raise ValidationError(_("El proveedor y la moneda deben coincidir con el contrato."))

    def button_confirm(self):
        for order in self.filtered('purchase_contract_id'):
            c = order.purchase_contract_id
            if c.state != 'confirmed' or c.is_superseded:
                raise ValidationError(_("Seleccione un contrato confirmado y vigente."))
        return super().button_confirm()


class Picking(models.Model):
    _inherit = 'stock.picking'
    purchase_contract_id = fields.Many2one(related='purchase_id.purchase_contract_id', string='Contrato de compra', readonly=True)
