# -*- coding: utf-8 -*-
"""Shared masters required by the export sales programme."""

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    step_export_receiver = fields.Boolean(string="Recibidor")


class ProductTemplate(models.Model):
    _inherit = "product.template"

    step_export_fruit_category_id = fields.Many2one(
        "step.management.fruit.category", string="Categoría de fruta")
    step_export_base_product_id = fields.Many2one(
        "product.template", string="Producto base", domain="[('is_fruta', '=', True)]")
    step_export_payment_concept_id = fields.Many2one(
        "step.export.payment.concept", string="Concepto de liquidación")
    step_export_budget_cost = fields.Float(string="Costo presupuesto", digits=(16, 4))
