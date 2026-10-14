"""Editable accounting defaults for the export workflow, per company."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ExportAccountingCompany(models.Model):
    _inherit = "res.company"

    step_export_sale_journal_id = fields.Many2one(
        "account.journal", string="Diario facturas exportación",
        domain="[('type', '=', 'sale')]")
    step_export_purchase_journal_id = fields.Many2one(
        "account.journal", string="Diario compras productores",
        domain="[('type', '=', 'purchase')]")
    step_export_adjustment_journal_id = fields.Many2one(
        "account.journal", string="Diario ajustes DTE externos",
        domain="[('type', '=', 'general')]")
    step_export_income_account_id = fields.Many2one(
        "account.account", string="Cuenta ventas exportación",
        domain="[('account_type', '=', 'income')]")
    step_export_purchase_account_id = fields.Many2one(
        "account.account", string="Cuenta compra fruta productores",
        domain="[('account_type', 'in', ['expense', 'expense_direct_cost'])]")
    step_export_sale_tax_id = fields.Many2one(
        "account.tax", string="Impuesto venta exportación",
        domain="[('type_tax_use', '=', 'sale')]",
        help="Vacío: las facturas de exportación se crean sin impuesto de venta.")
    step_export_purchase_tax_id = fields.Many2one(
        "account.tax", string="Impuesto compra fruta",
        domain="[('type_tax_use', '=', 'purchase')]")

    @api.constrains(
        "step_export_sale_journal_id", "step_export_purchase_journal_id",
        "step_export_adjustment_journal_id", "step_export_income_account_id",
        "step_export_purchase_account_id", "step_export_sale_tax_id",
        "step_export_purchase_tax_id")
    def _check_export_accounting_company(self):
        for company in self:
            for field_name, journal_type in (
                    ("step_export_sale_journal_id", "sale"),
                    ("step_export_purchase_journal_id", "purchase"),
                    ("step_export_adjustment_journal_id", "general")):
                journal = company[field_name]
                if journal and (journal.company_id != company or journal.type != journal_type):
                    raise ValidationError(_("El diario de Exportaciones debe pertenecer a la empresa y tener el tipo correcto."))
            for field_name in ("step_export_income_account_id", "step_export_purchase_account_id"):
                account = company[field_name]
                if account:
                    allowed = company in account.company_ids if "company_ids" in account._fields else account.company_id == company
                    if not allowed:
                        raise ValidationError(_("La cuenta de Exportaciones debe pertenecer a la empresa."))
            for field_name, tax_type in (("step_export_sale_tax_id", "sale"),
                                         ("step_export_purchase_tax_id", "purchase")):
                tax = company[field_name]
                if tax and (tax.company_id != company or tax.type_tax_use != tax_type):
                    raise ValidationError(_("El impuesto de Exportaciones debe pertenecer a la empresa y tener el tipo correcto."))
