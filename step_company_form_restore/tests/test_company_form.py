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

    def test_company_form_loads_identity_and_allows_editing_without_mutating_data(self):
        company=self.env.company
        before=company.read(['name','vat','partner_id','currency_id'])[0]
        count=self.env['res.company'].search_count([])
        original_phone=company.phone
        form=Form(company)
        form.phone='QA PHONE'
        self.assertEqual(form.phone,'QA PHONE')
        self.assertEqual(company.phone,original_phone)
        self.assertEqual(company.read(['name','vat','partner_id','currency_id'])[0],before)
        self.assertEqual(self.env['res.company'].search_count([]),count)

    def test_obsolete_previred_fields_are_not_rendered(self):
        from odoo.addons.step_company_form_restore.hooks import LEGACY
        arch=self.env['res.company']._get_view(view_type='form')[0]
        self.assertFalse({node.get('name') for node in arch.xpath('.//field')} & LEGACY)

    def test_branch_dialog_generated_contact_is_not_required_by_client(self):
        from odoo.tests.common import new_test_user
        user=new_test_user(self.env,login='branch_view_regression',groups='base.group_system')
        self.assertFalse(user.has_group('base.group_no_one'))
        # A real exporter bank domain also depends on partner_id. Make that
        # dependency explicit even in a minimal Community-only installation.
        self.env['ir.ui.view'].create({
            'name':'branch.contact.dependency.regression','model':'res.company',
            'inherit_id':self.env.ref('base.view_company_form').id,
            'arch':"<field name='email' position='attributes'><attribute name='invisible'>not partner_id</attribute></field>"})
        model=self.env['res.company'].with_user(user)
        for kind in ('form','list'):
            arch=etree.fromstring(model.get_view(view_type=kind)['arch'])
            nodes=arch.xpath("//field[@name='partner_id']")
            self.assertTrue(nodes)
            self.assertTrue(all(n.get('required') in ('0','False') for n in nodes))
        self.assertTrue(model._fields['partner_id'].required,
                        'Native database invariant must remain required')

    def test_native_branch_creation_generates_its_own_contact(self):
        root=self.env.company
        before=root.read(['name','partner_id','currency_id'])[0]
        count=self.env['res.company'].search_count([('parent_id','=',root.id)])
        parent=Form(root)
        with parent.child_ids.new() as branch:
            branch.name='Branch Native Contact Regression'
        parent.save()
        child=self.env['res.company'].search([('parent_id','=',root.id),('name','=','Branch Native Contact Regression')])
        self.assertEqual(len(child),1)
        self.assertTrue(child.partner_id)
        self.assertNotEqual(child.partner_id,root.partner_id)
        self.assertEqual(child.currency_id,root.currency_id)
        self.assertEqual(root.read(['name','partner_id','currency_id'])[0],before)
        self.assertEqual(self.env['res.company'].search_count([('parent_id','=',root.id)]),count+1)
