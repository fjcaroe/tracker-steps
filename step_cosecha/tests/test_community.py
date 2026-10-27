from odoo.tests import TransactionCase,tagged
from odoo.tests.common import new_test_user
from odoo.exceptions import UserError

@tagged('post_install','-at_install')
class HarvestCommunityCase(TransactionCase):
    def test_no_unknown_relations_in_harvest_models(self):
        models=self.env['ir.model'].search([('model','=like','step.cosecha.%')])
        self.assertTrue(models)
        for meta in models:
            for name,field in self.env[meta.model]._fields.items():
                if field.relational:
                    self.assertNotEqual(field.comodel_name,'_unknown',(meta.model,name))
                    self.assertIn(field.comodel_name,self.env.registry.models)

    def test_preserve_custom_sequence_parameters_on_repeated_upgrade_protection(self):
        import importlib.util
        from pathlib import Path
        spec=importlib.util.spec_from_file_location('harvest_pre',Path(__file__).parents[1]/'migrations/18.0.1.7.0/pre-migration.py')
        migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
        seq=self.env.ref('step_cosecha.seq_step_cosecha_propio')
        seq.write({'prefix':'PRIVATE/','padding':9,'number_increment':3})
        before=seq.read(['prefix','padding','number_increment','number_next','company_id'])
        migration.migrate(self.env.cr,'18.0.1.6.1');migration.migrate(self.env.cr,'18.0.1.6.1')
        seq.invalidate_recordset()
        self.assertEqual(seq.read(['prefix','padding','number_increment','number_next','company_id']),before)
        data=self.env['ir.model.data'].search([('module','=','step_cosecha'),('name','=','seq_step_cosecha_propio')])
        self.assertTrue(data.noupdate)

    def test_portal_denied_and_posted_harvest_guard(self):
        portal=new_test_user(self.env,login='private_harvest_portal',groups='base.group_portal')
        for model in ('step.cosecha.registry','step.cosecha.registry.line','step.history.cosecha'):
            self.assertFalse(self.env[model].with_user(portal).has_access('read'))
        harvest=self.env['step.cosecha.registry'].with_context(default_type_tarea='contratista').create({'name':'Private protected harvest','product_uom_id':self.env.ref('uom.product_uom_kgm').id})
        harvest.write({'state':'cont'})
        with self.assertRaises(UserError):harvest.unlink()

    def test_original_warehouse_marker_and_receipt_workflow(self):
        from odoo.addons.step_cosecha.hooks import pre_init_hook,post_init_hook
        self.assertEqual(self.env.ref('step_hr.field_stock_picking__cosecha'),
                         self.env.ref('step_cosecha.field_stock_picking__cosecha'))
        pre_init_hook(self.env);post_init_hook(self.env)
        company=self.env['res.company'].create({'name':'Private harvest receipt company'})
        scoped=self.env(context=dict(self.env.context,allowed_company_ids=company.ids))
        warehouse=scoped['stock.warehouse'].create({'name':'Private harvest warehouse','code':'HQA','company_id':company.id})
        partner=scoped['res.partner'].create({'name':'Private harvest contractor'})
        kg=scoped.ref('uom.product_uom_kgm')
        product=scoped['product.product'].create({'name':'Private harvest fruit','grupo_labor':'pack','type':'consu','uom_id':kg.id,'uom_po_id':kg.id})
        operator=new_test_user(scoped,login='private_harvest_receipt_operator',
            groups='base.group_user,hr.group_hr_user,stock.group_stock_user',
            company_id=company.id,company_ids=[(6,0,company.ids)])
        harvest=scoped['step.cosecha.registry'].with_user(operator).with_context(default_type_tarea='contratista').create({
            'name':'Private warehouse harvest','company_id':company.id,'partner_id':partner.id,
            'product_id':product.product_tmpl_id.id,'product_uom_id':kg.id,
            'tarja_registry_line':[(0,0,{'qty_kg':20})]})
        harvest.recibir_cosecha()
        picking=harvest.reception_picking_id
        self.assertTrue(picking.cosecha)
        self.assertEqual(picking.harvest_registry_id,harvest)
        self.assertEqual(picking.company_id,company)
        self.assertEqual(picking.move_ids.product_id,product)
        self.assertEqual(picking.move_ids.product_uom_qty,20)
        self.assertEqual(harvest.total_kilos,20)
        self.assertFalse(harvest.env.su)
        self.assertEqual(picking.location_dest_id,warehouse.in_type_id.default_location_dest_id)
        with self.assertRaises(UserError):harvest.recibir_cosecha()
        picking.action_confirm()
        for move in picking.move_ids:move.quantity=move.product_uom_qty
        picking.button_validate()
        self.assertEqual(picking.state,'done')
        self.assertTrue(harvest.cos_recibida)
