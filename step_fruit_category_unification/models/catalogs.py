from odoo import api, fields, models


class Picking(models.Model):
    _inherit = 'stock.picking'
    fruit_category_id = fields.Many2one('step.management.fruit.category', string='Categoría de fruta', check_company=True)
    fruit_class_id = fields.Many2one('step.management.fruit.category', string='Categoría de origen', check_company=True)


class ReceiptLine(models.Model):
    _inherit = 'step.packing.picking.tag.line'
    _check_company_auto = True
    category_id = fields.Many2one('step.management.fruit.category', string='Categoría de fruta', check_company=True)


class ContractProduct(models.Model):
    _inherit = 'step.producer.purchase.contract.product'
    category_id = fields.Many2one('step.management.fruit.category', string='Categoría', check_company=True)


class Category(models.Model):
    _inherit = 'step.management.fruit.category'
    # Existing Packing valuation code obtains the contract category through
    # this accessor. Both now use the SAME master, so the accessor is identity.
    # Its original stored column remains as migration history, never edited.
    step_contract_category_id = fields.Many2one('step.management.fruit.category',
        string='Categoría compartida en contratos', compute='_compute_contract_category',
        store=False, readonly=True, check_company=True)

    def _compute_contract_category(self):
        for category in self:
            category.step_contract_category_id = category
