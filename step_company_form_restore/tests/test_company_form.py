from lxml import etree
from odoo.tests import TransactionCase, tagged, Form


@tagged('post_install', '-at_install')
class CompanyFormCase(TransactionCase):
    def test_generic_form_is_the_complete_native_form(self):
        companies=self.env['res.company']
        arch,view=companies._get_view(view_type='form')
        self.assertEqual(view,self.env.ref('base.view_company_form'))
        self.assertTrue(arch.xpath('//notebook/page'))
        for name in ('name','vat','currency_id','country_id','phone','email'):
            self.assertTrue(arch.xpath("//field[@name='%s']" % name),name)
        expected=companies.get_view(view_id=view.id,view_type='form')['arch']
        self.assertEqual(companies.get_view(view_type='form')['arch'],expected)

    def test_generic_list_is_native_and_allows_standard_actions(self):
        arch,view=self.env['res.company']._get_view(view_type='list')
        self.assertEqual(view,self.env.ref('base.view_company_tree'))
        self.assertNotEqual(arch.get('create'),'false')
        action=self.env.ref('base.action_res_company_form')
        self.assertEqual(action.view_id,view)
        self.assertEqual(action.views[0],(view.id,'list'))
        self.assertIn('form',action.view_mode)

    def test_alphabetical_specialized_form_cannot_replace_generic_form(self):
        special=self.env['ir.ui.view'].create({'name':'aaa.company.compact.regression','model':'res.company','priority':16,
            'arch':'<form create="false"><sheet><field name="name"/></sheet></form>'})
        arch,view=self.env['res.company']._get_view(view_type='form')
        self.assertEqual(view,self.env.ref('base.view_company_form'))
        explicit=self.env['res.company'].get_view(view_id=special.id,view_type='form')
        self.assertFalse(etree.fromstring(explicit['arch']).xpath('//notebook'))

    def test_folio_and_packing_actions_remain_explicit(self):
        for xmlid,field in [('step_export_shipping_design.folio_company_action','export_folio_mode'),('step_packing_stock_flow.packing_company_action','step_packing_warehouse_id')]:
            action=self.env.ref(xmlid,raise_if_not_found=False)
            if not action: continue
            form=next(view for view,kind in action.views if kind=='form')
            self.assertTrue(form)
            self.assertNotEqual(form,self.env.ref('base.view_company_form').id)
            self.assertTrue(etree.fromstring(self.env['res.company'].get_view(view_id=form,view_type='form')['arch']).xpath("//field[@name='%s']" % field))

    def test_company_form_keeps_identity_and_currency_when_editing_phone(self):
        company=self.env.company
        before=company.read(['name','vat','partner_id','currency_id'])[0]
        count=self.env['res.company'].search_count([])
        with Form(company) as form: form.phone='QA PHONE'
        self.assertEqual(company.phone,'QA PHONE')
        self.assertEqual(company.read(['name','vat','partner_id','currency_id'])[0],before)
        self.assertEqual(self.env['res.company'].search_count([]),count)
