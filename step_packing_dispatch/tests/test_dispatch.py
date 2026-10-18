from odoo import Command
from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError, UserError, ValidationError


@tagged('post_install','-at_install')
class DispatchCase(TransactionCase):
    def fixture(self):
        e=self.env
        e.company.export_folio_mode='document'
        e.company.dispatch_dte_provider='third_party'
        self.producer=e['res.partner'].create({'name':'QA T91 productor','is_productor':True})
        self.receiver=e['res.partner'].create({'name':'QA T91 recibidor'})
        self.season=e['step.temporada'].create({'name':'QA T91 temporada'})
        self.species=e['step.especie'].create({'name':'QA T91 especie','type_especie':'frutal','group_especie':'seco'})
        self.product=e['product.product'].create({'name':'QA T91 caja','grupo_labor':'pack','is_fruta':True,'is_storable':True,'weight':5})
        self.packaging=e['product.packaging'].create({'name':'QA T91 embalaje','product_id':self.product.id,'qty':1})
        self.location=e['stock.warehouse'].search([('company_id','=',e.company.id)],limit=1).lot_stock_id
        self.shipment=e['step.export.export'].create({'name':'QA T91 embarque','company_id':e.company.id,
            'receiver_id':self.receiver.id,'season_id':self.season.id,'species_id':self.species.id,
            'line_ids':[Command.create({'product_id':self.product.id,'packaging_id':self.packaging.id,
                'pallet_qty':2,'boxes_per_pallet':10,'kg_per_box':5})]})
        self.plan=e['step.export.dispatch.order'].create({'name':'QA T91 instructivo','company_id':e.company.id,'shipment_id':self.shipment.id})
        self.plan.action_import_shipment_load()

    def tag(self,name,**values):
        tag=self.env['stock.quant.package'].create({'name':name,'is_fruit_tag':True,'step_tag_kind':'E',
            'step_tag_state':'created','step_producer_id':self.producer.id,'especie_id':self.species.id,
            'step_export_season_id':self.season.id,'box_count':10,'step_packaging_id':self.packaging.id,
            'step_tag_line_ids':[Command.create({'producer_id':self.producer.id,'product_id':self.product.id,
                'quantity':10,'boxes':10,'kilos':50})],**values})
        self.env['stock.quant']._update_available_quantity(self.product,self.location,10,package_id=tag)
        tag.action_step_validate_tag()
        return tag

    def guide(self,**values):
        return self.env['step.dispatch.guide'].create({'external_folio':'QA-T91-'+str(self.env['step.dispatch.guide'].search_count([])),
            'partner_id':self.receiver.id,'carrier_id':self.receiver.id,'origin_address':'Packing QA',
            'destination_address':'Puerto QA','truck_plate':'QA0000','dispatch_instruction_id':self.plan.id,**values})

    def test_instruction_totals_and_source_preservation(self):
        self.fixture()
        before=(self.shipment.line_ids.ids,self.shipment.box_qty,self.shipment.kg_qty)
        self.plan.load_line_ids.pallet_qty=100
        self.assertEqual((self.plan.pallet_qty,self.plan.box_qty,self.plan.kg_qty,self.plan.truck_qty),(100,1000,5000,5))
        self.plan.load_line_ids.pallet_qty=101
        self.assertEqual(self.plan.truck_qty,6)
        self.assertEqual((self.shipment.line_ids.ids,self.shipment.box_qty,self.shipment.kg_qty),before)
        with self.assertRaises(UserError),self.cr.savepoint():self.plan.action_import_shipment_load()
        with self.assertRaises(ValidationError),self.cr.savepoint():self.plan.pallets_per_truck=0

    def test_scan_selection_guide_and_packing_list(self):
        self.fixture();a=self.tag('QA-T91-A');b=self.tag('QA-T91-B')
        guide=self.guide()
        self.assertIn(a,guide.available_load_tag_ids)
        guide.scan_code=a.name;guide._scan()
        guide.scan_code=a.name;guide._scan()
        self.assertEqual(guide.load_tag_ids,a)
        guide.write({'load_tag_ids':[Command.link(b.id)]})
        self.assertEqual(guide.step_export_shipment_id,self.shipment)
        self.assertEqual(self.shipment.tag_ids,a|b)
        guide.action_load_pallet_detail()
        self.assertEqual((guide.line_ids.quantity,guide.total_kilos),(20,100))
        driver=self.env['res.partner'].create({'name':'QA T91 chofer','step_chofer':True})
        reason=self.env['step.dispatch.transfer.reason'].search([],limit=1)
        self.assertTrue(reason)
        guide.write({'driver_partner_id':driver.id,'transfer_reason_id':reason.id})
        guide.action_confirm()
        self.assertEqual(guide.state,'confirmed')
        action=guide.action_create_packing_list()
        packing=self.env['step.export.packing.list'].browse(action['res_id'])
        self.assertEqual(packing.tag_ids,a|b)
        self.assertEqual((packing.box_qty,packing.kg_qty),(20,100))
        self.assertEqual(guide.action_create_packing_list()['res_id'],packing.id)
        with self.assertRaises(ValidationError),self.cr.savepoint():packing.tag_ids=a
        with self.assertRaises(UserError),self.cr.savepoint():guide.load_tag_ids=a

    def test_filters_capacity_and_duplicate_guides(self):
        self.fixture();a=self.tag('QA-T91-F-A');b=self.tag('QA-T91-F-B');c=self.tag('QA-T91-F-C')
        wrong_season=self.env['step.temporada'].create({'name':'QA T91 otra temporada'})
        wrong=self.tag('QA-T91-WRONG',step_export_season_id=wrong_season.id)
        guide=self.guide(load_tag_ids=[Command.set(a.ids)])
        self.assertNotIn(wrong,guide.available_load_tag_ids)
        with self.assertRaises(ValidationError),self.cr.savepoint():guide.load_tag_ids=wrong
        with self.assertRaises(ValidationError),self.cr.savepoint():self.guide(load_tag_ids=[Command.set(a.ids)])
        with self.assertRaises(ValidationError),self.cr.savepoint():guide.load_tag_ids=a|b|c
        with self.assertRaises(UserError),self.cr.savepoint():self.plan.load_line_ids.pallet_qty=5
        guide.action_cancel()
        other=self.guide(load_tag_ids=[Command.set(a.ids)])
        self.assertEqual(other.load_tag_ids,a)
        other.action_cancel()
        self.plan.load_line_ids.write({'pallet_qty':1,'label':'QA marca'})
        self.plan.load_line_ids.copy({'instruction_id':self.plan.id,'label':False,'pallet_qty':1})
        # Both tags match only the wildcard row, whose capacity is one.
        with self.assertRaises(ValidationError),self.cr.savepoint():self.guide(load_tag_ids=[Command.set((a|b).ids)])

    def test_company_access_and_native_inspection_menus(self):
        self.fixture()
        other=self.env['res.company'].create({'name':'QA T91 otra empresa'})
        record=self.env['step.export.dispatch.order'].create({'name':'QA T91 ajeno','company_id':other.id})
        user=self.env['res.users'].with_context(no_reset_password=True).create({'name':'QA T91 operador','login':'qa-t91-operator',
            'company_id':self.env.company.id,'company_ids':[Command.set(self.env.company.ids)],
            'groups_id':[Command.set([self.env.ref('base.group_user').id,self.env.ref('stock.group_stock_user').id])]})
        model=self.env['step.export.dispatch.order'].with_user(user).with_context(allowed_company_ids=self.env.company.ids)
        self.assertIn(self.plan,model.search([]));self.assertNotIn(record,model.search([]))
        with self.assertRaises(AccessError):record.with_user(user).read(['name'])
        children=self.env['ir.ui.menu'].search([('parent_id','=',self.env.ref('step_packing_operations.menu_packing_operations_dispatch').id)])
        self.assertEqual(set(children.mapped('name')),{'Instructivo de despacho','Despacho','Packing List','Traslado lotes'})
        self.assertEqual(self.env.ref('step_packing_dispatch.sag_action').res_model,'step.packing.inspection')
        self.assertEqual(self.env.ref('step_packing_dispatch.internal_action').res_model,'step.packing.inspection')
