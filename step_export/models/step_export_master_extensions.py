# -*- coding: utf-8 -*-
"""Shared masters required by the export sales programme."""

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    step_export_receiver = fields.Boolean(string="Recibidor")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    step_export_enabled = fields.Boolean(string="Es exportación")
    step_export_fruit_category_id = fields.Many2one(
        "step.management.fruit.category", string="Categoría de fruta")
    step_export_base_product_id = fields.Many2one(
        "product.template", string="Producto base", domain="[('is_fruta', '=', True)]")
    step_export_payment_concept_id = fields.Many2one(
        "step.export.payment.concept", string="Concepto de liquidación")
    step_export_budget_cost = fields.Float(string="Costo presupuesto", digits=(16, 4))


class StockPackageType(models.Model):
    _inherit = "stock.package.type"

    step_export_pallets_20 = fields.Float(string="Pallets por contenedor de 20 pies", digits=(12, 2))
    step_export_pallets_40 = fields.Float(string="Pallets por contenedor de 40 pies", digits=(12, 2))
