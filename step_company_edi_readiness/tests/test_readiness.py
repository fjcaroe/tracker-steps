from datetime import date
from unittest.mock import patch
from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged, Form
from odoo.addons.l10n_cl_edi.models.account_move import AccountMove as NativeMove


@tagged('post_install','-at_install')
class CompanyReadinessCase(TransactionCase):
    def pending_company(self):
        company=self.env.company
        company.write({'l10n_cl_dte_service_provider':'SII','l10n_cl_dte_email':False,
            'l10n_cl_dte_resolution_number':False,'l10n_cl_dte_resolution_date':False})
        return company

    def invoice(self,company):
        journal=self.env['account.journal'].new({'name':'QA DTE','code':'QDTE','type':'sale',
            'company_id':company.id,'l10n_cl_point_of_sale_type':'online'})
        receiver=self.env['res.partner'].new({'name':'QA DTE Receiver','l10n_cl_dte_email':'qa.receiver@example.invalid'})
        doc=self.env['l10n_latam.document.type'].search([('code','=','33'),('country_id','=',self.env.ref('base.cl').id)],limit=1)
        self.assertTrue(doc)
        return self.env['account.move'].new({'move_type':'out_invoice','company_id':company.id,
            'journal_id':journal,'partner_id':receiver,'invoice_date':fields.Date.today(),
            'l10n_latam_document_type_id':doc.id})

    def test_general_company_save_does_not_require_fiscal_placeholders(self):
        company=self.pending_company()
        original=company.read(['name','vat','partner_id','currency_id'])[0]
        with Form(company) as form:form.phone='QA PHONE'
        self.assertEqual(company.phone,'QA PHONE')
        self.assertEqual(company.read(['name','vat','partner_id','currency_id'])[0],original)
        self.assertFalse(company.l10n_cl_dte_email)
        self.assertFalse(company.l10n_cl_dte_resolution_number)
        self.assertFalse(company.l10n_cl_dte_resolution_date)

    def test_warning_lists_missing_configuration(self):
        company=self.pending_company()
        self.assertTrue(company.step_sii_configuration_pending)
        for label in ('Correo DTE','Número de resolución SII','Fecha de resolución SII'):
            self.assertIn(label,company.step_sii_missing_configuration)

    def test_native_document_validation_still_rejects_missing_dte_email(self):
        invoice=self.invoice(self.pending_company())
        with self.assertRaises(UserError) as error:invoice._l10n_cl_edi_post_validation()
        self.assertIn('DTE',str(error.exception))

    def test_resolution_checked_after_native_validation_without_sending(self):
        company=self.pending_company();invoice=self.invoice(company)
        with patch.object(NativeMove,'_l10n_cl_edi_post_validation',return_value=True) as native:
            with self.assertRaises(UserError) as error:invoice._l10n_cl_edi_post_validation()
            self.assertIn('resolución',str(error.exception))
            native.assert_called_once()
        company.write({'l10n_cl_dte_resolution_number':'QA-TEST','l10n_cl_dte_resolution_date':date(2020,1,1)})
        with patch.object(NativeMove,'_l10n_cl_edi_post_validation',return_value=True) as native:
            self.assertTrue(invoice._l10n_cl_edi_post_validation());native.assert_called_once()
