from lxml import etree
from odoo import Command
from odoo.exceptions import ValidationError, AccessError
from odoo.tests import TransactionCase, tagged, new_test_user


@tagged('post_install','-at_install')
class BranchCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.parent=cls.env['res.company'].create({'name':'Private T145 parent'})
        cls.branch=cls.env['res.company'].create({'name':'Private T145 branch','parent_id':cls.parent.id})
        cls.foreign=cls.env['res.company'].create({'name':'Private T145 unrelated'})
        cls.user=new_test_user(cls.env(context=dict(cls.env.context,no_reset_password=True)),login='private-t145-manager',
            groups='stock.group_stock_manager,account.group_account_manager',company_id=cls.parent.id,
            company_ids=[Command.set((cls.parent|cls.branch|cls.foreign).ids)])
        cls.scope=cls.env(user=cls.user,su=False,context=dict(cls.env.context,allowed_company_ids=(cls.parent|cls.branch).ids))
        cls.journal=cls.env['account.journal'].create({'name':'Private T145 sales','code':'T145','type':'sale','company_id':cls.parent.id})
        cls.partner=cls.env['res.partner'].create({'name':'Private T145 partner'})

    def shipment(self):
        return self.scope['step.export.export'].create({'name':'Private T145 shipment','shipment_number':'PRIVATE-T145','company_id':self.parent.id})

    def tag(self,company):
        ot=self.env['step.packing.production'].with_company(company).create({'company_id':company.id})
        return self.env['stock.quant.package'].with_company(company).create({'name':'PRIVATE-T145-'+str(company.id),
            'is_fruit_tag':True,'step_tag_kind':'E','step_packing_production_id':ot.id})

    def guide(self,company):
        return self.env['step.dispatch.guide'].with_company(company).create({'external_folio':'PRIVATE-T145-'+str(company.id),
            'partner_id':self.partner.id,'company_id':company.id,'origin_address':'Private origin','destination_address':'Private destination',
            'carrier_id':self.partner.id,'truck_plate':'QA0145'})

    def test_actions_include_authorized_branches_and_preserve_current_company(self):
        model=self.scope(context=dict(self.scope.context,allowed_company_ids=self.branch.ids))['ir.actions.act_window']
        for alias in ('step_export.action_export_shipping_instructions','step_export.action_export_packing_list','step_export.action_export_consult_tags'):
            action=model._for_xml_id(alias)
            self.assertEqual(action['context']['allowed_company_ids'][0],self.branch.id)
            self.assertEqual(set(action['context']['allowed_company_ids']),set((self.parent|self.branch).ids))
            self.assertNotIn(self.foreign.id,action['context']['allowed_company_ids'])

    def test_shipment_and_packing_list_can_reference_branch_sources(self):
        shipment=self.shipment();tag=self.tag(self.branch);guide=self.guide(self.branch)
        shipment.write({'tag_ids':[Command.set(tag.ids)],'dispatch_guide_ids':[Command.set(guide.ids)]})
        tag=tag.with_env(self.scope)
        tag.write({'step_export_shipment_ids':[Command.set(shipment.ids)],'step_guide_ids':[Command.set(guide.ids)]})
        self.env['ir.sequence'].create({'name':'Private T145 packing','code':'step.export.packing.list','prefix':'PRIVATE-T145/','company_id':self.parent.id})
        packing=self.scope['step.export.packing.list'].create({'shipment_id':shipment.id,'guide_id':guide.id,'tag_ids':[Command.set(tag.ids)]})
        self.assertIn(tag,packing.available_tag_ids)
        self.assertIn(guide,packing.available_guide_ids)
        self.assertEqual(tag.company_id,self.branch)
        self.assertEqual(guide.company_id,self.branch)
        self.assertEqual(packing.company_id,self.parent)
        self.assertFalse(tag.quant_ids)

    def test_unrelated_company_is_rejected(self):
        shipment=self.shipment();tag=self.tag(self.foreign)
        wide=self.scope(context=dict(self.scope.context,allowed_company_ids=(self.parent|self.branch|self.foreign).ids))
        with self.cr.savepoint(),self.assertRaises(ValidationError):
            shipment.with_env(wide).write({'tag_ids':[Command.set(tag.ids)]})

    def test_accounting_boundary_is_preserved(self):
        tag=self.tag(self.branch).with_env(self.scope)
        invoice=self.scope['account.move'].create({'move_type':'out_invoice','company_id':self.parent.id,'journal_id':self.journal.id,'partner_id':self.partner.id})
        with self.cr.savepoint(),self.assertRaises(ValidationError):
            tag.write({'step_invoice_ids':[Command.set(invoice.ids)]})

    def test_consultation_displays_company_and_keeps_native_records(self):
        tag=self.tag(self.branch)
        view=self.scope['stock.quant.package'].get_view(view_id=self.scope.ref('step_export.view_export_fruit_tag_list').id,view_type='list')
        self.assertTrue(etree.fromstring(view['arch']).xpath("//field[@name='company_id'][@optional='show']"))
        found=self.scope['stock.quant.package'].search([('id','=',tag.id),('company_id','=',self.branch.id)])
        self.assertEqual(found.ids,tag.ids)
