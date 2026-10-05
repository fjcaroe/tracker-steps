"""Producer purchase defaults; preserve installed columns and external consumers."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProducerAccountingCompany(models.Model):
    _inherit = 'res.company'
    step_export_purchase_journal_id = fields.Many2one('account.journal', string='Diario compras productores', domain="[('type','=','purchase')]")
    step_export_purchase_account_id = fields.Many2one('account.account', string='Cuenta compra fruta productores', domain="[('account_type','in',['expense','expense_direct_cost'])]")
    step_export_purchase_tax_id = fields.Many2one('account.tax', string='Impuesto compra fruta', domain="[('type_tax_use','=','purchase')]")

    @api.constrains('step_export_purchase_journal_id', 'step_export_purchase_account_id', 'step_export_purchase_tax_id')
    def _check_producer_accounting_company(self):
        for company in self:
            journal, account, tax = company.step_export_purchase_journal_id, company.step_export_purchase_account_id, company.step_export_purchase_tax_id
            if journal and (journal.company_id != company or journal.type != 'purchase'):
                raise ValidationError(_('El diario de Productores debe ser de compras y pertenecer a la empresa.'))
            if account and company not in account.company_ids:
                raise ValidationError(_('La cuenta de Productores debe pertenecer a la empresa.'))
            if tax and (tax.company_id != company or tax.type_tax_use != 'purchase'):
                raise ValidationError(_('El impuesto de Productores debe ser de compra y pertenecer a la empresa.'))
