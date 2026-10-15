from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.addons.step_packing_operations.tests.test_packing_operations import TestPackingOperations


@tagged('post_install', '-at_install', 'step_packing_producer_change')
class ProducerChangeCase(TransactionCase):
    def prepare(self, national=False):
        self.company = self.env.company
        self.location = self.env['stock.warehouse'].search([('company_id','=',self.company.id)],limit=1).lot_stock_id
        self.producer = self.env['res.partner'].create({'name':'Origen prueba T87','is_productor':True})
        self.buyer = self.env['res.partner'].create({'name':'Comercial prueba T87','is_productor':True})
        self.species = self.env['step.especie'].create({'name':'Especie T87','type_especie':'frutal','group_especie':'fruta_h'})
        group = self.env['step.grupo.variedad'].create({'name':'Grupo T87','especie_id':self.species.id})
        self.variety = self.env['step.variedad'].create({'name':'Variedad T87','cod_variedad':'T87','especie_id':self.species.id,'grupo_variedad_id':group.id})
        self.finished = self.env['product.product'].create({'name':'Cajas T87','is_storable':True,'weight':5,'grupo_labor':'pack'})
        self.source = TestPackingOperations._tag(self,'T87 origen', 'N' if national else 'E',self.finished,50,10,'commercial' if national else 'export')
        self.source.action_step_validate_tag()
        self.env['stock.quant']._update_available_quantity(self.finished,self.location,10,package_id=self.source)
        self.process = self.env['step.packing.process.type'].create({'name':'Cambio T87','step_category':'correction','changes_commercial_producer':True})
        self.repack = self.env['step.packing.repack'].create({'process_type_id':self.process.id,'selected_source_ids':[(6,0,self.source.ids)]})
        self.repack.action_prepare_distribution()
        self.target = self.repack.target_tag_ids

    def test_change_stock_traceability_and_print(self):
        self.prepare()
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.repack.action_validate()
        self.repack.write({'target_tag_ids': [(1,self.target.id,{'commercial_producer_id':self.buyer.id})]})
        self.assertEqual(self.repack.line_ids.commercial_producer_id,self.buyer)
        self.repack.line_ids.commercial_producer_id = self.buyer
        self.assertEqual(self.target.commercial_producer_id,self.buyer)
        self.repack.action_validate()
        self.assertEqual(self.target.step_producer_id,self.producer)
        self.assertEqual(self.target.step_tag_line_ids.producer_id,self.producer)
        self.assertEqual(self.target.step_tag_line_ids.source_package_id,self.source)
        self.assertEqual(self.target.step_actual_kg,50)
        self.assertEqual(sum(self.target.quant_ids.mapped('quantity')),10)
        self.assertEqual(sum(self.source.quant_ids.mapped('quantity')),0)
        self.assertEqual(self.repack.picking_id.state,'done')
        with self.assertRaises(UserError), self.cr.savepoint():
            self.target.commercial_producer_id = self.producer
        with self.assertRaises(UserError), self.cr.savepoint():
            self.repack.line_ids.commercial_producer_id = self.producer
        html,_ = self.env['ir.actions.report']._render_qweb_html('step_inventory_fruit_tag.action_report_fruit_tag', self.target.ids)
        self.assertIn(self.buyer.name,html.decode())
        self.assertIn('data:image/png;base64,',html.decode())
        self.assertNotIn('>'+self.producer.name+'<',html.decode())

    def test_normal_repack_inherits_and_rejects_new_change(self):
        self.prepare()
        self.repack.line_ids.commercial_producer_id = self.buyer
        self.repack.action_validate()
        normal = self.env['step.packing.repack'].create({'selected_source_ids':[(6,0,self.target.ids)]})
        normal.action_prepare_distribution()
        self.assertEqual(normal.target_tag_ids.commercial_producer_id,self.buyer)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            normal.target_tag_ids.commercial_producer_id = self.env['res.partner'].create({'name':'No productor'})
        normal.target_tag_ids.commercial_producer_id = self.producer
        with self.assertRaises(ValidationError), self.cr.savepoint():
            normal.action_validate()
        normal.target_tag_ids.commercial_producer_id = self.buyer
        normal.action_validate()
        self.assertEqual(normal.target_tag_ids.commercial_producer_id,self.buyer)

    def test_company_scope_and_effective_form(self):
        self.prepare(national=True)
        foreign_company = self.env['res.company'].create({'name':'Empresa T87'})
        foreign = self.env['res.partner'].create({'name':'Productor ajeno T87','is_productor':True,'company_id':foreign_company.id})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.target.commercial_producer_id = foreign
        self.repack.line_ids.commercial_producer_id = self.buyer
        self.repack.action_validate()
        self.assertEqual(self.target.step_tag_line_ids.producer_id,self.producer)
        view = self.env['step.packing.repack'].get_view(self.env.ref('step_packing_operations.view_packing_repack_form').id,'form')['arch']
        self.assertGreaterEqual(view.count('name="commercial_producer_id"'),2)
        menu = self.env.ref('step_packing_operations.menu_packing_repack')
        self.assertTrue(menu.active and menu.action.res_model == 'step.packing.repack')
