from lxml import etree
from odoo.tests import TransactionCase, Form, tagged


@tagged('post_install', '-at_install')
class LayoutCase(TransactionCase):
    def test_effective_layout_preserves_fields_and_controls(self):
        arch=etree.fromstring(self.env['step.packing.production'].get_view(
            view_id=self.env.ref('step_packing_operations.view_packing_production_form').id,
            view_type='form')['arch'])
        expected={'ot_identity_left':['company_id','step_packing_order_id','step_packing_line_id','bom_id'],
            'ot_identity_right':['fruit_grower_id','fruit_fundo_id'],
            'ot_fruit_contract_left':['fruit_species_id','fruit_variety_id'],
            'ot_fruit_contract_right':['contract_id','contract_currency_id','contract_amount','purchase_bill_id'],
            'ot_raw_material_left':['raw_product_id'],'ot_instructions_left':['instruction_id'],
            'ot_instructions_right':['sales_program_id','sale_order_id']}
        for group,fields in expected.items():
            self.assertEqual(arch.xpath("//group[@name='%s']/field/@name"%group),fields)
        self.assertEqual(arch.xpath("//notebook[@name='fruit_details']/page[1]/@name"),['inputs'])
        self.assertEqual(arch.xpath("//field[@name='raw_product_id']/@readonly"),["state != 'created'"])
        self.assertTrue(arch.xpath("//field[@name='instruction_id']/@domain"))
        self.assertTrue(arch.xpath("//field[@name='contract_id']/@domain"))
        for button in ('action_step_packing_validate','action_step_packing_close','action_prepare_materials'):
            self.assertTrue(arch.xpath("//header/button[@name='%s']"%button))

    def test_existing_form_and_menu(self):
        action=self.env.ref('step_packing_operations.menu_packing_production').action
        self.assertEqual(action.res_model,'step.packing.production')
        slip=self.env['step.packing.production'].search([],limit=1)
        Form(slip or self.env['step.packing.production'],view='step_packing_operations.view_packing_production_form')
