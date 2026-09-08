from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = "product.category"

    management_budget_group_id = fields.Many2one(
        "step.management.budget.group", string="Grupo presupuesto (Gestión y Costos)",
        help="Grupo presupuestario por defecto para los productos de esta "
             "categoría. Se resuelve producto → subcategoría → categoría.",
    )


class ProductTemplate(models.Model):
    _inherit = "product.template"

    management_budget_group_id = fields.Many2one(
        "step.management.budget.group", string="Grupo presupuesto (Gestión y Costos)",
        help="Grupo presupuestario específico de este producto. Si está vacío "
             "se toma el de la (sub)categoría. La coherencia de empresa se "
             "valida al usar el producto en un presupuesto.",
    )

    def _get_management_budget_group(self, company=None):
        """Devuelve el grupo presupuestario aplicable: primero el del producto,
        luego el de la categoría y sus ascendientes. Sin coincidencias vagas."""
        self.ensure_one()
        company = company or self.env.company
        if (
            self.management_budget_group_id
            and self.management_budget_group_id.company_id == company
        ):
            return self.management_budget_group_id
        category = self.categ_id
        while category:
            if (
                category.management_budget_group_id
                and category.management_budget_group_id.company_id == company
            ):
                return category.management_budget_group_id
            category = category.parent_id
        return self.env["step.management.budget.group"]


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_management_budget_group(self, company=None):
        self.ensure_one()
        return self.product_tmpl_id._get_management_budget_group(company=company)
