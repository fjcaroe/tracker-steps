from lxml import etree
from odoo.tests import TransactionCase, Form, tagged
from odoo.tools.safe_eval import safe_eval


@tagged('post_install','-at_install')
class TicketRevisionCase(TransactionCase):
    def test_process_header_uses_existing_packing_date_and_fundo(self):
        model=self.env['step.packing.production']
        arch=etree.fromstring(model.get_view(view_type='form')['arch'])
        names=arch.xpath("//group[@name='ot_identity_left']/field/@name")
        self.assertEqual(names[:3],['packing_partner_id','date','step_packing_order_id'])
        fundo=arch.xpath("//field[@name='fruit_fundo_id']")[0]
        self.assertEqual(fundo.getnext().get('name'),'company_id')
        self.assertEqual(len(arch.xpath("//field[@name='date']")),1)
        self.assertIn('step_export_packing',arch.xpath("//field[@name='packing_partner_id']/@domain")[0])
        self.assertEqual(model._fields['packing_partner_id'].comodel_name,'res.partner')

    def test_producer_proposes_first_own_fundo_and_retains_operator_choice(self):
        producer=self.env['res.partner'].create({'name':'QA Packing producer','is_productor':True})
        first=self.env['step.fundo'].create({'name':'QA First','partner_id':producer.id,'company_id':self.env.company.id})
        second=self.env['step.fundo'].create({'name':'QA Second','partner_id':producer.id,'company_id':self.env.company.id})
        form=Form(self.env['step.packing.production'])
        form.fruit_grower_id=producer
        self.assertEqual(form.fruit_fundo_id,first)
        form.fruit_fundo_id=second
        self.assertEqual(form.fruit_fundo_id,second)
        form.fruit_grower_id=False
        self.assertFalse(form.fruit_fundo_id)

    def test_reception_columns_are_ordered_with_one_editable_net_weight(self):
        arch=etree.fromstring(self.env['stock.picking'].get_view(view_id=self.env.ref('step_packing_reception_revision.view_process_reception_form').id,view_type='form')['arch'])
        columns=arch.xpath("//field[@name='fruit_tag_line_ids']/list/field")
        visible=[n.get('name') for n in columns if n.get('column_invisible') not in ('1','True') and n.get('optional')!='hide']
        self.assertEqual(visible[:13],['sequence','tag_number','product_id','packaging_id','uom_id','caliber_id','category_id','brand','quantity','gross_kg','tare_kg','kilos','step_kg_per_box'])
        self.assertNotIn('net_kg',visible)
        for field in ('gross_kg','tare_kg','kilos'):
            self.assertTrue(arch.xpath("//field[@name='fruit_tag_line_ids']/list/field[@name='%s']/@sum"%field))
        self.assertTrue(arch.xpath("//field[@name='step_kg_per_box']/@avg"))
        plant=arch.xpath("//field[@name='step_receiving_packing_id']")[0]
        self.assertEqual(plant.getnext().get('for'),'scheduled_date')

    def test_stock_actions_reuse_native_quants_and_include_descendants(self):
        from odoo.osv import expression
        for code,label in [('fruit','1 fruta'),('materials','6 materiales de embalajes')]:
            root=self.env['product.category'].search([('name','=ilike',label)])
            self.assertEqual(len(root),1)
            child=self.env['product.category'].create({'name':'QA Packing child','parent_id':root.id})
            product=self.env['product.product'].create({'name':'QA Report stock','categ_id':child.id,'is_storable':True})
            warehouse=self.env['stock.warehouse'].search([('company_id','=',self.env.company.id)],limit=1)
            self.env['stock.quant']._update_available_quantity(product,warehouse.lot_stock_id,5)
            action=self.env['stock.quant'].action_steps_packing_stock(code)
            self.assertEqual(action['res_model'],'stock.quant')
            found=self.env['stock.quant'].search(expression.AND([action['domain'],[('product_id','=',product.id)]]))
            self.assertEqual(sum(found.mapped('quantity')),5)
            self.assertFalse(self.env['stock.quant'].search(expression.AND([action['domain'],[('location_id.usage','=','supplier')]])))

    def test_reports_menu_reuses_reception_reports_and_native_tag_data(self):
        root=self.env.ref('step_packing_ticket_revision.reports')
        self.assertEqual(root.parent_id,self.env.ref('step_packing_operations.menu_packing_operations_root'))
        self.assertGreater(root.sequence,self.env.ref('step_packing_operations.menu_packing_operations_dispatch').sequence)
        for menu,action in [('process_receptions','action_process'),('packed_receptions','action_packed')]:
            self.assertEqual(self.env.ref('step_packing_ticket_revision.'+menu).action,self.env.ref('step_producer_fruit_reports.'+action))
        action=self.env.ref('step_packing_ticket_revision.tags')
        self.assertEqual(action.res_model,'stock.quant.package')
        self.assertEqual(safe_eval(action.domain),[('is_fruit_tag','=',True)])
        self.assertTrue(self.env['stock.quant.package']._fields['step_packing_partner_id'].store)

    def test_tag_packing_follows_reception_then_actual_process(self):
        partner=self.env['res.partner'].create({'name':'QA Reception Packing','step_export_packing':True})
        wh=self.env['stock.warehouse'].search([('company_id','=',self.env.company.id)],limit=1)
        picking=self.env['stock.picking'].create({'picking_type_id':wh.in_type_id.id,'location_id':wh.in_type_id.default_location_src_id.id,'location_dest_id':wh.lot_stock_id.id,'step_receiving_packing_id':partner.id})
        package=self.env['stock.quant.package'].create({'name':'QA Report Package','step_process_reception_id':picking.id})
        self.assertEqual(package.step_packing_partner_id,partner)
        other=self.env['res.partner'].create({'name':'QA Actual Packing','step_export_packing':True})
        production=self.env['step.packing.production'].create({'packing_partner_id':other.id,'date':'2026-10-23'})
        package.step_packing_production_id=production
        self.assertEqual(package.step_packing_partner_id,other)
        self.assertEqual(str(package.step_packing_date),'2026-10-23')
