"""Producer purchase defaults; preserve installed columns and external consumers."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProducerAccountingCompany(models.Model):
    _inherit = 'res.company'

    def action_step_producer_accounting(self):
        company = self.env.company
        view = self.env.ref('step_producers.view_producer_accounting_form')
        return {'type': 'ir.actions.act_window', 'name': _('Ajustes contables de Productores'),
                'res_model': 'res.company', 'res_id': company.id,
                'view_mode': 'form', 'views': [(view.id, 'form')], 'target': 'current'}
    step_producer_advance_product_id = fields.Many2one(
        'product.product', string='Concepto de anticipo de contrato', check_company=True)
    step_producer_advance_account_id = fields.Many2one(
        'account.account', string='Cuenta de anticipo de contrato', check_company=True,
        domain="[('account_type', 'in', ['asset_current', 'asset_non_current', 'asset_prepayments']), ('deprecated', '=', False)]")

    @api.constrains('step_producer_advance_product_id', 'step_producer_advance_account_id')
    def _check_contract_advance_company(self):
        for company in self:
            product = company.step_producer_advance_product_id
            account = company.step_producer_advance_account_id
            if product.company_id and product.company_id != company:
                raise ValidationError(_('El concepto de anticipo debe pertenecer a la empresa o ser compartido.'))
            if account and (company not in account.company_ids or account.deprecated or
                            account.account_type not in ('asset_current', 'asset_non_current', 'asset_prepayments')):
                raise ValidationError(_('Configure una cuenta de activo vigente para el anticipo de contrato de esta empresa.'))
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
