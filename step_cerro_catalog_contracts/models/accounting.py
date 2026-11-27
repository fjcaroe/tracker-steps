from odoo import fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    account_id = fields.Many2one(ondelete='cascade')


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_uom = fields.Many2one(ondelete='set null')


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    uom_id = fields.Many2one(required=False, ondelete='set null')
