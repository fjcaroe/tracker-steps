from unittest.mock import patch
from lxml import etree
from odoo.tests import TransactionCase, tagged, Form


@tagged('post_install', '-at_install')
class ManualContactCase(TransactionCase):
    def test_manual_company_form_without_iap(self):
        with patch.object(type(self.env['iap.autocomplete.api']), '_contact_iap', side_effect=AssertionError('No external enrichment allowed')):
            form = Form(self.env['res.partner'])
            form.company_type = 'company'
            form.name = 'QA Agricultural Supplier'
            partner = form.save()
            self.assertEqual(partner.name, 'QA Agricultural Supplier')
            self.assertTrue(partner.is_company)
            if 'supplier_rank' in partner._fields:
                partner.supplier_rank = 1
                self.assertEqual(partner.supplier_rank, 1)

    def test_form_has_no_paid_enrichment_widgets(self):
        view=self.env['res.partner'].get_view(view_type='form')
        arch=etree.fromstring(view['arch'])
        self.assertFalse(arch.xpath("//field[@widget='field_partner_autocomplete']"))
        self.assertTrue(arch.xpath("//field[@name='name']"))
        self.assertTrue(arch.xpath("//field[@name='vat']"))

    def test_no_external_suggestions_or_enrichment_requests(self):
        partner=self.env['res.partner']
        with patch.object(type(self.env['iap.autocomplete.api']), '_contact_iap', side_effect=AssertionError('No external request')):
            self.assertEqual(partner.autocomplete_by_name('QA Supplier'), [])
            self.assertEqual(partner.autocomplete_by_vat('CL123'), [])
            self.assertEqual(partner.enrich_by_duns('0001'), {})
            self.assertEqual(partner.enrich_by_gst('0001'), {})
            self.assertEqual(partner.enrich_by_domain('example.invalid'), {})

    def test_existing_contact_lookup_remains_available(self):
        partner=self.env['res.partner'].create({'name':'QA Existing Supplier'})
        self.assertIn(partner.id,[row[0] for row in self.env['res.partner'].name_search('QA Existing Supplier')])
